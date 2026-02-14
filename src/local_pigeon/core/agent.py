"""
Local Pigeon Agent

The main agent orchestration layer that:
- Manages conversations with the LLM
- Handles tool registration and execution
- Implements the agentic loop (tool calling)
- Manages payment approvals
"""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

from local_pigeon.config import Settings, get_settings
from local_pigeon.core.llm_client import OllamaClient, Message, ToolDefinition, ToolCall
from local_pigeon.core.conversation import AsyncConversationManager
from local_pigeon.tools.registry import ToolRegistry, Tool


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
    """
    
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        
        # Initialize LLM client
        self.llm = OllamaClient(
            host=self.settings.ollama.host,
            model=self.settings.ollama.model,
            temperature=self.settings.ollama.temperature,
            context_length=self.settings.ollama.context_length,
        )
        
        # Initialize conversation manager
        db_path = self.settings.storage.database
        self.conversations = AsyncConversationManager(
            db_path=db_path,
            max_history=self.settings.agent.max_history_messages,
        )
        
        # Initialize tool registry
        self.tools = ToolRegistry()
        self._register_default_tools()
        
        # Pending approvals
        self._pending_approvals: dict[str, PendingApproval] = {}
        
        # Approval callbacks (set by platforms)
        self._approval_handlers: dict[str, Callable[[PendingApproval], Awaitable[bool]]] = {}
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # Web search tools
        if self.settings.web.search.enabled:
            from local_pigeon.tools.web.search import WebSearchTool
            self.tools.register(WebSearchTool(self.settings.web.search))
        
        if self.settings.web.fetch.enabled:
            from local_pigeon.tools.web.fetch import WebFetchTool
            self.tools.register(WebFetchTool(self.settings.web.fetch))
        
        # Google Workspace tools
        if self.settings.google.gmail_enabled:
            from local_pigeon.tools.google.gmail import GmailTool
            self.tools.register(GmailTool(self.settings.google))
        
        if self.settings.google.calendar_enabled:
            from local_pigeon.tools.google.calendar import CalendarTool
            self.tools.register(CalendarTool(self.settings.google))
        
        if self.settings.google.drive_enabled:
            from local_pigeon.tools.google.drive import DriveTool
            self.tools.register(DriveTool(self.settings.google))
        
        # Payment tools
        if self.settings.payments.stripe.enabled:
            from local_pigeon.tools.payments.stripe_card import StripeCardTool
            self.tools.register(StripeCardTool(
                self.settings.payments.stripe,
                self.settings.payments.approval,
            ))
        
        if self.settings.payments.crypto.enabled:
            from local_pigeon.tools.payments.crypto_wallet import CryptoWalletTool
            self.tools.register(CryptoWalletTool(
                self.settings.payments.crypto,
                self.settings.payments.approval,
            ))
    
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
        """Get the system prompt with tool information."""
        base_prompt = self.settings.agent.system_prompt
        
        if self.settings.agent.tools_enabled and self.tools.list_tools():
            tool_list = "\n".join(
                f"- {tool.name}: {tool.description}"
                for tool in self.tools.list_tools()
            )
            base_prompt += f"\n\nAvailable tools:\n{tool_list}"
        
        return base_prompt
    
    async def chat(
        self,
        user_message: str,
        user_id: str,
        session_id: str | None = None,
        platform: str = "cli",
        stream_callback: Callable[[str], None] | None = None,
    ) -> str:
        """
        Process a chat message and return the response.
        
        Args:
            user_message: The user's message
            user_id: The user's identifier
            session_id: Optional session/thread identifier
            platform: Platform name (cli, discord, telegram, web)
            stream_callback: Optional callback for streaming responses
            
        Returns:
            The assistant's response
        """
        # Get or create conversation
        conversation_id = await self.conversations.get_or_create_conversation(
            user_id=user_id,
            session_id=session_id,
            platform=platform,
        )
        
        # Get conversation history
        history = await self.conversations.get_messages(conversation_id)
        
        # Build messages for the LLM
        messages = [
            Message(role="system", content=self.get_system_prompt()),
            *history,
            Message(role="user", content=user_message),
        ]
        
        # Save user message
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
        Run the agentic loop, executing tools until completion.
        
        The loop continues while the model requests tool calls,
        up to max_iterations to prevent infinite loops.
        """
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Get LLM response
            if stream_callback and iteration == 1:
                # Stream the first response
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
            
            # If no tool calls, we're done
            if not response.tool_calls:
                return response.content
            
            # Add assistant message with tool calls
            messages.append(response)
            
            # Execute tool calls
            for tool_call in response.tool_calls:
                result = await self._execute_tool(
                    tool_call=tool_call,
                    user_id=user_id,
                    platform=platform,
                )
                
                # Handle approval requirements
                if result.requires_approval:
                    # Create pending approval
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
                    
                    # Try to get approval
                    approved = await self._request_approval(pending, platform)
                    
                    if approved:
                        # Re-execute with approval
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
                    
                    # Clean up
                    del self._pending_approvals[approval_id]
                
                # Add tool result to messages
                messages.append(Message(
                    role="tool",
                    content=result.result,
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                ))
        
        # Max iterations reached
        return "I've completed multiple steps but haven't reached a final answer. Please let me know if you'd like me to continue."
    
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
