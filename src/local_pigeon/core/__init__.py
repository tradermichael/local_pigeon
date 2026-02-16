"""
Local Pigeon Core Module

Contains the agent, LLM client, and conversation management.
"""

# Import these lazily to avoid circular imports
# Users should import from the specific modules directly

__all__ = [
    "LocalPigeonAgent",
    "OllamaClient",
    "ConversationManager",
    "StatusEvent",
    "StatusType",
]


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
    elif name == "StatusEvent":
        from local_pigeon.core.agent import StatusEvent
        return StatusEvent
    elif name == "StatusType":
        from local_pigeon.core.agent import StatusType
        return StatusType
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
