"""
Model Catalog for Local Pigeon

Provides a curated inventory of popular models organized by category,
with support for both Ollama and llama-cpp-python (GGUF) backends.

Categories:
- Thinking/Reasoning: Models with Chain-of-Thought capabilities
- Vision: Models that can process images
- Coding: Optimized for code generation
- General: Well-rounded chat models
- Small/Fast: Lightweight models for quick responses
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ModelCategory(Enum):
    """Model capability categories."""
    THINKING = "thinking"      # Chain-of-thought reasoning
    VISION = "vision"          # Image understanding
    CODING = "coding"          # Code generation
    GENERAL = "general"        # Well-rounded chat
    SMALL = "small"            # Fast, lightweight
    MULTILINGUAL = "multilingual"  # Strong non-English support
    TOOL_CALLING = "tool_calling"  # Native function/tool calling support


class ModelBackend(Enum):
    """Supported model backends."""
    OLLAMA = "ollama"
    GGUF = "gguf"  # llama-cpp-python


@dataclass
class ModelInfo:
    """Information about a model in the catalog."""
    name: str                      # Display name
    ollama_name: str | None        # Ollama model name (e.g., "deepseek-r1:7b")
    gguf_repo: str | None          # HuggingFace repo for GGUF
    gguf_file: str | None          # GGUF filename
    description: str               # Short description
    categories: list[ModelCategory]  # Model capabilities
    size_label: str                # e.g., "7B", "32B"
    context_length: int = 8192     # Default context window
    recommended: bool = False      # Highlight as recommended
    
    @property
    def supports_ollama(self) -> bool:
        return self.ollama_name is not None
    
    @property
    def supports_gguf(self) -> bool:
        return self.gguf_repo is not None and self.gguf_file is not None


# =============================================================================
# MODEL CATALOG
# =============================================================================

MODEL_CATALOG: list[ModelInfo] = [
    # -------------------------------------------------------------------------
    # THINKING / REASONING MODELS (Chain-of-Thought)
    # -------------------------------------------------------------------------
    ModelInfo(
        name="DeepSeek R1 (7B)",
        ollama_name="deepseek-r1:7b",
        gguf_repo="bartowski/DeepSeek-R1-Distill-Qwen-7B-GGUF",
        gguf_file="DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
        description="DeepSeek's reasoning model - excellent for complex problems",
        categories=[ModelCategory.THINKING, ModelCategory.CODING],
        size_label="7B",
        context_length=32768,
        recommended=True,
    ),
    ModelInfo(
        name="DeepSeek R1 (14B)",
        ollama_name="deepseek-r1:14b",
        gguf_repo="bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF",
        gguf_file="DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf",
        description="Larger DeepSeek R1 - stronger reasoning",
        categories=[ModelCategory.THINKING, ModelCategory.CODING],
        size_label="14B",
        context_length=32768,
    ),
    ModelInfo(
        name="DeepSeek R1 (32B)",
        ollama_name="deepseek-r1:32b",
        gguf_repo="bartowski/DeepSeek-R1-Distill-Qwen-32B-GGUF",
        gguf_file="DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf",
        description="Most powerful DeepSeek R1 distill - near full R1 quality",
        categories=[ModelCategory.THINKING, ModelCategory.CODING],
        size_label="32B",
        context_length=32768,
    ),
    ModelInfo(
        name="Qwen 3 (8B)",
        ollama_name="qwen3:8b",
        gguf_repo="Qwen/Qwen3-8B-GGUF",
        gguf_file="qwen3-8b-q4_k_m.gguf",
        description="Alibaba Qwen 3 - supports thinking mode with /think",
        categories=[ModelCategory.THINKING, ModelCategory.GENERAL, ModelCategory.MULTILINGUAL],
        size_label="8B",
        context_length=32768,
        recommended=True,
    ),
    ModelInfo(
        name="Qwen 3 (14B)",
        ollama_name="qwen3:14b",
        gguf_repo="Qwen/Qwen3-14B-GGUF",
        gguf_file="qwen3-14b-q4_k_m.gguf",
        description="Larger Qwen 3 with stronger reasoning",
        categories=[ModelCategory.THINKING, ModelCategory.GENERAL, ModelCategory.MULTILINGUAL],
        size_label="14B",
        context_length=32768,
    ),
    ModelInfo(
        name="Qwen 3 (32B)",
        ollama_name="qwen3:32b",
        gguf_repo="Qwen/Qwen3-32B-GGUF",
        gguf_file="qwen3-32b-q4_k_m.gguf",
        description="Large Qwen 3 - excellent reasoning and multilingual",
        categories=[ModelCategory.THINKING, ModelCategory.GENERAL, ModelCategory.MULTILINGUAL],
        size_label="32B",
        context_length=32768,
    ),
    ModelInfo(
        name="Kimi K2 (Qwen3 8B Thinking)",
        ollama_name="mannix/kimi-k2-instruct:q4_k_m",
        gguf_repo=None,
        gguf_file=None,
        description="Moonshot's Kimi K2 - long-context thinking model",
        categories=[ModelCategory.THINKING, ModelCategory.GENERAL],
        size_label="8B",
        context_length=131072,
    ),

    # -------------------------------------------------------------------------
    # VISION MODELS
    # -------------------------------------------------------------------------
    ModelInfo(
        name="LLaVA 1.6 (7B)",
        ollama_name="llava:7b",
        gguf_repo="mys/ggml_llava-v1.6-mistral-7b",
        gguf_file="ggml-model-q4_k.gguf",
        description="Vision-language model - analyze images",
        categories=[ModelCategory.VISION, ModelCategory.GENERAL],
        size_label="7B",
        context_length=4096,
        recommended=True,
    ),
    ModelInfo(
        name="LLaVA 1.6 (13B)",
        ollama_name="llava:13b",
        gguf_repo="mys/ggml_llava-v1.6-34b",
        gguf_file="ggml-model-q4_k.gguf",
        description="Larger LLaVA with better image understanding",
        categories=[ModelCategory.VISION, ModelCategory.GENERAL],
        size_label="13B",
        context_length=4096,
    ),
    ModelInfo(
        name="Moondream 2",
        ollama_name="moondream:latest",
        gguf_repo="vikhyatk/moondream2",
        gguf_file="moondream2-text-model-f16.gguf",
        description="Tiny but capable vision model - fast image analysis",
        categories=[ModelCategory.VISION, ModelCategory.SMALL],
        size_label="1.8B",
        context_length=2048,
        recommended=True,
    ),
    ModelInfo(
        name="Llama 3.2 Vision (11B)",
        ollama_name="llama3.2-vision:11b",
        gguf_repo=None,
        gguf_file=None,
        description="Meta's latest vision model - excellent quality",
        categories=[ModelCategory.VISION, ModelCategory.GENERAL],
        size_label="11B",
        context_length=8192,
    ),
    ModelInfo(
        name="MiniCPM-V 2.6",
        ollama_name="minicpm-v:latest",
        gguf_repo=None,
        gguf_file=None,
        description="Efficient vision model with strong OCR",
        categories=[ModelCategory.VISION, ModelCategory.SMALL],
        size_label="8B",
        context_length=8192,
    ),

    # -------------------------------------------------------------------------
    # CODING MODELS
    # -------------------------------------------------------------------------
    ModelInfo(
        name="Qwen 2.5 Coder (7B)",
        ollama_name="qwen2.5-coder:7b",
        gguf_repo="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        gguf_file="qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        description="Alibaba's coding specialist - strong code generation",
        categories=[ModelCategory.CODING, ModelCategory.GENERAL],
        size_label="7B",
        context_length=32768,
        recommended=True,
    ),
    ModelInfo(
        name="Qwen 2.5 Coder (14B)",
        ollama_name="qwen2.5-coder:14b",
        gguf_repo="Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
        gguf_file="qwen2.5-coder-14b-instruct-q4_k_m.gguf",
        description="Larger Qwen coder for complex code tasks",
        categories=[ModelCategory.CODING, ModelCategory.GENERAL],
        size_label="14B",
        context_length=32768,
    ),
    ModelInfo(
        name="CodeLlama (7B)",
        ollama_name="codellama:7b",
        gguf_repo="TheBloke/CodeLlama-7B-Instruct-GGUF",
        gguf_file="codellama-7b-instruct.Q4_K_M.gguf",
        description="Meta's code-focused Llama variant",
        categories=[ModelCategory.CODING],
        size_label="7B",
        context_length=16384,
    ),
    ModelInfo(
        name="DeepSeek Coder V2 (16B)",
        ollama_name="deepseek-coder-v2:16b",
        gguf_repo=None,
        gguf_file=None,
        description="DeepSeek's coding model - MoE architecture",
        categories=[ModelCategory.CODING, ModelCategory.GENERAL],
        size_label="16B",
        context_length=32768,
    ),

    # -------------------------------------------------------------------------
    # GENERAL PURPOSE MODELS
    # -------------------------------------------------------------------------
    ModelInfo(
        name="Llama 3.1 (8B) ⭐ Best for Tools",
        ollama_name="llama3.1:8b",
        gguf_repo="bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        gguf_file="Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        description="Meta's most tool-capable model - excellent function calling",
        categories=[ModelCategory.GENERAL, ModelCategory.TOOL_CALLING],
        size_label="8B",
        context_length=131072,
        recommended=True,
    ),
    ModelInfo(
        name="Llama 3.1 (70B)",
        ollama_name="llama3.1:70b",
        gguf_repo=None,
        gguf_file=None,
        description="Large Llama 3.1 - powerful with native tools",
        categories=[ModelCategory.GENERAL, ModelCategory.TOOL_CALLING, ModelCategory.THINKING],
        size_label="70B",
        context_length=131072,
    ),
    ModelInfo(
        name="Llama 3.2 (3B)",
        ollama_name="llama3.2:3b",
        gguf_repo="bartowski/Llama-3.2-3B-Instruct-GGUF",
        gguf_file="Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        description="Meta's efficient model - great balance of speed/quality",
        categories=[ModelCategory.GENERAL, ModelCategory.SMALL, ModelCategory.TOOL_CALLING],
        size_label="3B",
        context_length=8192,
        recommended=True,
    ),
    ModelInfo(
        name="Llama 3.1 (8B)",
        ollama_name="llama3.1:8b",
        gguf_repo="bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        gguf_file="Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        description="Solid 8B model from Meta with 128K context",
        categories=[ModelCategory.GENERAL, ModelCategory.TOOL_CALLING],
        size_label="8B",
        context_length=131072,
    ),
    ModelInfo(
        name="Gemma 3 (4B)",
        ollama_name="gemma3:4b",
        gguf_repo=None,
        gguf_file=None,
        description="Google's latest Gemma - efficient and capable",
        categories=[ModelCategory.GENERAL, ModelCategory.SMALL],
        size_label="4B",
        context_length=8192,
        recommended=True,
    ),
    ModelInfo(
        name="Gemma 3 (12B)",
        ollama_name="gemma3:12b",
        gguf_repo=None,
        gguf_file=None,
        description="Larger Gemma 3 with better reasoning",
        categories=[ModelCategory.GENERAL],
        size_label="12B",
        context_length=8192,
    ),
    ModelInfo(
        name="Gemma 3 (27B)",
        ollama_name="gemma3:27b",
        gguf_repo=None,
        gguf_file=None,
        description="Largest Gemma 3 - strong performance",
        categories=[ModelCategory.GENERAL, ModelCategory.THINKING],
        size_label="27B",
        context_length=8192,
    ),
    ModelInfo(
        name="Llama 3.2 (1B)",
        ollama_name="llama3.2:1b",
        gguf_repo="bartowski/Llama-3.2-1B-Instruct-GGUF",
        gguf_file="Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        description="Tiny Llama - ultra fast responses",
        categories=[ModelCategory.GENERAL, ModelCategory.SMALL, ModelCategory.TOOL_CALLING],
        size_label="1B",
        context_length=8192,
    ),
    ModelInfo(
        name="Mistral (7B)",
        ollama_name="mistral:7b",
        gguf_repo="TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
        gguf_file="mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        description="Classic efficient model - reliable tool support",
        categories=[ModelCategory.GENERAL, ModelCategory.TOOL_CALLING],
        size_label="7B",
        context_length=8192,
    ),
    ModelInfo(
        name="Phi-3 Medium (14B)",
        ollama_name="phi3:14b",
        gguf_repo="microsoft/Phi-3-medium-4k-instruct-gguf",
        gguf_file="Phi-3-medium-4k-instruct-q4.gguf",
        description="Microsoft's reasoning-focused model",
        categories=[ModelCategory.GENERAL, ModelCategory.THINKING],
        size_label="14B",
        context_length=4096,
    ),

    # -------------------------------------------------------------------------
    # SMALL / FAST MODELS
    # -------------------------------------------------------------------------
    ModelInfo(
        name="Qwen 2.5 (0.5B)",
        ollama_name="qwen2.5:0.5b",
        gguf_repo="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        gguf_file="qwen2.5-0.5b-instruct-q8_0.gguf",
        description="Tiny model - instant responses, basic tasks",
        categories=[ModelCategory.SMALL],
        size_label="0.5B",
        context_length=8192,
    ),
    ModelInfo(
        name="Qwen 2.5 (1.5B)",
        ollama_name="qwen2.5:1.5b",
        gguf_repo="Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        gguf_file="qwen2.5-1.5b-instruct-q4_k_m.gguf",
        description="Very fast model - good for simple tasks",
        categories=[ModelCategory.SMALL, ModelCategory.GENERAL],
        size_label="1.5B",
        context_length=8192,
        recommended=True,
    ),
    ModelInfo(
        name="Qwen 2.5 (3B)",
        ollama_name="qwen2.5:3b",
        gguf_repo="Qwen/Qwen2.5-3B-Instruct-GGUF",
        gguf_file="qwen2.5-3b-instruct-q4_k_m.gguf",
        description="Quick and capable - nice balance",
        categories=[ModelCategory.SMALL, ModelCategory.GENERAL, ModelCategory.MULTILINGUAL],
        size_label="3B",
        context_length=8192,
    ),
    ModelInfo(
        name="Phi-3 Mini (3.8B)",
        ollama_name="phi3:mini",
        gguf_repo="microsoft/Phi-3-mini-4k-instruct-gguf",
        gguf_file="Phi-3-mini-4k-instruct-q4.gguf",
        description="Microsoft's efficient small model",
        categories=[ModelCategory.SMALL, ModelCategory.GENERAL],
        size_label="3.8B",
        context_length=4096,
    ),
    ModelInfo(
        name="Gemma 2 (2B)",
        ollama_name="gemma2:2b",
        gguf_repo="bartowski/gemma-2-2b-it-GGUF",
        gguf_file="gemma-2-2b-it-Q4_K_M.gguf",
        description="Google's tiny model - fast responses",
        categories=[ModelCategory.SMALL],
        size_label="2B",
        context_length=8192,
    ),
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_models_by_category(category: ModelCategory) -> list[ModelInfo]:
    """Get all models in a specific category."""
    return [m for m in MODEL_CATALOG if category in m.categories]


def get_recommended_models() -> list[ModelInfo]:
    """Get models marked as recommended."""
    return [m for m in MODEL_CATALOG if m.recommended]


def get_thinking_models() -> list[ModelInfo]:
    """Get models with Chain-of-Thought/reasoning capabilities."""
    return get_models_by_category(ModelCategory.THINKING)


def get_vision_models() -> list[ModelInfo]:
    """Get models that can process images."""
    return get_models_by_category(ModelCategory.VISION)


def get_coding_models() -> list[ModelInfo]:
    """Get models optimized for code."""
    return get_models_by_category(ModelCategory.CODING)


def get_small_models() -> list[ModelInfo]:
    """Get lightweight/fast models."""
    return get_models_by_category(ModelCategory.SMALL)


def get_tool_calling_models() -> list[ModelInfo]:
    """Get models with native tool/function calling support."""
    return get_models_by_category(ModelCategory.TOOL_CALLING)


def _parse_size_to_b(size_label: str) -> float:
    """Parse size label like '7B', '1.8B', '70B' to numeric billions."""
    import re
    match = re.search(r'([\d.]+)\s*B', size_label, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return 999  # Unknown size treated as large


def get_starter_pack_recommendations(max_size_b: float = 11.0) -> dict[str, list[ModelInfo]]:
    """
    Get recommended starter models (11B or below) for each category.
    
    Returns dict with keys: 'vision', 'thinking', 'tool_calling', 'coding'
    Each contains up to 4 recommended models sorted by quality/popularity.
    """
    def filter_by_size(models: list[ModelInfo]) -> list[ModelInfo]:
        return [m for m in models if _parse_size_to_b(m.size_label) <= max_size_b]
    
    # Vision models ≤11B (prioritize recommended, then by size)
    vision = filter_by_size(get_vision_models())
    vision_sorted = sorted(vision, key=lambda m: (not m.recommended, _parse_size_to_b(m.size_label)))
    
    # Thinking models ≤11B
    thinking = filter_by_size(get_thinking_models())
    thinking_sorted = sorted(thinking, key=lambda m: (not m.recommended, _parse_size_to_b(m.size_label)))
    
    # Tool calling models ≤11B
    tools = filter_by_size(get_tool_calling_models())
    tools_sorted = sorted(tools, key=lambda m: (not m.recommended, _parse_size_to_b(m.size_label)))
    
    # Coding models ≤11B
    coding = filter_by_size(get_coding_models())
    coding_sorted = sorted(coding, key=lambda m: (not m.recommended, _parse_size_to_b(m.size_label)))
    
    return {
        'vision': vision_sorted[:4],
        'thinking': thinking_sorted[:4],
        'tool_calling': tools_sorted[:4],
        'coding': coding_sorted[:4],
    }


def format_starter_pack_for_display() -> str:
    """Format starter pack as markdown for UI display."""
    recs = get_starter_pack_recommendations()
    
    lines = [
        "## 🚀 Recommended Starter Pack (11B or smaller)",
        "",
        "These models are optimized for consumer hardware (8-16GB RAM) and offer the best balance of quality and speed.",
        "",
        "### 🔧 Tool Calling (Required for Agent)",
        "| Model | Size | Description |",
        "|-------|------|-------------|",
    ]
    for m in recs['tool_calling']:
        star = "⭐ " if m.recommended else ""
        lines.append(f"| {star}{m.ollama_name} | {m.size_label} | {m.description} |")
    
    lines.extend([
        "",
        "### 🖼️ Vision (For Image Analysis)",
        "| Model | Size | Description |",
        "|-------|------|-------------|",
    ])
    for m in recs['vision']:
        star = "⭐ " if m.recommended else ""
        lines.append(f"| {star}{m.ollama_name} | {m.size_label} | {m.description} |")
    
    lines.extend([
        "",
        "### 🧠 Thinking/Reasoning",
        "| Model | Size | Description |",
        "|-------|------|-------------|",
    ])
    for m in recs['thinking']:
        star = "⭐ " if m.recommended else ""
        lines.append(f"| {star}{m.ollama_name} | {m.size_label} | {m.description} |")
    
    lines.extend([
        "",
        "### 💻 Coding",
        "| Model | Size | Description |",
        "|-------|------|-------------|",
    ])
    for m in recs['coding']:
        star = "⭐ " if m.recommended else ""
        lines.append(f"| {star}{m.ollama_name} | {m.size_label} | {m.description} |")
    
    return "\n".join(lines)


def get_ollama_models() -> list[ModelInfo]:
    """Get models available via Ollama."""
    return [m for m in MODEL_CATALOG if m.supports_ollama]


def get_gguf_models() -> list[ModelInfo]:
    """Get models available as GGUF for llama-cpp-python."""
    return [m for m in MODEL_CATALOG if m.supports_gguf]


def find_model(name: str) -> ModelInfo | None:
    """Find a model by name (case-insensitive partial match)."""
    name_lower = name.lower()
    for model in MODEL_CATALOG:
        if name_lower in model.name.lower() or \
           (model.ollama_name and name_lower in model.ollama_name.lower()):
            return model
    return None


def format_catalog_for_display() -> list[list[str]]:
    """
    Format the catalog as a list of rows for UI display.
    
    Returns:
        List of [Name, Size, Categories, Backend, Description] rows
    """
    rows = []
    for model in MODEL_CATALOG:
        # Format categories with emojis
        cat_emojis = {
            ModelCategory.THINKING: "🧠",
            ModelCategory.VISION: "🖼️",
            ModelCategory.CODING: "💻",
            ModelCategory.GENERAL: "💬",
            ModelCategory.SMALL: "⚡",
            ModelCategory.MULTILINGUAL: "🌍",
            ModelCategory.TOOL_CALLING: "🔧",
        }
        categories = " ".join(cat_emojis.get(c, "") for c in model.categories)
        
        # Backend availability
        backends = []
        if model.supports_ollama:
            backends.append("Ollama")
        if model.supports_gguf:
            backends.append("GGUF")
        backend_str = " / ".join(backends)
        
        # Recommended indicator
        name = f"⭐ {model.name}" if model.recommended else model.name
        
        rows.append([
            name,
            model.size_label,
            categories,
            backend_str,
            model.description,
        ])
    
    return rows


def get_install_command(model: ModelInfo, backend: str = "ollama") -> str | None:
    """
    Get the install command for a model.
    
    Args:
        model: The model info
        backend: "ollama" or "gguf"
    
    Returns:
        Install command string or None if not available
    """
    if backend == "ollama" and model.ollama_name:
        return f"ollama pull {model.ollama_name}"
    elif backend == "gguf" and model.gguf_repo:
        return f"pip install llama-cpp-python huggingface_hub\n# Then download: {model.gguf_repo}/{model.gguf_file}"
    return None
