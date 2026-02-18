"""Core dependency injection interfaces for pluggable providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from local_pigeon.storage.memory import AsyncMemoryManager, MemoryType


class MemoryProvider(ABC):
    """Abstract memory provider for context persistence and retrieval."""

    @abstractmethod
    async def save_context(
        self,
        user_id: str,
        key: str,
        text: str,
        memory_type: str = "fact",
        source: str = "agent",
    ) -> None:
        """Save contextual memory for a user."""

    @abstractmethod
    async def retrieve_context(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant context for a user query."""

    @abstractmethod
    async def format_context_for_prompt(self, user_id: str) -> str:
        """Return memory context text suitable for prompt injection."""

    @abstractmethod
    def get_native_manager(self) -> Any | None:
        """Return underlying native manager object, if available."""


class NetworkProvider(ABC):
    """Abstract network provider for mesh/federation connectivity."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to network/mesh resources."""

    @abstractmethod
    async def listen(self) -> None:
        """Start listening for incoming network events/messages."""


class ToolProvider(ABC):
    """Abstraction for providing tool implementations to the agent."""

    @abstractmethod
    def get_tools(self, agent: Any) -> list[Any]:
        """Return default tools for the given agent instance."""

    async def get_mcp_tools(self, agent: Any) -> tuple[Any | None, list[Any]]:
        """Return (mcp_manager, tools) for MCP integrations."""
        return None, []

    def get_discord_tools(self, agent: Any, bot: Any) -> list[Any]:
        """Return Discord-specific tools bound to a bot instance."""
        return []


class LocalDiskMemoryProvider(MemoryProvider):
    """Default local memory provider backed by AsyncMemoryManager."""

    def __init__(self, db_path: str):
        self._manager = AsyncMemoryManager(db_path=db_path)

    async def save_context(
        self,
        user_id: str,
        key: str,
        text: str,
        memory_type: str = "fact",
        source: str = "agent",
    ) -> None:
        try:
            mem_type = MemoryType(memory_type)
        except Exception:
            mem_type = MemoryType.FACT

        await self._manager.set_memory(
            user_id=user_id,
            key=key,
            value=text,
            memory_type=mem_type,
            source=source,
        )

    async def retrieve_context(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        memories = await self._manager.search_memories(
            user_id=user_id,
            query=query,
            limit=limit,
        )
        return [
            {
                "key": m.key,
                "value": m.value,
                "memory_type": m.memory_type.value,
                "source": m.source,
            }
            for m in memories
        ]

    async def format_context_for_prompt(self, user_id: str) -> str:
        return await self._manager.format_memories_for_prompt(user_id)

    def get_native_manager(self) -> AsyncMemoryManager | None:
        return self._manager
