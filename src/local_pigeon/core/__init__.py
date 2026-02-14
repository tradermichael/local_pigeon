"""
Local Pigeon Core Module

Contains the agent, LLM client, and conversation management.
"""

from local_pigeon.core.agent import LocalPigeonAgent
from local_pigeon.core.llm_client import OllamaClient
from local_pigeon.core.conversation import ConversationManager

__all__ = ["LocalPigeonAgent", "OllamaClient", "ConversationManager"]
