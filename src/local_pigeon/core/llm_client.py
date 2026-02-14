"""
Ollama LLM Client

Wrapper around the Ollama Python SDK with support for:
- Chat completions with message history
- Streaming responses
- Tool/function calling
- Model management
"""

import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable

import ollama
from ollama import AsyncClient


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
    """
    
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "llama3.2",
        temperature: float = 0.7,
        context_length: int = 8192,
    ):
        self.host = host
        self.model = model
        self.temperature = temperature
        self.context_length = context_length
        
        self._sync_client = ollama.Client(host=host)
        self._async_client = AsyncClient(host=host)
    
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
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions
            model: Override the default model
            
        Returns:
            The assistant's response message
        """
        ollama_messages = [m.to_ollama() for m in messages]
        ollama_tools = [t.to_ollama() for t in tools] if tools else None
        
        response = await self._async_client.chat(
            model=model or self.model,
            messages=ollama_messages,
            tools=ollama_tools,
            options={
                "temperature": self.temperature,
                "num_ctx": self.context_length,
            },
        )
        
        return Message.from_ollama(response.get("message", {}))
    
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
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions
            model: Override the default model
            on_chunk: Optional callback for each content chunk
            
        Returns:
            The complete assistant message
        """
        ollama_messages = [m.to_ollama() for m in messages]
        ollama_tools = [t.to_ollama() for t in tools] if tools else None
        
        full_content = ""
        final_message = None
        
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
                full_content += content
                if on_chunk:
                    on_chunk(content)
            
            # Keep the last message for tool_calls
            if chunk.get("done", False):
                final_message = message
        
        # Build the complete message
        if final_message:
            final_message["content"] = full_content
            return Message.from_ollama(final_message)
        
        return Message(role="assistant", content=full_content)
    
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
