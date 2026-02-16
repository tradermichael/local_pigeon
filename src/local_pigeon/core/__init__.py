"""
Local Pigeon Core Module

Contains the agent, LLM client, and conversation management.
"""

# Import these lazily to avoid circular imports
# Users should import from the specific modules directly

__all__ = ["LocalPigeonAgent", "OllamaClient", "ConversationManager"]


def __getattr__(name: str):
    """Lazy imports to avoid circular imports."""
    if name == "LocalPigeonAgent":
        from local_pigeon.core.agent import LocalPigeonAgent
        return LocalPigeonAgent
    elif name == "OllamaClient":
        from local_pigeon.core.llm_client import OllamaClient
        return OllamaClient
    elif name == "ConversationManager":
        from local_pigeon.core.conversation import ConversationManager
        return ConversationManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
