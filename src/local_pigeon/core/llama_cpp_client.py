"""
llama-cpp-python Backend

Alternative LLM backend using llama-cpp-python for running GGUF models
directly without requiring Ollama.

Features:
- Downloads models from HuggingFace
- Runs GGUF models locally
- Tool calling via prompt-based bridge
- Drop-in replacement for OllamaClient
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable
import asyncio

from local_pigeon.config import get_models_dir

# Lazy import to avoid requiring llama-cpp-python if not used
_llama_cpp = None


def _get_llama_cpp():
    """Lazy import llama-cpp-python."""
    global _llama_cpp
    if _llama_cpp is None:
        try:
            import llama_cpp
            _llama_cpp = llama_cpp
        except ImportError:
            raise ImportError(
                "llama-cpp-python is not installed. "
                "Install it with: pip install llama-cpp-python"
            )
    return _llama_cpp


# Default models available for download
AVAILABLE_MODELS = {
    "gemma-2-2b": {
        "repo": "bartowski/gemma-2-2b-it-GGUF",
        "file": "gemma-2-2b-it-Q4_K_M.gguf",
        "context_length": 8192,
        "description": "Google Gemma 2 2B - Fast and capable",
    },
    "phi-3-mini": {
        "repo": "microsoft/Phi-3-mini-4k-instruct-gguf",
        "file": "Phi-3-mini-4k-instruct-q4.gguf",
        "context_length": 4096,
        "description": "Microsoft Phi-3 Mini - Efficient reasoning",
    },
    "llama-3.2-3b": {
        "repo": "bartowski/Llama-3.2-3B-Instruct-GGUF",
        "file": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "context_length": 8192,
        "description": "Meta Llama 3.2 3B - Excellent all-rounder",
    },
    "qwen2.5-3b": {
        "repo": "Qwen/Qwen2.5-3B-Instruct-GGUF",
        "file": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "context_length": 8192,
        "description": "Alibaba Qwen 2.5 3B - Strong multilingual",
    },
    "mistral-7b": {
        "repo": "TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
        "file": "mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        "context_length": 8192,
        "description": "Mistral 7B - Powerful general model",
    },
}


# Tool calling prompt (same as OllamaClient)
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


@dataclass
class ToolCall:
    """Represents a tool call from the model."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    """A chat message."""
    role: str
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None

    def to_llama_cpp(self) -> dict[str, str]:
        """Convert to llama-cpp-python format."""
        return {"role": self.role, "content": self.content}


@dataclass
class ToolDefinition:
    """Definition of a tool."""
    name: str
    description: str
    parameters: dict[str, Any]


def parse_tool_calls_from_text(text: str) -> list[dict[str, Any]]:
    """Parse tool calls from model output."""
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
    """Remove tool call tags from text."""
    pattern = r'<tool_call>\s*\{.*?\}\s*</tool_call>'
    return re.sub(pattern, '', text, flags=re.DOTALL).strip()


def download_model(
    model_name: str,
    callback: Callable[[int, int], None] | None = None,
) -> Path:
    """
    Download a model from HuggingFace.
    
    Args:
        model_name: Key from AVAILABLE_MODELS or a HuggingFace repo/file path
        callback: Progress callback (bytes_downloaded, total_bytes)
    
    Returns:
        Path to the downloaded model file
    """
    models_dir = get_models_dir()
    
    if model_name in AVAILABLE_MODELS:
        model_info = AVAILABLE_MODELS[model_name]
        repo = model_info["repo"]
        filename = model_info["file"]
    elif "/" in model_name:
        # Assume it's a repo/filename format
        parts = model_name.rsplit("/", 1)
        if len(parts) == 2:
            repo, filename = parts
        else:
            raise ValueError(f"Invalid model format: {model_name}")
    else:
        raise ValueError(
            f"Unknown model: {model_name}. "
            f"Available: {list(AVAILABLE_MODELS.keys())}"
        )
    
    model_path = models_dir / filename
    
    if model_path.exists():
        return model_path
    
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise ImportError(
            "huggingface_hub is required for downloading models. "
            "Install with: pip install huggingface_hub"
        )
    
    print(f"Downloading {filename} from {repo}...")
    
    downloaded_path = hf_hub_download(
        repo_id=repo,
        filename=filename,
        local_dir=models_dir,
        local_dir_use_symlinks=False,
    )
    
    return Path(downloaded_path)


def list_downloaded_models() -> list[dict[str, Any]]:
    """List all downloaded models."""
    models_dir = get_models_dir()
    models = []
    
    for file in models_dir.glob("*.gguf"):
        # Try to match with known models
        model_info = None
        for name, info in AVAILABLE_MODELS.items():
            if info["file"] == file.name:
                model_info = {"name": name, **info}
                break
        
        if model_info:
            models.append({
                "name": model_info["name"],
                "file": file.name,
                "path": str(file),
                "size_mb": file.stat().st_size / (1024 * 1024),
                "description": model_info.get("description", ""),
            })
        else:
            models.append({
                "name": file.stem,
                "file": file.name,
                "path": str(file),
                "size_mb": file.stat().st_size / (1024 * 1024),
                "description": "Custom model",
            })
    
    return models


class LlamaCppClient:
    """
    Client for running GGUF models via llama-cpp-python.
    
    Drop-in compatible with OllamaClient for basic use cases.
    """
    
    def __init__(
        self,
        model_path: str | Path | None = None,
        model_name: str = "gemma-2-2b",
        temperature: float = 0.7,
        context_length: int = 4096,
        n_gpu_layers: int = -1,  # -1 = auto-detect
    ):
        self.model_path = model_path
        self.model_name = model_name
        self.temperature = temperature
        self.context_length = context_length
        self.n_gpu_layers = n_gpu_layers
        self._llm = None
        self._loaded_model_path: Path | None = None
    
    def _ensure_model_loaded(self) -> None:
        """Ensure the model is loaded."""
        if self.model_path:
            target_path = Path(self.model_path)
        elif self.model_name in AVAILABLE_MODELS:
            target_path = download_model(self.model_name)
        else:
            # Check if it's a local file
            models_dir = get_models_dir()
            local_path = models_dir / f"{self.model_name}.gguf"
            if local_path.exists():
                target_path = local_path
            else:
                raise ValueError(
                    f"Model not found: {self.model_name}. "
                    f"Run download first or provide model_path."
                )
        
        if self._llm is not None and self._loaded_model_path == target_path:
            return  # Already loaded
        
        llama_cpp = _get_llama_cpp()
        
        self._llm = llama_cpp.Llama(
            model_path=str(target_path),
            n_ctx=self.context_length,
            n_gpu_layers=self.n_gpu_layers,
            verbose=False,
        )
        self._loaded_model_path = target_path
    
    def _build_tool_prompt(self, tools: list[ToolDefinition]) -> str:
        """Build tool prompt for non-native tool calling."""
        descriptions = []
        for tool in tools:
            params_str = json.dumps(tool.parameters, indent=2)
            descriptions.append(
                f"**{tool.name}**: {tool.description}\nParameters: {params_str}"
            )
        return TOOL_SYSTEM_PROMPT.format(
            tool_descriptions="\n\n".join(descriptions)
        )
    
    def _add_tool_prompt(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> list[Message]:
        """Add tool instructions to messages."""
        tool_prompt = self._build_tool_prompt(tools)
        new_messages = []
        has_system = False
        
        for msg in messages:
            if msg.role == "system":
                new_content = tool_prompt + "\n\n" + msg.content
                new_messages.append(Message(role="system", content=new_content))
                has_system = True
            else:
                new_messages.append(msg)
        
        if not has_system:
            new_messages.insert(0, Message(role="system", content=tool_prompt))
        
        return new_messages
    
    def _parse_tool_response(self, message: Message) -> Message:
        """Parse tool calls from text response."""
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
            cleaned = strip_tool_calls_from_text(message.content)
            return Message(
                role=message.role,
                content=cleaned,
                tool_calls=tool_calls,
            )
        
        return message
    
    def list_models(self) -> list[dict[str, Any]]:
        """List available models."""
        downloaded = list_downloaded_models()
        
        # Add available models that aren't downloaded yet
        available = []
        for name, info in AVAILABLE_MODELS.items():
            if not any(m["name"] == name for m in downloaded):
                available.append({
                    "name": name,
                    "file": info["file"],
                    "downloaded": False,
                    "description": info["description"],
                })
        
        return [
            {**m, "downloaded": True} for m in downloaded
        ] + available
    
    async def achat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
    ) -> Message:
        """Send a chat completion request."""
        self._ensure_model_loaded()
        
        # Add tool prompt if tools provided
        if tools:
            messages = self._add_tool_prompt(messages, tools)
        
        llama_messages = [m.to_llama_cpp() for m in messages]
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._llm.create_chat_completion(
                messages=llama_messages,
                temperature=self.temperature,
                max_tokens=2048,
            )
        )
        
        content = response["choices"][0]["message"]["content"]
        result = Message(role="assistant", content=content)
        
        # Parse tool calls if tools were provided
        if tools:
            result = self._parse_tool_response(result)
        
        return result
    
    async def achat_stream_full(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> Message:
        """Send a streaming chat request."""
        self._ensure_model_loaded()
        
        # Add tool prompt if tools provided
        if tools:
            messages = self._add_tool_prompt(messages, tools)
        
        llama_messages = [m.to_llama_cpp() for m in messages]
        
        full_content = ""
        
        def generate():
            nonlocal full_content
            for chunk in self._llm.create_chat_completion(
                messages=llama_messages,
                temperature=self.temperature,
                max_tokens=2048,
                stream=True,
            ):
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_content += content
                    if on_chunk:
                        on_chunk(content)
            return full_content
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, generate)
        
        result = Message(role="assistant", content=full_content)
        
        if tools:
            result = self._parse_tool_response(result)
        
        return result
    
    def set_model(self, model_name: str) -> None:
        """Change the active model."""
        self.model_name = model_name
        self._llm = None  # Force reload on next use
        self._loaded_model_path = None


def is_available() -> bool:
    """Check if llama-cpp-python is available."""
    try:
        _get_llama_cpp()
        return True
    except ImportError:
        return False
