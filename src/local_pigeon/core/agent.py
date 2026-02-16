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
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Awaitable

from local_pigeon.config import Settings, get_settings
from local_pigeon.core.llm_client import OllamaClient, Message, ToolDefinition, ToolCall, call_callback
from local_pigeon.core.conversation import AsyncConversationManager
from local_pigeon.storage.memory import AsyncMemoryManager, MemoryType
from local_pigeon.storage.failure_log import AsyncFailureLog
from local_pigeon.tools.registry import ToolRegistry, Tool


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
    ):
        self.settings = settings or get_settings()
        self.backend = backend
        
        # Initialize LLM client (with automatic backend selection)
        self.llm = _create_llm_client(self.settings, backend)
        
        # Initialize conversation manager
        db_path = self.settings.storage.database
        self.conversations = AsyncConversationManager(
            db_path=db_path,
            max_history=self.settings.agent.max_history_messages,
        )
        
        # Initialize memory manager
        self.memory = AsyncMemoryManager(db_path=db_path)
        
        # Initialize failure log for Ralph Loop pattern
        self.failure_log = AsyncFailureLog(db_path=db_path)
        
        # Initialize tool registry
        self.tools = ToolRegistry()
        self._register_default_tools()
        
        # Pending approvals
        self._pending_approvals: dict[str, PendingApproval] = {}
        
        # Approval callbacks (set by platforms)
        self._approval_handlers: dict[str, Callable[[PendingApproval], Awaitable[bool]]] = {}
        
        # Initialization flag
        self._initialized = False
    
    async def initialize(self) -> None:
        """
        Async initialization for the agent.
        
        Called once before first use to ensure database and other
        async resources are properly set up.
        """
        if self._initialized:
            return
        
        # Ensure database tables exist (sync manager handles this in __init__)
        # Any additional async setup can go here
        self._initialized = True
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # Web search tools
        if self.settings.web.search.enabled:
            from local_pigeon.tools.web.search import WebSearchTool
            self.tools.register(WebSearchTool(settings=self.settings.web.search))
        
        if self.settings.web.fetch.enabled:
            from local_pigeon.tools.web.fetch import WebFetchTool
            self.tools.register(WebFetchTool(settings=self.settings.web.fetch))
        
        # Browser automation (Playwright)
        if self.settings.web.browser.enabled:
            from local_pigeon.tools.web.browser import BrowserTool, BrowserSearchTool
            self.tools.register(BrowserTool(settings=self.settings.web.browser))
            self.tools.register(BrowserSearchTool(settings=self.settings.web.browser))
        
        # Google Workspace tools
        if self.settings.google.gmail_enabled:
            from local_pigeon.tools.google.gmail import GmailTool
            self.tools.register(GmailTool(settings=self.settings.google))
        
        if self.settings.google.calendar_enabled:
            from local_pigeon.tools.google.calendar import CalendarTool
            self.tools.register(CalendarTool(settings=self.settings.google))
        
        if self.settings.google.drive_enabled:
            from local_pigeon.tools.google.drive import DriveTool
            self.tools.register(DriveTool(settings=self.settings.google))
        
        # Payment tools
        if self.settings.payments.stripe.enabled:
            from local_pigeon.tools.payments.stripe_card import StripeCardTool
            self.tools.register(StripeCardTool(
                stripe_settings=self.settings.payments.stripe,
                approval_settings=self.settings.payments.approval,
            ))
        
        if self.settings.payments.crypto.enabled:
            from local_pigeon.tools.payments.crypto_wallet import CryptoWalletTool
            self.tools.register(CryptoWalletTool(
                crypto_settings=self.settings.payments.crypto,
                approval_settings=self.settings.payments.approval,
            ))
        
        # Self-healing tools (Ralph Loop pattern) - always enabled
        from local_pigeon.tools.self_healing import (
            ViewFailureLogTool,
            MarkFailureResolvedTool,
            AnalyzeFailurePatternsTool,
        )
        self.tools.register(ViewFailureLogTool(failure_log=self.failure_log))
        self.tools.register(MarkFailureResolvedTool(failure_log=self.failure_log))
        self.tools.register(AnalyzeFailurePatternsTool(failure_log=self.failure_log))
    
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
        
        return self.tools.list_tools()
    
    def register_discord_tools(self, bot: Any) -> None:
        """
        Register Discord-specific tools with the bot instance.
        
        Called by the Discord adapter when the bot connects.
        This allows the agent to perform actions on Discord.
        """
        if not self.settings.discord.enabled:
            return
        
        from local_pigeon.tools.discord import (
            DiscordSendMessageTool,
            DiscordSendDMTool,
            DiscordGetMessagesTool,
            DiscordAddReactionTool,
            DiscordListChannelsTool,
            DiscordCreateThreadTool,
            DiscordGetServerInfoTool,
        )
        
        # Register Discord tools with bot reference
        self.tools.register(DiscordSendMessageTool(bot=bot))
        self.tools.register(DiscordSendDMTool(bot=bot))
        self.tools.register(DiscordGetMessagesTool(bot=bot))
        self.tools.register(DiscordAddReactionTool(bot=bot))
        self.tools.register(DiscordListChannelsTool(bot=bot))
        self.tools.register(DiscordCreateThreadTool(bot=bot))
        self.tools.register(DiscordGetServerInfoTool(bot=bot))
    
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
    
    def get_system_prompt(self) -> str:
        """Get the base system prompt with current time and tool information."""
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
        
        base_prompt = time_context + self.settings.agent.system_prompt
        
        if self.settings.agent.tools_enabled and self.tools.list_tools():
            tool_list = "\n".join(
                f"- {tool.name}: {tool.description}"
                for tool in self.tools.list_tools()
            )
            base_prompt += f"\n\nAvailable tools:\n{tool_list}"
        
        return base_prompt
    
    async def get_personalized_system_prompt(self, user_id: str) -> str:
        """Get the system prompt personalized with user memories."""
        base_prompt = self.get_system_prompt()
        
        # Add user memories
        memory_context = await self.memory.format_memories_for_prompt(user_id)
        if memory_context:
            base_prompt += memory_context
        
        return base_prompt
    
    async def chat(
        self,
        user_message: str,
        user_id: str,
        session_id: str | None = None,
        platform: str = "cli",
        stream_callback: Callable[[str], None] | None = None,
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
        # If images are provided, check if we need to switch to a vision model
        if images:
            if not self.llm.is_vision_model():
                # Try to find a vision model
                vision_model = self.llm.get_vision_model()
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
        
        # Get or create conversation
        conversation_id = await self.conversations.get_or_create_conversation(
            user_id=user_id,
            session_id=session_id,
            platform=platform,
        )
        
        # Get conversation history
        history = await self.conversations.get_messages(conversation_id)
        
        # Get personalized system prompt with user memories
        system_prompt = await self.get_personalized_system_prompt(user_id)
        
        # Build messages for the LLM
        # Include images in the user message if provided
        user_msg = Message(role="user", content=user_message, images=images or [])
        
        messages = [
            Message(role="system", content=system_prompt),
            *history,
            user_msg,
        ]
        
        # Save user message (without images for storage)
        await self.conversations.add_message(
            conversation_id,
            Message(role="user", content=user_message),
        )
        
        # Get tool definitions
        tools = None
        if self.settings.agent.tools_enabled:
            tools = self.tools.get_tool_definitions()
        
        # Run the agentic loop
        response = await self._agentic_loop(
            messages=messages,
            tools=tools,
            user_id=user_id,
            platform=platform,
            stream_callback=stream_callback,
            max_iterations=self.settings.agent.max_tool_iterations,
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
        max_iterations: int = 10,
    ) -> str:
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
        """
        iteration = 0
        tool_results_this_session = []
        
        while iteration < max_iterations:
            iteration += 1
            
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
                final_response = response.content
                
                # If we executed tools, prepend a brief status
                if tool_results_this_session and stream_callback:
                    # Stream the final response
                    await call_callback(stream_callback, final_response)
                
                return final_response
            
            # Model wants to use tools - add assistant message
            messages.append(response)
            
            # Execute each tool call
            for tool_call in response.tool_calls:
                # Notify user that tool is being executed
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
                
                # Add tool result to conversation for next iteration
                messages.append(Message(
                    role="tool",
                    content=result.result,
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                ))
            
            # Continue loop - model will process tool results and decide next step
        
        # Max iterations reached - provide a helpful response
        return (
            f"I've completed {iteration} steps using tools but need more iterations to finish. "
            "Here's what I've done so far:\n"
            + "\n".join(f"- {r.name}: {'✓' if r.success else '✗'}" for r in tool_results_this_session)
            + "\n\nPlease let me know if you'd like me to continue."
        )
    
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
    
    async def clear_history(self, user_id: str, session_id: str | None = None) -> None:
        """Clear conversation history for a user."""
        conversation_id = await self.conversations.get_or_create_conversation(
            user_id=user_id,
            session_id=session_id,
        )
        await self.conversations.clear_conversation(conversation_id)
