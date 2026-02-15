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

IMPORTANT RULES:
1. Only use tools when you need external information or actions to answer the user's question
2. You can make multiple tool calls by including multiple <tool_call> blocks
3. After you receive tool results, analyze them and either:
   - Use another tool if you need more information
   - Provide your FINAL ANSWER to the user (without any <tool_call> tags)
4. If no tool is needed, respond directly without any <tool_call> tags
5. NEVER include raw <tool_call> tags in your final answer to the user
6. When you have all the information you need, give a complete, helpful response

Remember: Your response either contains <tool_call> blocks (and I will execute them), OR it's a final answer to the user. Never mix them.
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
                                                on_chunk(display_buffer[:json_match.start()])
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
                                            on_chunk(display_buffer[:potential_start])
                                            display_buffer = display_buffer[potential_start:]
                                        elif potential_start == -1:
                                            # No potential match, send everything
                                            if display_buffer:
                                                on_chunk(display_buffer)
                                            display_buffer = ""
                                        break
                                    elif start_idx > 0:
                                        # Send content before tool call
                                        on_chunk(display_buffer[:start_idx])
                                        display_buffer = display_buffer[start_idx:]
                                        in_tool_call = True
                                    else:
                                        # Tool call starts at beginning
                                        in_tool_call = True
                                        continue
                        else:
                            # Native tools or no tools - send directly
                            on_chunk(content)
                
                # Keep the last message for tool_calls
                if chunk.get("done", False):
                    final_message = message
            
            # Flush any remaining non-tool-call content
            if use_prompt_tools and on_chunk and display_buffer and not in_tool_call:
                # Clean any tool-call-related content from remaining buffer
                cleaned_buffer = strip_tool_calls_from_text(display_buffer)
                if cleaned_buffer:
                    on_chunk(cleaned_buffer)
            
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
