"""
Ollama LLM Client

Wrapper around the Ollama Python SDK with support for:
- Chat completions with message history
- Streaming responses
- Tool/function calling (native + prompt-based fallback)
- Model management
"""

import asyncio
import inspect
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Awaitable, Union

import ollama
from ollama import AsyncClient

# Logger for this module
logger = logging.getLogger("local_pigeon.llm_client")

# Type for callbacks that can be sync or async
ChunkCallback = Callable[[str], Union[None, Awaitable[None]]]


async def call_callback(callback: ChunkCallback | None, chunk: str) -> None:
    """Call a callback that might be sync or async."""
    if callback is None:
        return
    result = callback(chunk)
    if inspect.iscoroutine(result):
        await result


# Tool calling prompt template for models without native support
TOOL_SYSTEM_PROMPT = """You have access to tools. You MUST use them when the user asks for information you don't have.

TO USE A TOOL, respond with ONLY this format (nothing else):

<tool_call>
{{"name": "tool_name", "arguments": {{"arg1": "value1"}}}}
</tool_call>

Available tools:
{tool_descriptions}

CRITICAL INSTRUCTIONS:
1. When user asks about their emails → USE gmail tool with {{"action": "list"}}
2. When user asks about their calendar → USE calendar tool with {{"action": "list"}}  
3. When user asks about current events/news → USE web_search tool
4. DO NOT say "I can't access" or "I'm unable to" - USE THE TOOL INSTEAD
5. DO NOT suggest the user do it themselves - USE THE TOOL FOR THEM
6. The user has already authorized these tools via OAuth - you have permission

EXAMPLES:
User: "what are my latest emails?"
You respond: <tool_call>
{{"name": "gmail", "arguments": {{"action": "list", "max_results": 5}}}}
</tool_call>

User: "what's on my calendar today?"
You respond: <tool_call>
{{"name": "calendar", "arguments": {{"action": "list"}}}}
</tool_call>

After receiving tool results, provide a helpful summary to the user.
"""


def parse_tool_calls_from_text(text: str) -> list[dict[str, Any]]:
    """
    Parse tool calls from model output text.
    
    Handles multiple formats:
    - Properly formatted: <tool_call>{...}</tool_call>
    - Missing opening tag: </tool_call>{...} or {...}</tool_call>
    - Raw JSON with name/arguments structure
    """
    tool_calls = []
    
    # Pattern 1: Properly formatted tool calls
    pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
    matches = re.findall(pattern, text, re.DOTALL)
    
    # Pattern 2: Malformed - JSON followed by closing tag (no opening)
    if not matches:
        pattern2 = r'(\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\})\s*</tool_call>'
        matches = re.findall(pattern2, text, re.DOTALL)
    
    # Pattern 3: Closing tag followed by JSON (weird but handles some models)
    if not matches:
        pattern3 = r'</tool_call>\s*(\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\})'
        matches = re.findall(pattern3, text, re.DOTALL)
    
    # Pattern 4: Raw JSON objects that look like tool calls (no tags at all)
    if not matches:
        pattern4 = r'\{[^{}]*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{[^{}]*\})[^{}]*\}'
        raw_matches = re.findall(pattern4, text, re.DOTALL)
        for i, (name, args_str) in enumerate(raw_matches):
            try:
                args = json.loads(args_str)
                tool_calls.append({
                    "id": f"call_{i}",
                    "name": name,
                    "arguments": args,
                })
            except json.JSONDecodeError:
                continue
        if tool_calls:
            return tool_calls
    
    # Parse matches from patterns 1-3
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
    """
    Remove tool call tags and raw tool call JSON from text.
    
    Handles:
    - Properly formatted: <tool_call>{...}</tool_call>
    - Orphan tags: </tool_call>, <tool_call>
    - Raw JSON tool calls
    """
    # Remove properly formatted tool calls
    pattern = r'<tool_call>\s*\{.*?\}\s*</tool_call>'
    cleaned = re.sub(pattern, '', text, flags=re.DOTALL)
    
    # Remove orphan closing tags followed by JSON
    pattern2 = r'</tool_call>\s*\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}'
    cleaned = re.sub(pattern2, '', cleaned, flags=re.DOTALL)
    
    # Remove JSON followed by orphan closing tags
    pattern3 = r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}\s*</tool_call>'
    cleaned = re.sub(pattern3, '', cleaned, flags=re.DOTALL)
    
    # Remove any remaining orphan tags
    cleaned = re.sub(r'</?tool_call>', '', cleaned)
    
    # Remove raw JSON tool call objects that look like tool calls
    # (JSON with "name" and "arguments" keys at the start)
    pattern4 = r'^\s*\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}\s*\}\s*$'
    cleaned = re.sub(pattern4, '', cleaned, flags=re.MULTILINE | re.DOTALL)
    
    # Also handle when it's at the start with other content after
    pattern5 = r'^\s*\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}\s*\}\s*\n*'
    cleaned = re.sub(pattern5, '', cleaned, flags=re.MULTILINE)
    
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
    images: list[str] = field(default_factory=list)  # Base64-encoded images for vision models
    
    def to_ollama(self) -> dict[str, Any]:
        """Convert to Ollama message format."""
        msg: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
        
        # Add images for vision-capable models
        if self.images:
            msg["images"] = self.images
        
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
    
    # Models known to not support native tool calling (use prompt-based instead)
    _models_without_native_tools: set[str] = set()
    
    # Model families that should always use prompt-based tools
    # Note: qwen3 and gemma3 have good native tool support, so they're NOT included
    # We only match exact base names to avoid matching substrings incorrectly
    PROMPT_TOOL_MODEL_FAMILIES = {
        "deepseek-r1", "deepseek-r1-distill",  # Reasoning models - always need prompt tools
        "qwq",  # QwQ reasoning model - needs prompt tools
        "phi", "phi3", "phi4",  # Microsoft Phi models - native unreliable
        "gemma", "gemma2",  # Gemma 1/2 - native unreliable (gemma3 works natively)
        "tinyllama", "orca-mini",  # Smaller models - no native support
    }
    
    # Cache for model capabilities
    _model_capabilities_cache: dict[str, dict[str, Any]] = {}
    
    # Known vision-capable model families (base names without tags)
    VISION_MODEL_FAMILIES = {
        "llava", "llava-llama3", "llava-phi3", "bakllava",
        "moondream", "moondream2",
        "llama3.2-vision", "minicpm-v",
        "cogvlm", "yi-vl", "nanollava",
        "gemma3",  # gemma3 models include vision support
        "ministral",  # Ministral 3 family
        "ministral3",  # alternative naming
        "mistral-small3",  # Mistral Small 3.x family
        "mistral-small3.1",  # explicit 3.1 tag
    }
    
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
        self._closed = False
        
        self._sync_client = ollama.Client(host=host)
        self._async_client = AsyncClient(host=host)
    
    def _ensure_client(self) -> None:
        """Ensure the async client is ready, recreating if closed."""
        if self._closed:
            logger.debug("Recreating closed async client")
            self._async_client = AsyncClient(host=self.host)
            self._closed = False
    
    async def close(self) -> None:
        """Close the async client session."""
        if hasattr(self._async_client, '_client') and self._async_client._client:
            try:
                await self._async_client._client.aclose()
            except Exception:
                pass  # Already closed
        self._closed = True
    
    def _should_use_prompt_tools(self, model: str) -> bool:
        """Check if we should use prompt-based tool calling for this model."""
        if self.force_prompt_tools or model in self._models_without_native_tools:
            return True
        
        # Check if model family should use prompt-based tools
        base_name = self._get_model_base_name(model)
        
        # Models with good native tool support - skip prompt tools for these
        NATIVE_TOOL_MODELS = {"qwen3", "qwen2.5", "gemma3", "llama3", "llama3.1", "llama3.2", "mistral"}
        for native in NATIVE_TOOL_MODELS:
            if base_name == native or base_name.startswith(native + "-"):
                return False
        
        # Check against prompt tool model families
        for family in self.PROMPT_TOOL_MODEL_FAMILIES:
            if base_name == family or base_name.startswith(family):
                return True
        
        return False
    
    def _add_tool_prompt_to_messages(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> list[Message]:
        """Add tool calling instructions to the system prompt.
        
        For prompt-based tool calling, we also need to convert 'tool' role
        messages to a format the model understands, since many models
        don't have a native 'tool' role.
        """
        tool_prompt = build_tool_prompt(tools)
        
        # Process messages
        new_messages = []
        has_system = False
        
        for msg in messages:
            if msg.role == "system":
                # Prepend tool instructions to existing system prompt
                new_content = tool_prompt + "\n\n" + msg.content
                new_messages.append(Message(role="system", content=new_content))
                has_system = True
            elif msg.role == "tool":
                # Convert tool result to a user message format the model understands
                tool_result_content = f"""<tool_result>
Tool: {msg.name}
Result: {msg.content}
</tool_result>

Based on this tool result, please continue with your task. Either use another tool if needed, or provide your final answer to the user."""
                new_messages.append(Message(role="user", content=tool_result_content))
            elif msg.role == "assistant" and msg.tool_calls:
                # For assistant messages with tool calls, show what tool was called
                tool_call_summary = "\n".join(
                    f"[Called tool: {tc.name} with args: {json.dumps(tc.arguments)}]"
                    for tc in msg.tool_calls
                )
                content = msg.content + "\n" + tool_call_summary if msg.content else tool_call_summary
                new_messages.append(Message(role="assistant", content=content))
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
        # Handle both old dict format and new typed object format
        raw_models = result.get("models", []) if isinstance(result, dict) else getattr(result, "models", [])
        models = []
        for m in raw_models:
            if isinstance(m, dict):
                models.append(m)
            else:
                # Convert typed object to dict
                models.append({
                    "name": getattr(m, "model", getattr(m, "name", str(m))),
                    "size": getattr(m, "size", 0),
                    "modified_at": str(getattr(m, "modified_at", "")),
                    "digest": getattr(m, "digest", ""),
                })
        return models
    
    def pull_model(self, model: str) -> None:
        """Pull a model from the Ollama registry."""
        self._sync_client.pull(model)
    
    def _get_model_base_name(self, model: str) -> str:
        """Extract the base model name without tags (e.g., 'llava:13b' -> 'llava')."""
        return model.split(":")[0].lower()
    
    def is_vision_model(self, model: str | None = None) -> bool:
        """
        Check if a model supports vision/image inputs.
        
        Args:
            model: Model name to check (defaults to current model)
        
        Returns:
            True if the model supports images
        """
        check_model = model or self.model
        base_name = self._get_model_base_name(check_model)
        
        # Check against known vision model families
        for family in self.VISION_MODEL_FAMILIES:
            if base_name.startswith(family) or base_name == family:
                return True
        
        # Check cache for previously determined capabilities
        if check_model in self._model_capabilities_cache:
            return self._model_capabilities_cache[check_model].get("vision", False)
        
        return False
    
    async def get_model_capabilities(self, model: str | None = None) -> dict[str, Any]:
        """
        Get capabilities for a model.
        
        Args:
            model: Model name to check (defaults to current model)
        
        Returns:
            Dict with capabilities: vision, context_length, parameter_size, etc.
        """
        check_model = model or self.model
        
        # Return cached if available
        if check_model in self._model_capabilities_cache:
            return self._model_capabilities_cache[check_model]
        
        self._ensure_client()
        capabilities = {
            "name": check_model,
            "vision": self.is_vision_model(check_model),
            "tool_calling": check_model not in self._models_without_native_tools,
        }
        
        # Try to get model info from Ollama
        try:
            info = await self._async_client.show(check_model)
            if info:
                # Extract useful info
                model_info = info.get("modelfile", "")
                details = info.get("details", {})
                
                capabilities["family"] = details.get("family", "")
                capabilities["parameter_size"] = details.get("parameter_size", "")
                capabilities["quantization"] = details.get("quantization_level", "")
                
                # Check modelfile for vision-related info
                if "vision" in model_info.lower() or "image" in model_info.lower():
                    capabilities["vision"] = True
        except Exception:
            pass
        
        # Cache the result
        self._model_capabilities_cache[check_model] = capabilities
        return capabilities
    
    async def list_models_with_capabilities(self) -> list[dict[str, Any]]:
        """
        List all available models with their capabilities.
        
        Returns:
            List of model dicts with name, vision, size, etc.
        """
        self._ensure_client()
        models = []
        
        try:
            result = await self._async_client.list()
            raw_models = result.get("models", [])
            
            for model in raw_models:
                name = model.get("name", "")
                
                model_info = {
                    "name": name,
                    "size": model.get("size", 0),
                    "modified": model.get("modified_at", ""),
                    "vision": self.is_vision_model(name),
                    "digest": model.get("digest", "")[:12],
                }
                
                # Format size for display
                size_gb = model_info["size"] / (1024 ** 3)
                model_info["size_display"] = f"{size_gb:.1f} GB" if size_gb >= 1 else f"{model_info['size'] / (1024 ** 2):.0f} MB"
                
                models.append(model_info)
        except Exception:
            pass
        
        return models
    
    def get_vision_model(self, preferred: str | None = None) -> str | None:
        """
        Get a vision-capable model from available models.
        
        Args:
            preferred: Preferred vision model name (used if available)
        
        Returns the preferred model if available and vision-capable,
        otherwise the first vision model found, or None if none available.
        """
        try:
            models = self.list_models()
            model_names = [m.get("name", "") for m in models]
            
            # Check preferred model first
            if preferred:
                # Check exact match
                if preferred in model_names and self.is_vision_model(preferred):
                    return preferred
                # Check partial match (e.g., "llava" matches "llava:7b")
                for name in model_names:
                    if preferred.lower() in name.lower() and self.is_vision_model(name):
                        return name
            
            # Fall back to first available vision model
            for name in model_names:
                if self.is_vision_model(name):
                    return name
        except Exception:
            pass
        return None
    
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
        self._ensure_client()
        use_model = model or self.model
        
        # Log the request
        user_msg = next((m.content for m in reversed(messages) if m.role == "user"), "")
        logger.debug(f"Chat request: model={use_model}, tools={len(tools) if tools else 0}, user_msg={user_msg[:100]}...")
        
        # Check if we should use prompt-based tools
        if tools and self._should_use_prompt_tools(use_model):
            logger.debug(f"Using prompt-based tools for model {use_model}")
            return await self._achat_with_prompt_tools(messages, tools, use_model)
        
        # Try native tool calling first
        if tools:
            try:
                ollama_messages = [m.to_ollama() for m in messages]
                ollama_tools = [t.to_ollama() for t in tools]
                
                logger.debug(f"Sending chat with native tools to Ollama")
                response = await self._async_client.chat(
                    model=use_model,
                    messages=ollama_messages,
                    tools=ollama_tools,
                    options={
                        "temperature": self.temperature,
                        "num_ctx": self.context_length,
                    },
                )
                
                result = Message.from_ollama(response.get("message", {}))
                logger.debug(f"Response: tool_calls={len(result.tool_calls) if result.tool_calls else 0}, content_len={len(result.content or '')}")
                if result.tool_calls:
                    logger.info(f"Model called tools: {[tc.name for tc in result.tool_calls]}")
                return result
                
            except ollama.ResponseError as e:
                # Check if the error is about tool support
                if "does not support tools" in str(e) or e.status_code == 400:
                    # Remember this model doesn't support native tools
                    logger.info(f"Model {use_model} doesn't support native tools, switching to prompt-based")
                    self._models_without_native_tools.add(use_model)
                    # Retry with prompt-based tools
                    return await self._achat_with_prompt_tools(messages, tools, use_model)
                logger.error(f"Ollama error: {e}")
                raise
        
        # No tools - simple chat
        ollama_messages = [m.to_ollama() for m in messages]
        
        logger.debug(f"Sending simple chat (no tools) to Ollama")
        response = await self._async_client.chat(
            model=use_model,
            messages=ollama_messages,
            options={
                "temperature": self.temperature,
                "num_ctx": self.context_length,
            },
        )
        
        result = Message.from_ollama(response.get("message", {}))
        logger.debug(f"Response received: {len(result.content or '')} chars")
        return result
    
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
        self._ensure_client()
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
        on_chunk: ChunkCallback | None = None,
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
        self._ensure_client()
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
        
        # For prompt-based tools, we need to buffer content to filter tool calls from display
        display_buffer = ""
        tool_call_pattern_start = "<tool_call>"
        in_tool_call = False
        
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
                        if use_prompt_tools:
                            # Buffer content and filter out tool calls for display
                            display_buffer += content
                            
                            # Process buffer to send displayable content
                            while True:
                                if in_tool_call:
                                    # Look for end of tool call
                                    end_idx = display_buffer.find("</tool_call>")
                                    if end_idx != -1:
                                        # Skip past the tool call
                                        display_buffer = display_buffer[end_idx + len("</tool_call>"):]
                                        in_tool_call = False
                                    else:
                                        # Still inside tool call, wait for more
                                        break
                                else:
                                    # First, check for orphan </tool_call> (malformed output)
                                    orphan_end = display_buffer.find("</tool_call>")
                                    if orphan_end != -1:
                                        # Remove orphan closing tag and everything before it that looks like JSON
                                        # (the model probably outputted malformed tool call)
                                        before_tag = display_buffer[:orphan_end]
                                        # Check if there's JSON-like content to skip
                                        json_start = before_tag.rfind("{")
                                        if json_start != -1 and '"name"' in before_tag[json_start:]:
                                            # Skip the JSON and closing tag
                                            display_buffer = display_buffer[orphan_end + len("</tool_call>"):]
                                        else:
                                            # Just skip the orphan tag
                                            display_buffer = before_tag + display_buffer[orphan_end + len("</tool_call>"):]
                                        continue
                                    
                                    # Look for start of tool call
                                    start_idx = display_buffer.find("<tool_call>")
                                    if start_idx == -1:
                                        # No tool call found - check for raw JSON tool calls
                                        # Pattern: {"name": "...", "arguments": {...}}
                                        json_match = re.search(
                                            r'\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{',
                                            display_buffer
                                        )
                                        if json_match:
                                            # Found JSON tool call - send content before it and wait
                                            if json_match.start() > 0:
                                                await call_callback(on_chunk, display_buffer[:json_match.start()])
                                            # Keep from the JSON start to see if it completes
                                            display_buffer = display_buffer[json_match.start():]
                                            # Check if we have a complete JSON object
                                            brace_count = 0
                                            json_end = -1
                                            for i, c in enumerate(display_buffer):
                                                if c == '{':
                                                    brace_count += 1
                                                elif c == '}':
                                                    brace_count -= 1
                                                    if brace_count == 0:
                                                        json_end = i
                                                        break
                                            if json_end != -1:
                                                # Complete JSON found - skip it
                                                display_buffer = display_buffer[json_end + 1:]
                                                continue
                                            else:
                                                # Incomplete JSON - wait for more
                                                break
                                        
                                        # Check if we might be starting one
                                        # Keep potential partial matches in buffer
                                        potential_start = -1
                                        for i in range(1, len("<tool_call>")):
                                            if display_buffer.endswith("<tool_call>"[:i]):
                                                potential_start = len(display_buffer) - i
                                                break
                                        
                                        if potential_start > 0:
                                            # Send everything before the potential match
                                            await call_callback(on_chunk, display_buffer[:potential_start])
                                            display_buffer = display_buffer[potential_start:]
                                        elif potential_start == -1:
                                            # No potential match, send everything
                                            if display_buffer:
                                                await call_callback(on_chunk, display_buffer)
                                            display_buffer = ""
                                        break
                                    elif start_idx > 0:
                                        # Send content before tool call
                                        await call_callback(on_chunk, display_buffer[:start_idx])
                                        display_buffer = display_buffer[start_idx:]
                                        in_tool_call = True
                                    else:
                                        # Tool call starts at beginning
                                        in_tool_call = True
                                        continue
                        else:
                            # Native tools or no tools - send directly
                            await call_callback(on_chunk, content)
                
                # Keep the last message for tool_calls
                if chunk.get("done", False):
                    final_message = message
            
            # Flush any remaining non-tool-call content
            if use_prompt_tools and on_chunk and display_buffer and not in_tool_call:
                # Clean any tool-call-related content from remaining buffer
                cleaned_buffer = strip_tool_calls_from_text(display_buffer)
                if cleaned_buffer:
                    await call_callback(on_chunk, cleaned_buffer)
            
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
        self._ensure_client()
        response = await self._async_client.embed(
            model=model or self.model,
            input=text,
        )
        
        embeddings = response.get("embeddings", [[]])
        return embeddings[0] if embeddings else []
