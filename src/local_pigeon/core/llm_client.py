"""
Ollama LLM Client

Wrapper around the Ollama Python SDK with support for:
- Chat completions with message history
- Streaming responses
- Tool/function calling (native + prompt-based fallback)
- Model management
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable

import ollama
from ollama import AsyncClient


# Tool calling prompt template for models without native support
TOOL_SYSTEM_PROMPT = """You have access to the following tools. To use a tool, respond with a tool call in this exact format:

<tool_call>
{{"name": "tool_name", "arguments": {{"arg1": "value1"}}}}
</tool_call>

Available tools:
{tool_descriptions}

Important rules:
- Only use tools when needed to answer the user's question
- You can make multiple tool calls by including multiple <tool_call> blocks
- After receiving tool results, provide a natural response to the user
- If no tool is needed, just respond normally without any <tool_call> tags
"""


def parse_tool_calls_from_text(text: str) -> list[dict[str, Any]]:
    """Parse tool calls from model output text."""
    tool_calls = []
    pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
    
    matches = re.findall(pattern, text, re.DOTALL)
    for i, match in enumerate(matches):
        try:
            call_data = json.loads(match)
            tool_calls.append({
                "id": f"call_{i}",
                "name": call_data.get("name", ""),
                "arguments": call_data.get("arguments", {}),
            })
        except json.JSONDecodeError:
            continue
    
    return tool_calls


def strip_tool_calls_from_text(text: str) -> str:
    """Remove tool call tags from text to get the natural response."""
    pattern = r'<tool_call>\s*\{.*?\}\s*</tool_call>'
    cleaned = re.sub(pattern, '', text, flags=re.DOTALL)
    return cleaned.strip()


def build_tool_prompt(tools: list["ToolDefinition"]) -> str:
    """Build tool descriptions for the system prompt."""
    descriptions = []
    for tool in tools:
        params_str = json.dumps(tool.parameters, indent=2)
        descriptions.append(f"**{tool.name}**: {tool.description}\nParameters: {params_str}")
    
    return TOOL_SYSTEM_PROMPT.format(tool_descriptions="\n\n".join(descriptions))


@dataclass
class ToolCall:
    """Represents a tool call from the model."""
    
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    """A chat message."""
    
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None  # For tool responses
    
    def to_ollama(self) -> dict[str, Any]:
        """Convert to Ollama message format."""
        msg: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
        
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments,
                    }
                }
                for tc in self.tool_calls
            ]
        
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        
        if self.name:
            msg["name"] = self.name
        
        return msg
    
    @classmethod
    def from_ollama(cls, data: dict[str, Any]) -> "Message":
        """Create from Ollama response format."""
        tool_calls = []
        
        if "tool_calls" in data:
            for tc in data["tool_calls"]:
                func = tc.get("function", {})
                args = func.get("arguments", {})
                
                # Handle string arguments (need to parse JSON)
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                
                tool_calls.append(ToolCall(
                    id=tc.get("id", ""),
                    name=func.get("name", ""),
                    arguments=args,
                ))
        
        return cls(
            role=data.get("role", "assistant"),
            content=data.get("content", ""),
            tool_calls=tool_calls,
            tool_call_id=data.get("tool_call_id"),
            name=data.get("name"),
        )


@dataclass
class ToolDefinition:
    """Definition of a tool that can be called by the model."""
    
    name: str
    description: str
    parameters: dict[str, Any]
    
    def to_ollama(self) -> dict[str, Any]:
        """Convert to Ollama tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class OllamaClient:
    """
    Client for interacting with Ollama LLM.
    
    Provides both sync and async methods for chat completions,
    with support for tool calling and streaming.
    
    For models that don't support native tool calling, automatically
    falls back to prompt-based tool calling.
    """
    
    # Models known to not support native tool calling
    _models_without_native_tools: set[str] = set()
    
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "llama3.2",
        temperature: float = 0.7,
        context_length: int = 8192,
        force_prompt_tools: bool = False,
    ):
        self.host = host
        self.model = model
        self.temperature = temperature
        self.context_length = context_length
        self.force_prompt_tools = force_prompt_tools
        
        self._sync_client = ollama.Client(host=host)
        self._async_client = AsyncClient(host=host)
    
    def _should_use_prompt_tools(self, model: str) -> bool:
        """Check if we should use prompt-based tool calling for this model."""
        return self.force_prompt_tools or model in self._models_without_native_tools
    
    def _add_tool_prompt_to_messages(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> list[Message]:
        """Add tool calling instructions to the system prompt."""
        tool_prompt = build_tool_prompt(tools)
        
        # Find or create system message
        new_messages = []
        has_system = False
        
        for msg in messages:
            if msg.role == "system":
                # Prepend tool instructions to existing system prompt
                new_content = tool_prompt + "\n\n" + msg.content
                new_messages.append(Message(role="system", content=new_content))
                has_system = True
            else:
                new_messages.append(msg)
        
        if not has_system:
            # Add system message at the beginning
            new_messages.insert(0, Message(role="system", content=tool_prompt))
        
        return new_messages
    
    def _parse_tool_response(self, message: Message) -> Message:
        """Parse tool calls from the message content if using prompt-based tools."""
        if not message.content:
            return message
        
        tool_calls_data = parse_tool_calls_from_text(message.content)
        
        if tool_calls_data:
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    name=tc["name"],
                    arguments=tc["arguments"],
                )
                for tc in tool_calls_data
            ]
            
            # Clean the content to remove tool call tags
            cleaned_content = strip_tool_calls_from_text(message.content)
            
            return Message(
                role=message.role,
                content=cleaned_content,
                tool_calls=tool_calls,
            )
        
        return message
    
    def list_models(self) -> list[dict[str, Any]]:
        """List available models."""
        result = self._sync_client.list()
        return result.get("models", [])
    
    def pull_model(self, model: str) -> None:
        """Pull a model from the Ollama registry."""
        self._sync_client.pull(model)
    
    def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
    ) -> Message:
        """
        Send a chat completion request (synchronous).
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions
            model: Override the default model
            
        Returns:
            The assistant's response message
        """
        ollama_messages = [m.to_ollama() for m in messages]
        ollama_tools = [t.to_ollama() for t in tools] if tools else None
        
        response = self._sync_client.chat(
            model=model or self.model,
            messages=ollama_messages,
            tools=ollama_tools,
            options={
                "temperature": self.temperature,
                "num_ctx": self.context_length,
            },
        )
        
        return Message.from_ollama(response.get("message", {}))
    
    async def achat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
    ) -> Message:
        """
        Send a chat completion request (asynchronous).
        
        Automatically falls back to prompt-based tool calling if the
        model doesn't support native function calling.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions
            model: Override the default model
            
        Returns:
            The assistant's response message
        """
        use_model = model or self.model
        
        # Check if we should use prompt-based tools
        if tools and self._should_use_prompt_tools(use_model):
            return await self._achat_with_prompt_tools(messages, tools, use_model)
        
        # Try native tool calling first
        if tools:
            try:
                ollama_messages = [m.to_ollama() for m in messages]
                ollama_tools = [t.to_ollama() for t in tools]
                
                response = await self._async_client.chat(
                    model=use_model,
                    messages=ollama_messages,
                    tools=ollama_tools,
                    options={
                        "temperature": self.temperature,
                        "num_ctx": self.context_length,
                    },
                )
                
                return Message.from_ollama(response.get("message", {}))
                
            except ollama.ResponseError as e:
                # Check if the error is about tool support
                if "does not support tools" in str(e) or e.status_code == 400:
                    # Remember this model doesn't support native tools
                    self._models_without_native_tools.add(use_model)
                    # Retry with prompt-based tools
                    return await self._achat_with_prompt_tools(messages, tools, use_model)
                raise
        
        # No tools - simple chat
        ollama_messages = [m.to_ollama() for m in messages]
        
        response = await self._async_client.chat(
            model=use_model,
            messages=ollama_messages,
            options={
                "temperature": self.temperature,
                "num_ctx": self.context_length,
            },
        )
        
        return Message.from_ollama(response.get("message", {}))
    
    async def _achat_with_prompt_tools(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        model: str,
    ) -> Message:
        """Chat using prompt-based tool calling."""
        # Add tool instructions to messages
        enhanced_messages = self._add_tool_prompt_to_messages(messages, tools)
        ollama_messages = [m.to_ollama() for m in enhanced_messages]
        
        response = await self._async_client.chat(
            model=model,
            messages=ollama_messages,
            options={
                "temperature": self.temperature,
                "num_ctx": self.context_length,
            },
        )
        
        message = Message.from_ollama(response.get("message", {}))
        
        # Parse tool calls from the text response
        return self._parse_tool_response(message)
    
    async def achat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Send a streaming chat completion request.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions (note: streaming with tools may have limitations)
            model: Override the default model
            
        Yields:
            Content chunks as they arrive
        """
        ollama_messages = [m.to_ollama() for m in messages]
        ollama_tools = [t.to_ollama() for t in tools] if tools else None
        
        stream = await self._async_client.chat(
            model=model or self.model,
            messages=ollama_messages,
            tools=ollama_tools,
            stream=True,
            options={
                "temperature": self.temperature,
                "num_ctx": self.context_length,
            },
        )
        
        async for chunk in stream:
            message = chunk.get("message", {})
            content = message.get("content", "")
            if content:
                yield content
    
    async def achat_stream_full(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> Message:
        """
        Send a streaming chat request and collect the full response.
        
        This is useful when you want both streaming output and access
        to tool calls in the final response.
        
        Automatically falls back to prompt-based tool calling if the
        model doesn't support native function calling.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions
            model: Override the default model
            on_chunk: Optional callback for each content chunk
            
        Returns:
            The complete assistant message
        """
        use_model = model or self.model
        use_prompt_tools = tools is not None and self._should_use_prompt_tools(use_model)
        
        # Prepare messages - add tool prompt if using prompt-based tools
        if use_prompt_tools and tools:
            enhanced_messages = self._add_tool_prompt_to_messages(messages, tools)
            ollama_messages = [m.to_ollama() for m in enhanced_messages]
            ollama_tools = None  # Don't pass tools to Ollama
        else:
            ollama_messages = [m.to_ollama() for m in messages]
            ollama_tools = [t.to_ollama() for t in tools] if tools else None
        
        full_content = ""
        final_message = None
        
        try:
            stream = await self._async_client.chat(
                model=use_model,
                messages=ollama_messages,
                tools=ollama_tools,
                stream=True,
                options={
                    "temperature": self.temperature,
                    "num_ctx": self.context_length,
                },
            )
            
            async for chunk in stream:
                message = chunk.get("message", {})
                content = message.get("content", "")
                
                if content:
                    full_content += content
                    if on_chunk:
                        on_chunk(content)
                
                # Keep the last message for tool_calls
                if chunk.get("done", False):
                    final_message = message
            
        except ollama.ResponseError as e:
            # Check if the error is about tool support
            if tools and ("does not support tools" in str(e) or e.status_code == 400):
                # Remember this model doesn't support native tools
                self._models_without_native_tools.add(use_model)
                # Retry with prompt-based tools
                return await self.achat_stream_full(messages, tools, model, on_chunk)
            raise
        
        # Build the complete message
        if final_message:
            final_message["content"] = full_content
            result = Message.from_ollama(final_message)
        else:
            result = Message(role="assistant", content=full_content)
        
        # If using prompt-based tools, parse tool calls from text
        if use_prompt_tools:
            result = self._parse_tool_response(result)
        
        return result
    
    def generate_embeddings(
        self,
        text: str,
        model: str | None = None,
    ) -> list[float]:
        """
        Generate embeddings for text.
        
        Args:
            text: Text to embed
            model: Model to use (defaults to current model)
            
        Returns:
            Embedding vector
        """
        response = self._sync_client.embed(
            model=model or self.model,
            input=text,
        )
        
        embeddings = response.get("embeddings", [[]])
        return embeddings[0] if embeddings else []
    
    async def agenerate_embeddings(
        self,
        text: str,
        model: str | None = None,
    ) -> list[float]:
        """
        Generate embeddings for text (async).
        
        Args:
            text: Text to embed
            model: Model to use (defaults to current model)
            
        Returns:
            Embedding vector
        """
        response = await self._async_client.embed(
            model=model or self.model,
            input=text,
        )
        
        embeddings = response.get("embeddings", [[]])
        return embeddings[0] if embeddings else []
