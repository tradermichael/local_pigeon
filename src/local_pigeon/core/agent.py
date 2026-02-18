"""
Local Pigeon Agent

The main agent orchestration layer that:
- Manages conversations with the LLM
- Handles tool registration and execution
- Implements the agentic loop (tool calling)
- Manages payment approvals
- Supports multiple backends (Ollama, llama-cpp-python)
"""

import asyncio
import inspect
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable

from local_pigeon.config import Settings, get_settings, get_data_dir
from local_pigeon.core.llm_client import OllamaClient, Message, ToolDefinition, ToolCall, call_callback
from local_pigeon.core.conversation import AsyncConversationManager
from local_pigeon.core.skills import SkillsManager
from local_pigeon.core.ralph import RALPHLoop
from local_pigeon.core.capabilities import generate_capabilities_summary, generate_architecture_summary
from local_pigeon.storage.memory import AsyncMemoryManager, MemoryType
from local_pigeon.storage.failure_log import AsyncFailureLog
from local_pigeon.storage.user_settings import UserSettingsStore
from local_pigeon.storage.database import Database
from local_pigeon.tools.registry import ToolRegistry, Tool
from local_pigeon.core.interfaces import MemoryProvider, NetworkProvider, LocalDiskMemoryProvider, ToolProvider
from local_pigeon.core.default_tool_provider import DefaultToolProvider

logger = logging.getLogger(__name__)


class LLMBackend(Enum):
    """Available LLM backends."""
    OLLAMA = "ollama"
    LLAMA_CPP = "llama_cpp"
    AUTO = "auto"  # Try Ollama first, fallback to llama-cpp


def _check_ollama_available(host: str = "http://localhost:11434") -> bool:
    """Check if Ollama is running and accessible."""
    try:
        import httpx
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{host}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


def _create_llm_client(
    settings: Settings,
    backend: LLMBackend = LLMBackend.AUTO,
) -> Any:
    """
    Create the appropriate LLM client based on backend selection.
    
    Args:
        settings: Application settings
        backend: Which backend to use (auto will try Ollama first)
    
    Returns:
        LLM client instance (OllamaClient or LlamaCppClient)
    """
    if backend == LLMBackend.OLLAMA:
        return OllamaClient(
            host=settings.ollama.host,
            model=settings.ollama.model,
            temperature=settings.ollama.temperature,
            context_length=settings.ollama.context_length,
        )
    
    if backend == LLMBackend.LLAMA_CPP:
        from local_pigeon.core.llama_cpp_client import LlamaCppClient
        return LlamaCppClient(
            model_name=settings.ollama.model.replace(":latest", "").replace(":", "-"),
            temperature=settings.ollama.temperature,
            context_length=settings.ollama.context_length,
        )
    
    # AUTO: Try Ollama first, fallback to llama-cpp-python
    if _check_ollama_available(settings.ollama.host):
        return OllamaClient(
            host=settings.ollama.host,
            model=settings.ollama.model,
            temperature=settings.ollama.temperature,
            context_length=settings.ollama.context_length,
        )
    
    # Fallback to llama-cpp-python
    try:
        from local_pigeon.core.llama_cpp_client import LlamaCppClient, is_available
        if is_available():
            return LlamaCppClient(
                model_name=settings.ollama.model.replace(":latest", "").replace(":", "-"),
                temperature=settings.ollama.temperature,
                context_length=settings.ollama.context_length,
            )
    except ImportError:
        pass
    
    # Final fallback to Ollama (will error if not available)
    return OllamaClient(
        host=settings.ollama.host,
        model=settings.ollama.model,
        temperature=settings.ollama.temperature,
        context_length=settings.ollama.context_length,
    )


from enum import Enum


class StatusType(str, Enum):
    """Types of status events for UI transparency."""
    THINKING = "thinking"
    TOOL_START = "tool_start"
    TOOL_ARGS = "tool_args"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    ITERATION = "iteration"
    APPROVAL = "approval"
    DONE = "done"


@dataclass
class StatusEvent:
    """A status event for UI transparency."""
    type: StatusType
    message: str
    details: dict | None = None


@dataclass
class ToolResult:
    """Result from executing a tool."""
    
    tool_call_id: str
    name: str
    result: str
    success: bool = True
    requires_approval: bool = False
    approval_message: str | None = None


@dataclass
class PendingApproval:
    """A payment or action pending user approval."""
    
    id: str
    user_id: str
    tool_name: str
    arguments: dict[str, Any]
    amount: float | None
    description: str
    callback: Callable[[], Awaitable[str]] | None = None


class LocalPigeonAgent:
    """
    The main Local Pigeon agent.
    
    Handles:
    - Chat interactions with conversation history
    - Tool registration and execution
    - Agentic loop for multi-step tasks
    - Payment approval workflow
    - Multiple LLM backends (Ollama, llama-cpp-python)
    """
    
    def __init__(
        self,
        settings: Settings | None = None,
        backend: LLMBackend = LLMBackend.AUTO,
        memory_provider: MemoryProvider | None = None,
        network_provider: NetworkProvider | None = None,
        tool_registry: ToolRegistry | None = None,
        tool_provider: ToolProvider | None = None,
    ):
        self.settings = settings or get_settings()
        self.backend = backend
        
        # Initialize LLM client (with automatic backend selection)
        self.llm = _create_llm_client(self.settings, backend)
        
        # Build database path in data directory
        data_dir = get_data_dir()
        db_filename = self.settings.storage.database
        # If it's just a filename, put it in data_dir
        # If it's already an absolute path, use it as-is
        from pathlib import Path
        if Path(db_filename).is_absolute():
            db_path = db_filename
        else:
            db_path = str(data_dir / db_filename)

        # Dependency-injection providers
        self.memory_provider = memory_provider or LocalDiskMemoryProvider(db_path=db_path)
        self.network_provider = network_provider
        self.tool_provider = tool_provider or DefaultToolProvider()
        
        # Initialize conversation manager
        self.conversations = AsyncConversationManager(
            db_path=db_path,
            max_history=self.settings.agent.max_history_messages,
        )
        
        # Initialize memory manager (from provider when possible)
        native_memory = self.memory_provider.get_native_manager()
        if isinstance(native_memory, AsyncMemoryManager):
            self.memory = native_memory
        else:
            self.memory = AsyncMemoryManager(db_path=db_path)
        
        # Initialize failure log for Ralph Loop pattern
        self.failure_log = AsyncFailureLog(db_path=db_path)
        
        # Initialize user settings store
        self._database = Database(db_path=db_path)
        self.user_settings = UserSettingsStore(database=self._database)
        
        # Initialize skills manager and RALPH loop for self-improvement
        self.skills = SkillsManager(data_dir=data_dir)
        self.ralph = RALPHLoop(
            skills_manager=self.skills,
            failure_log=self.failure_log,
        )
        
        # Initialize heartbeat for periodic self-reflection
        from local_pigeon.core.heartbeat import Heartbeat
        self.heartbeat = Heartbeat(
            agent=self,
            interval_minutes=self.settings.agent.heartbeat_interval_minutes,
            enabled=self.settings.agent.heartbeat_enabled,
            auto_approve_skills=self.settings.agent.auto_approve_skills,
        )
        
        # Initialize scheduler for cron-like recurring tasks
        from local_pigeon.core.scheduler import Scheduler
        self.scheduler = Scheduler(
            db_path=db_path,
            agent=self,
            heartbeat_seconds=30.0,
        )
        
        # Initialize tool registry
        self.tools = tool_registry or ToolRegistry()
        self._register_default_tools()

        # Event hooks for extension points (free/enterprise wrappers)
        self._event_hooks: dict[str, list[Callable[[dict[str, Any]], Any]]] = defaultdict(list)
        self.on("memory_saved", lambda payload: logger.debug("memory_saved event: %s", payload))
        
        # Initialize MCP manager (connected in initialize() if enabled)
        self.mcp_manager: Any = None
        
        # Pending approvals
        self._pending_approvals: dict[str, PendingApproval] = {}
        
        # Approval callbacks (set by platforms)
        self._approval_handlers: dict[str, Callable[[PendingApproval], Awaitable[bool]]] = {}
        self._message_handlers: dict[str, Callable[..., Awaitable[None]]] = {}
        
        # Initialization flag
        self._initialized = False

        # Scheduler completion callback for proactive notifications
        self.scheduler.add_callback(self._handle_scheduled_task_completion)

    def on(self, event_name: str, callback: Callable[[dict[str, Any]], Any]) -> None:
        """Register an event callback.

        Example:
            agent.on("memory_saved", callback)
        """
        self._event_hooks[event_name].append(callback)

    def off(self, event_name: str, callback: Callable[[dict[str, Any]], Any]) -> None:
        """Unregister a previously registered event callback."""
        callbacks = self._event_hooks.get(event_name, [])
        if callback in callbacks:
            callbacks.remove(callback)

    async def trigger(self, event_name: str, payload: dict[str, Any]) -> None:
        """Trigger event callbacks for a given event name."""
        for callback in list(self._event_hooks.get(event_name, [])):
            try:
                result = callback(payload)
                if inspect.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.debug("Event hook '%s' failed: %s", event_name, exc)
    
    async def initialize(self) -> None:
        """
        Async initialization for the agent.
        
        Called once before first use to ensure database and other
        async resources are properly set up.
        """
        if self._initialized:
            return
        
        # Initialize database schema (creates tables if not exist)
        await self._database.initialize()
        
        # Connect to MCP servers (if enabled)
        await self._connect_mcp_servers()
        
        # Start heartbeat if enabled
        if self.settings.agent.heartbeat_enabled:
            await self.heartbeat.start()
        
        # Start scheduler for recurring tasks
        await self.scheduler.start()
        
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Clean shutdown of the agent."""
        # Stop heartbeat
        await self.heartbeat.stop()
        
        # Stop scheduler
        await self.scheduler.stop()
        
        # Disconnect MCP servers
        if self.mcp_manager:
            await self.mcp_manager.disconnect_all()
        
        # Close LLM client session
        if self.llm:
            await self.llm.close()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        for tool in self.tool_provider.get_tools(self):
            self.tools.register(tool)
    
    def reload_tools(self) -> list[str]:
        """
        Reload all tools based on current settings.
        
        Call this after changing settings to register/unregister tools
        without restarting the entire application.
        
        Returns:
            List of registered tool names
        """
        # Clear existing tools
        self.tools = ToolRegistry()
        
        # Re-register all tools
        self._register_default_tools()
        
        return [tool.name for tool in self.tools.list_tools()]
    
    async def _connect_mcp_servers(self) -> None:
        """Connect to configured MCP servers and register their tools."""
        self.mcp_manager, mcp_tools = await self.tool_provider.get_mcp_tools(self)
        for tool in mcp_tools:
            self.tools.register(tool)

        if mcp_tools:
            logger.info(f"Registered {len(mcp_tools)} MCP tools")
    
    async def reload_mcp_servers(self) -> list[str]:
        """
        Reload MCP servers from config without full restart.
        
        Returns:
            List of newly registered MCP tool names
        """
        # Disconnect existing MCP servers
        if self.mcp_manager:
            await self.mcp_manager.disconnect_all()
        
        # Unregister existing MCP tools
        existing_tools = list(self.tools._tools.keys())
        for name in existing_tools:
            if name.startswith("mcp_"):
                self.tools.unregister(name)
        
        # Reload settings
        from local_pigeon.config import reload_settings
        self.settings = reload_settings()
        
        # Reconnect
        await self._connect_mcp_servers()
        
        # Return new tool names
        return [t.name for t in self.tools.list_tools() if t.name.startswith("mcp_")]

    def register_discord_tools(self, bot: Any) -> None:
        """
        Register Discord-specific tools with the bot instance.
        
        Called by the Discord adapter when the bot connects.
        This allows the agent to perform actions on Discord.
        """
        for tool in self.tool_provider.get_discord_tools(self, bot):
            self.tools.register(tool)
    
    def register_approval_handler(
        self,
        platform: str,
        handler: Callable[[PendingApproval], Awaitable[bool]],
    ) -> None:
        """
        Register a handler for approval requests on a platform.
        
        The handler should display the approval request to the user
        and return True if approved, False if denied.
        """
        self._approval_handlers[platform] = handler

    def register_message_handler(
        self,
        platform: str,
        handler: Callable[..., Awaitable[None]],
    ) -> None:
        """Register a proactive message sender for a platform."""
        self._message_handlers[platform] = handler

        # Best-effort flush of pending notifications queued while offline
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._flush_pending_notifications(platform))
        except RuntimeError:
            pass
    
    def get_system_prompt(
        self,
        bot_name: str | None = None,
        user_name: str | None = None,
    ) -> str:
        """
        Get the base system prompt with current time and tool information.
        
        Args:
            bot_name: Name for the bot (defaults to config default)
            user_name: Name for the user (optional, for personalization)
        """
        from datetime import datetime
        
        # Get current date/time in user-friendly format
        now = datetime.now()
        
        # Format: "Friday, February 14, 2026 at 3:45 PM"
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M %p").lstrip("0")
        
        # Build the prompt with current time context
        time_context = f"""Current date and time: {date_str} at {time_str}
Timezone: {datetime.now().astimezone().tzinfo}

"""
        
        # Get effective bot name
        effective_bot_name = bot_name or self.settings.agent.default_bot_name
        
        # Format the system prompt with bot name
        system_prompt = self.settings.agent.system_prompt.format(
            bot_name=effective_bot_name,
            user_name=user_name or "the user",
        )
        
        # Add user name context if provided
        if user_name:
            system_prompt += f"\n\nIMPORTANT: The user prefers to be called \"{user_name}\". Address them by this name when appropriate."
        
        base_prompt = time_context + system_prompt
        
        # Add capabilities summary with architecture context
        # This helps the model understand what it IS and what it CAN DO
        if self.settings.agent.tools_enabled and self.tools.list_tools():
            available_tools = [tool.name for tool in self.tools.list_tools()]
            capabilities = generate_capabilities_summary(
                available_tools=available_tools,
                include_examples=True,
            )
            base_prompt += f"\n\n{capabilities}"
            
            # For reasoning models, add architecture context
            if any(x in self.llm.model.lower() for x in ["deepseek", "r1", "qwen"]):
                base_prompt += f"\n{generate_architecture_summary()}"
        
        return base_prompt
    
    async def get_personalized_system_prompt(
        self,
        user_id: str,
        user_message: str | None = None,
    ) -> str:
        """
        Get the system prompt personalized with user settings, memories, and skills.
        
        Args:
            user_id: User identifier for personalization
            user_message: Optional user message to find relevant skills
        """
        # Get user settings for personalization
        user_settings = await self.user_settings.get(user_id)
        
        bot_name = user_settings.bot_name
        user_name = user_settings.user_display_name if user_settings.user_display_name else None
        
        base_prompt = self.get_system_prompt(bot_name=bot_name, user_name=user_name)
        
        # Add user memories
        memory_context = await self.memory_provider.format_context_for_prompt(user_id)
        if memory_context:
            base_prompt += memory_context
        
        # Add relevant skills from RALPH loop
        # This teaches the model how to correctly use tools based on learned patterns
        if user_message:
            skill_context = self.ralph.get_enhanced_prompt(user_message)
            if skill_context:
                base_prompt += skill_context
        
        return base_prompt
    
    async def _preflight_grounding(
        self,
        user_message: str,
        stream_callback: Callable[[str], None] | None = None,
        status_callback: Callable[[StatusEvent], None] | None = None,
    ) -> str:
        """
        Check if query needs factual grounding and pre-fetch results if so.
        
        This ensures the model gets accurate, up-to-date information for
        factual questions rather than relying on (potentially outdated) training data.
        
        Args:
            user_message: The user's question
            stream_callback: Optional callback for status updates
            status_callback: Optional callback for status events
            
        Returns:
            Grounding context string to inject into system prompt, or empty string
        """
        from local_pigeon.core.grounding import GroundingClassifier
        
        # Two-stage classification: fast patterns first, then LLM if uncertain
        classifier = GroundingClassifier(llm_client=self.llm)
        
        # Try fast classification first
        fast_result = classifier.classify_fast(user_message)
        
        # If high confidence, use fast result; otherwise use LLM classification
        if fast_result.confidence >= 0.7:
            result = fast_result
            classification_method = "pattern"
        else:
            # Use LLM for uncertain cases
            if stream_callback:
                await call_callback(stream_callback, f"🤔 Uncertain query ({fast_result.confidence:.0%}), using LLM classifier...\n")
            result = await classifier.classify(user_message, use_llm=True)
            classification_method = "LLM"
        
        # Always show classification in stream so user knows what happened
        if stream_callback:
            grounding_type = "FACTUAL" if result.needs_grounding else "NON-FACTUAL"
            await call_callback(stream_callback, f"📊 Classification [{classification_method}]: {grounding_type} (confidence: {result.confidence:.0%}, reason: {result.reason})\n")
        
        # Only proceed if we're confident grounding is needed
        if not result.needs_grounding or result.confidence < 0.7:
            return ""
        
        # Get web_search tool
        web_search = self.tools.get_tool("web_search")
        if not web_search:
            return ""
        
        # Notify user we're doing a pre-search
        if status_callback:
            await call_callback(status_callback, StatusEvent(
                type=StatusType.THINKING,
                message="🔍 Pre-fetching factual information...",
            ))
        
        # Execute search
        search_query = result.suggested_query or user_message
        try:
            search_result = await web_search.execute(query=search_query, num_results=5)
            
            if search_result and "Error" not in search_result:
                # Return the raw search results - they'll be injected as tool messages
                # which the model naturally trusts more than system/user injections
                if stream_callback:
                    await call_callback(stream_callback, "🔍 Found relevant information\n")
                return search_result
        except Exception as e:
            # Log but don't fail - model can still use tools if needed
            if stream_callback:
                await call_callback(stream_callback, f"⚠️ Pre-search failed: {e}\n")
        
        return ""
    
    async def chat(
        self,
        user_message: str,
        user_id: str,
        session_id: str | None = None,
        platform: str = "cli",
        stream_callback: Callable[[str], None] | None = None,
        status_callback: Callable[[StatusEvent], None] | None = None,
        images: list[str] | None = None,
    ) -> str:
        """
        Process a chat message and return the response.
        
        Args:
            user_message: The user's message
            user_id: The user's identifier
            session_id: Optional session/thread identifier
            platform: Platform name (cli, discord, telegram, web)
            stream_callback: Optional callback for streaming responses
            images: Optional list of base64-encoded images for vision models
            
        Returns:
            The assistant's response
        """
        # Track if we need to restore the model after vision processing
        original_model = None
        is_vision_request = False
        
        # If images are provided, check if we need to switch to a vision model
        if images:
            is_vision_request = True
            if not self.llm.is_vision_model():
                # Try to find a vision model (prefer user's configured choice)
                preferred_vision = self.settings.ollama.vision_model or None
                vision_model = self.llm.get_vision_model(preferred=preferred_vision)
                if vision_model:
                    # Temporarily switch to vision model for this request
                    original_model = self.llm.model
                    self.llm.model = vision_model
                    # Log the model switch
                    if stream_callback:
                        stream_callback(f"🖼️ Switching to vision model: {vision_model}\\n\\n")
                else:
                    if stream_callback:
                        stream_callback("⚠️ No vision model available. Install one with: `ollama pull llava`\\n\\n")
                    # Continue without images
                    images = None
                    is_vision_request = False
        
        # Get or create conversation
        conversation_id = await self.conversations.get_or_create_conversation(
            user_id=user_id,
            session_id=session_id,
            platform=platform,
        )
        
        # Get conversation history
        history = await self.conversations.get_messages(conversation_id)
        
        # Get personalized system prompt with user memories and relevant skills
        system_prompt = await self.get_personalized_system_prompt(user_id, user_message)
        
        # Grounding preflight: check if query needs factual grounding
        # If so, pre-fetch search results and inject as synthetic tool call/response
        # This makes the model trust the results as if it called web_search itself
        grounding_context = ""
        preflight_tool_messages = []
        if self.settings.agent.tools_enabled and not is_vision_request:
            grounding_context = await self._preflight_grounding(
                user_message, 
                stream_callback, 
                status_callback
            )
        
        # Build the user message (no augmentation - we'll use tool messages instead)
        user_msg = Message(role="user", content=user_message, images=images or [])
        
        messages = [
            Message(role="system", content=system_prompt),
            *history,
            user_msg,
        ]
        
        # If we have grounding context, inject it as synthetic tool call + result
        # The model will see: "I called web_search and got these results"
        # This is MORE trusted than user-injected context
        if grounding_context:
            import uuid
            tool_call_id = f"preflight_{uuid.uuid4().hex[:8]}"
            
            # Add assistant message with tool call (model "called" web_search)
            messages.append(Message(
                role="assistant",
                content=None,
                tool_calls=[{
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": f'{{"query": "{user_message}"}}',
                    }
                }],
            ))
            
            # Add tool result message (web_search "returned" results)
            # Include forceful grounding instructions since the model trusts tool results
            messages.append(Message(
                role="tool",
                content=f"""╔══════════════════════════════════════════════════════════════════════════════╗
║                    ⚠️  LIVE WEB SEARCH RESULTS  ⚠️                            ║
║  Date: {datetime.now().strftime('%Y-%m-%d')} (TODAY)                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

{grounding_context}

╔══════════════════════════════════════════════════════════════════════════════╗
║  CRITICAL INSTRUCTIONS:                                                       ║
║  1. Your training data is OUTDATED - these search results are CURRENT         ║
║  2. Use ONLY the facts from the search results above                          ║
║  3. Include citations: mention source name/URL for key facts                  ║
║  4. Example format: "According to [Source], Trump is the current president"   ║
║  5. Do NOT contradict the search results with your training data              ║
╚══════════════════════════════════════════════════════════════════════════════╝""",
                tool_call_id=tool_call_id,
                name="web_search",
            ))
        
        # Save user message (without images for storage)
        await self.conversations.add_message(
            conversation_id,
            Message(role="user", content=user_message),
        )
        
        # Get tool definitions
        # Skip tools for vision requests as most vision models don't support them well
        tools = None
        if self.settings.agent.tools_enabled and not is_vision_request:
            tools = self.tools.get_tool_definitions()
        
        try:
            # Run the agentic loop
            response, tool_calls_made, tools_used = await self._agentic_loop(
                messages=messages,
                tools=tools,
                user_id=user_id,
                platform=platform,
                stream_callback=stream_callback,
                status_callback=status_callback,
                max_iterations=self.settings.agent.max_tool_iterations,
            )
        finally:
            # Restore original model if we switched for vision
            if original_model:
                self.llm.model = original_model
        
        # RALPH Loop: Check if model should have used tools but didn't
        # This allows the agent to learn from failures and improve over time
        if tools and not tool_calls_made:
            expected_tool = self.ralph.detect_expected_tool(user_message)
            if expected_tool and self.ralph.detect_refusal(response):
                # Model refused to use a tool it should have used - learn from this
                skill = self.ralph.learn_from_failure(
                    user_message=user_message,
                    model_response=response,
                )
                if skill and stream_callback:
                    await call_callback(
                        stream_callback,
                        f"\n💡 RALPH: Learned new pattern for '{skill.tool}' tool\n"
                    )
        
        # RALPH Loop: Check for incomplete multi-tool usage
        # This catches cases like "who is the president AND check my email"
        # where the model only uses one tool and hallucinates the rest
        if tools and tool_calls_made:
            # Get tools that were actually used from the agentic loop
            missing_tools = self.ralph.detect_missing_tools(
                user_message=user_message,
                tools_used=tools_used,
                model_response=response,
            )
            if missing_tools and stream_callback:
                # Model hallucinated instead of using all required tools
                await call_callback(
                    stream_callback,
                    f"\n⚠️ RALPH: Detected incomplete tool usage. "
                    f"Missing: {', '.join(missing_tools)}\n"
                )
                # Learn from this failure
                for missing in missing_tools:
                    skill = self.ralph.learn_from_failure(
                        user_message=user_message,
                        model_response=response,
                    )
                    if skill:
                        await call_callback(
                            stream_callback,
                            f"💡 Learned pattern for '{skill.tool}' tool\n"
                        )
        
        # Save assistant response
        await self.conversations.add_message(
            conversation_id,
            Message(role="assistant", content=response),
        )
        
        return response
    
    async def _agentic_loop(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None,
        user_id: str,
        platform: str,
        stream_callback: Callable[[str], None] | None = None,
        status_callback: Callable[[StatusEvent], None] | None = None,
        max_iterations: int = 10,
    ) -> tuple[str, bool, list[str]]:
        """
        Run the agentic orchestrator loop, executing tools until task completion.
        
        The loop continues while the model requests tool calls,
        up to max_iterations to prevent infinite loops. After executing
        tools, results are fed back to the model to continue reasoning.
        
        This implements the pattern:
        1. Reasoning: Model decides what to do
        2. Tool Call: Model requests tool execution
        3. Execution: We run the tool and get results
        4. Re-entry: Feed results back to model
        5. Repeat until model provides final answer without tool calls
        
        Returns:
            Tuple of (response_text, tool_calls_made, tools_used_names)
        """
        iteration = 0
        tool_results_this_session = []
        recent_tool_calls: list[tuple[str, str]] = []  # Track (name, args_hash) for dedup
        
        def get_tool_signature(name: str, args: dict) -> tuple[str, str]:
            """Get a signature for a tool call for deduplication."""
            import json
            args_str = json.dumps(args, sort_keys=True) if args else ""
            return (name, args_str)
        
        # Helper to emit status events
        async def emit_status(type: StatusType, message: str, details: dict | None = None):
            if status_callback:
                event = StatusEvent(type=type, message=message, details=details)
                if asyncio.iscoroutinefunction(status_callback):
                    await status_callback(event)
                else:
                    status_callback(event)
        
        while iteration < max_iterations:
            iteration += 1
            
            # Emit iteration status if we're doing multiple iterations
            if iteration > 1:
                await emit_status(
                    StatusType.ITERATION,
                    f"Analyzing tool results (step {iteration}/{max_iterations})...",
                    {"iteration": iteration, "max": max_iterations}
                )
            elif tools:
                await emit_status(
                    StatusType.THINKING,
                    "Thinking...",
                    {"has_tools": True}
                )
            
            # Get LLM response
            if stream_callback and iteration == 1 and not tool_results_this_session:
                # Stream only the very first response before any tools are called
                response = await self.llm.achat_stream_full(
                    messages=messages,
                    tools=tools,
                    on_chunk=stream_callback,
                )
            else:
                response = await self.llm.achat(
                    messages=messages,
                    tools=tools,
                )
            
            # Check if model is done (no tool calls)
            if not response.tool_calls:
                # Model provided a final answer
                await emit_status(
                    StatusType.THINKING,
                    f"Model response (no tools): {(response.content or '')[:100]}...",
                    {"has_tool_calls": False, "content_length": len(response.content or "")}
                )
                final_response = response.content
                
                # Handle empty response with retries and model fallback
                if not final_response or not final_response.strip():
                    retry_result = await self._handle_empty_response(
                        messages=messages,
                        tools=tools,
                        iteration=iteration,
                        tool_results_this_session=tool_results_this_session,
                        emit_status=emit_status,
                    )
                    
                    # Check if result is a Response object (model wants to use tools)
                    if hasattr(retry_result, 'tool_calls') and retry_result.tool_calls:
                        # Model returned tool_calls during retry - process them normally
                        response = retry_result
                        # Fall through to tool processing below (outside this if block)
                    elif retry_result:
                        # Got a text response
                        final_response = retry_result
                    else:
                        # Still nothing, continue to next iteration
                        continue
            
            # If model has tool_calls (original or from retry), process them
            if response.tool_calls:
                pass  # Fall through to tool processing below
            else:
                # No tool_calls - return the final response
                # Final safety net - never return empty
                if not final_response or not final_response.strip():
                    final_response = "I received your message but couldn't generate a response. Please try rephrasing or try a different model."
                 
                # Get list of tool names used
                tools_used = list(set(r.name for r in tool_results_this_session))
                   
                # If we executed tools, prepend a brief status
                if tool_results_this_session:
                    await emit_status(
                        StatusType.DONE,
                        f"Completed using {len(tool_results_this_session)} tool(s)",
                        {"tools_used": tools_used}
                    )
                    if stream_callback:
                        # Stream the final response
                        await call_callback(stream_callback, final_response)
                
                return final_response, len(tool_results_this_session) > 0, tools_used
            
            # Model wants to use tools - check for duplicates BEFORE adding to conversation
            current_signatures = [
                get_tool_signature(tc.name, tc.arguments)
                for tc in response.tool_calls
            ]
            
            # If all tool calls in this batch are duplicates from recent calls, nudge the model
            duplicates = [sig for sig in current_signatures if sig in recent_tool_calls]
            if duplicates and len(duplicates) == len(current_signatures):
                # All calls are duplicates - don't execute, provide synthetic results
                await emit_status(
                    StatusType.ITERATION,
                    "Detected repeated tool calls, nudging model to provide answer...",
                    {"duplicates": [d[0] for d in duplicates]}
                )
                
                # Add the assistant message (required for valid conversation flow)
                messages.append(response)
                
                # Add synthetic tool results telling model it already has the data
                for tc in response.tool_calls:
                    messages.append(Message(
                        role="tool",
                        content=f"You already called {tc.name} with these arguments and received results above. "
                                "Please review the previous results and provide your final answer to the user.",
                        tool_call_id=tc.id,
                        name=tc.name,
                    ))
                
                continue  # Let model reconsider with the nudge
            
            # Not duplicates - add assistant message and track signatures
            messages.append(response)
            recent_tool_calls.extend(current_signatures)
            recent_tool_calls = recent_tool_calls[-10:]
            
            # Execute each tool call
            for tool_call in response.tool_calls:
                # Emit detailed status about tool being used
                await emit_status(
                    StatusType.TOOL_START,
                    f"Using {tool_call.name}",
                    {"tool": tool_call.name}
                )
                
                # Format arguments nicely for status
                if tool_call.arguments:
                    args_display = ", ".join(
                        f"{k}={repr(v)[:50]}..." if len(repr(v)) > 50 else f"{k}={repr(v)}"
                        for k, v in tool_call.arguments.items()
                    )
                    await emit_status(
                        StatusType.TOOL_ARGS,
                        f"→ {args_display}",
                        {"tool": tool_call.name, "arguments": tool_call.arguments}
                    )
                
                # Notify user that tool is being executed (for stream output)
                if stream_callback:
                    await call_callback(stream_callback, f"\n🔧 Using {tool_call.name}...\n")
                
                # Checkpoint mode: require approval for every tool execution
                if self.settings.agent.checkpoint_mode:
                    approval_id = str(uuid.uuid4())
                    pending = PendingApproval(
                        id=approval_id,
                        user_id=user_id,
                        tool_name=tool_call.name,
                        arguments=tool_call.arguments,
                        amount=None,
                        description=f"[Checkpoint Mode] Execute {tool_call.name} with args: {tool_call.arguments}",
                    )
                    self._pending_approvals[approval_id] = pending
                    
                    if stream_callback:
                        await call_callback(stream_callback, f"\n⏸️ Checkpoint: Awaiting approval for {tool_call.name}...\n")
                    
                    approved = await self._request_approval(pending, platform)
                    del self._pending_approvals[approval_id]
                    
                    if not approved:
                        result = ToolResult(
                            tool_call_id=tool_call.id,
                            name=tool_call.name,
                            result="Tool execution skipped by user (checkpoint mode).",
                            success=False,
                        )
                        tool_results_this_session.append(result)
                        await emit_status(
                            StatusType.TOOL_ERROR,
                            f"❌ {tool_call.name}: Skipped (checkpoint mode)",
                            {"tool": tool_call.name, "success": False}
                        )
                        messages.append(Message(
                            role="tool",
                            content=result.result,
                            tool_call_id=tool_call.id,
                            name=tool_call.name,
                        ))
                        continue
                
                result = await self._execute_tool(
                    tool_call=tool_call,
                    user_id=user_id,
                    platform=platform,
                )
                
                # Handle approval requirements
                if result.requires_approval:
                    approval_id = str(uuid.uuid4())
                    pending = PendingApproval(
                        id=approval_id,
                        user_id=user_id,
                        tool_name=tool_call.name,
                        arguments=tool_call.arguments,
                        amount=tool_call.arguments.get("amount"),
                        description=result.approval_message or f"Execute {tool_call.name}",
                    )
                    self._pending_approvals[approval_id] = pending
                    
                    approved = await self._request_approval(pending, platform)
                    
                    if approved:
                        result = await self._execute_tool(
                            tool_call=tool_call,
                            user_id=user_id,
                            platform=platform,
                            approved=True,
                        )
                    else:
                        result = ToolResult(
                            tool_call_id=tool_call.id,
                            name=tool_call.name,
                            result="User denied the request.",
                            success=False,
                        )
                    
                    del self._pending_approvals[approval_id]
                
                # Track tool results
                tool_results_this_session.append(result)
                
                # Emit tool result status
                if result.success:
                    # Truncate result for display
                    result_preview = result.result[:100] + "..." if len(result.result) > 100 else result.result
                    await emit_status(
                        StatusType.TOOL_RESULT,
                        f"✓ {result.name}: {result_preview}",
                        {"tool": result.name, "success": True, "result": result.result}
                    )
                else:
                    await emit_status(
                        StatusType.TOOL_ERROR,
                        f"✗ {result.name}: {result.result[:100]}",
                        {"tool": result.name, "success": False, "error": result.result}
                    )
                
                # Add tool result to conversation for next iteration
                messages.append(Message(
                    role="tool",
                    content=result.result,
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                ))
            
            # Continue loop - model will process tool results and decide next step
        
        # Max iterations reached - provide a helpful response
        # Debug: show what happened in each iteration
        debug_info = f"(Tools available: {len(tools) if tools else 0})"
        tools_used = list(set(r.name for r in tool_results_this_session))
        return (
            f"I've completed {iteration} steps using tools but need more iterations to finish. "
            f"{debug_info}\n"
            "Here's what I've done so far:\n"
            + ("\n".join(f"- {r.name}: {'✓' if r.success else '✗'}" for r in tool_results_this_session) or "- (no tools executed)")
            + "\n\nPlease let me know if you'd like me to continue.",
            len(tool_results_this_session) > 0,  # Only True if tools were actually called
            tools_used,
        )
    
    async def _handle_empty_response(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None,
        iteration: int,
        tool_results_this_session: list,
        emit_status: Callable,
    ) -> str | None:
        """
        Handle empty responses with retries and model fallback.
        
        Returns:
            The response string if successful, or None to continue the loop
            (e.g., if model now wants to use tools).
        """
        import asyncio
        
        max_retries = self.settings.ollama.max_retries
        retry_delay = self.settings.ollama.retry_delay
        fallback_models = self.settings.ollama.fallback_models
        original_model = self.llm.model
        
        # Only retry on first iteration before any tools were called
        if iteration > 1 or tool_results_this_session:
            return None
        
        # Retry with the current model
        for retry in range(max_retries):
            await emit_status(
                StatusType.THINKING,
                f"Retrying ({retry + 1}/{max_retries})...",
                {"retry": retry + 1, "max_retries": max_retries}
            )
            
            if retry > 0:
                await asyncio.sleep(retry_delay * retry)  # Exponential backoff
            
            response = await self.llm.achat(
                messages=messages,
                tools=tools,
            )
            
            if response.tool_calls:
                # Model now wants to use tools - return the response
                # so the main loop can process the tool calls
                return response
            
            if response.content and response.content.strip():
                return response.content
        
        # Try fallback models
        for fallback_model in fallback_models:
            if fallback_model == original_model:
                continue  # Skip the model we already tried
            
            # Check if fallback model is available
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{self.settings.ollama.host}/api/tags")
                    if resp.status_code == 200:
                        models = [m["name"] for m in resp.json().get("models", [])]
                        if fallback_model not in models:
                            continue  # Model not installed, skip
            except Exception:
                continue  # Can't check, skip
            
            await emit_status(
                StatusType.THINKING,
                f"Trying fallback model: {fallback_model}",
                {"fallback_model": fallback_model}
            )
            
            # Temporarily switch to fallback model
            self.llm.model = fallback_model
            
            try:
                response = await self.llm.achat(
                    messages=messages,
                    tools=tools,
                )
                
                if response.tool_calls:
                    # Model wants to use tools - return the response
                    return response
                
                if response.content and response.content.strip():
                    # Success! Keep using this model for the rest of this conversation
                    return f"*(Switched to {fallback_model})*\n\n{response.content}"
            except Exception:
                pass  # Try next fallback
            finally:
                # Restore original model for next request
                self.llm.model = original_model
        
        # All retries and fallbacks failed
        return None

    async def _execute_tool(
        self,
        tool_call: ToolCall,
        user_id: str,
        platform: str,
        approved: bool = False,
    ) -> ToolResult:
        """Execute a single tool call."""
        tool = self.tools.get_tool(tool_call.name)
        
        if not tool:
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                result=f"Error: Tool '{tool_call.name}' not found.",
                success=False,
            )
        
        try:
            # Check if tool requires approval
            if tool.requires_approval and not approved:
                amount = tool_call.arguments.get("amount", 0)
                threshold = self.settings.payments.approval.threshold
                
                if amount > threshold:
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        name=tool_call.name,
                        result="",
                        requires_approval=True,
                        approval_message=f"Payment of ${amount:.2f} requires approval.",
                    )
            
            # Execute the tool
            result = await tool.execute(
                user_id=user_id,
                **tool_call.arguments,
            )

            await self.trigger(
                "tool_executed",
                {
                    "tool": tool_call.name,
                    "arguments": tool_call.arguments,
                    "result": str(result),
                    "user_id": user_id,
                    "platform": platform,
                },
            )

            if tool_call.name == "remember":
                await self.trigger(
                    "memory_saved",
                    {
                        "tool": tool_call.name,
                        "arguments": tool_call.arguments,
                        "result": str(result),
                        "user_id": user_id,
                        "platform": platform,
                    },
                )
            
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                result=str(result),
                success=True,
            )
            
        except Exception as e:
            # Log failure for Ralph Loop pattern
            await self.failure_log.log_failure(
                tool_name=tool_call.name,
                error=e,
                arguments=tool_call.arguments,
                user_id=user_id,
                platform=platform,
            )

            await self.trigger(
                "tool_error",
                {
                    "tool": tool_call.name,
                    "arguments": tool_call.arguments,
                    "error": str(e),
                    "user_id": user_id,
                    "platform": platform,
                },
            )
            
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                result=f"Error executing tool: {str(e)}",
                success=False,
            )
    
    async def _request_approval(
        self,
        pending: PendingApproval,
        platform: str,
    ) -> bool:
        """Request approval from the user via their platform."""
        handler = self._approval_handlers.get(platform)
        
        if not handler:
            # No handler registered, auto-deny for safety
            return False
        
        try:
            return await asyncio.wait_for(
                handler(pending),
                timeout=self.settings.payments.approval.timeout,
            )
        except asyncio.TimeoutError:
            return False

    async def _handle_scheduled_task_completion(self, task: Any, result: str) -> None:
        """Send or queue scheduler results so users receive proactive updates."""
        run_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        message = (
            f"⏰ Scheduled task completed\n\n"
            f"Name: {task.name}\n"
            f"Run time: {run_time}\n"
            f"Result:\n{result}"
        )
        await self._send_or_queue_scheduled_notification(
            user_id=task.user_id,
            platform=task.platform,
            message=message,
            task_id=task.id,
        )

    async def _send_or_queue_scheduled_notification(
        self,
        *,
        user_id: str,
        platform: str,
        message: str,
        task_id: str | None,
    ) -> None:
        """Try real-time send; fallback to durable queue."""
        handler = self._message_handlers.get(platform)
        if handler:
            try:
                await handler(user_id, message)
                return
            except Exception:
                logger.debug("Scheduled notification send failed; queueing", exc_info=True)

        await self.scheduler.store.add_notification(
            task_id=task_id,
            user_id=user_id,
            platform=platform,
            message=message,
        )

    async def _flush_pending_notifications(self, platform: str) -> None:
        """Flush queued notifications for a platform once a sender is available."""
        handler = self._message_handlers.get(platform)
        if not handler:
            return

        pending = await self.scheduler.store.get_pending_notifications(platform=platform, limit=200)
        for notification in pending:
            try:
                await handler(notification["user_id"], notification["message"])
                await self.scheduler.store.mark_notification_delivered(notification["id"])
            except Exception:
                logger.debug(
                    "Failed delivering pending notification %s on %s",
                    notification["id"],
                    platform,
                    exc_info=True,
                )
    
    async def approve_pending(self, approval_id: str) -> bool:
        """Approve a pending action by ID."""
        if approval_id in self._pending_approvals:
            # The approval will be handled in the agentic loop
            return True
        return False
    
    async def deny_pending(self, approval_id: str) -> bool:
        """Deny a pending action by ID."""
        if approval_id in self._pending_approvals:
            del self._pending_approvals[approval_id]
            return True
        return False
    
    def set_model(self, model: str) -> None:
        """Change the active model."""
        self.llm.model = model
        self.settings.ollama.model = model

        # Best-effort sync event for wrappers observing model changes
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.trigger("model_changed", {"model": model}))
        except RuntimeError:
            pass
    
    async def clear_history(self, user_id: str, session_id: str | None = None) -> None:
        """Clear conversation history for a user."""
        conversation_id = await self.conversations.get_or_create_conversation(
            user_id=user_id,
            session_id=session_id,
        )
        await self.conversations.clear_conversation(conversation_id)
