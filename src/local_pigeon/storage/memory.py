"""
User Memory Storage

Manages long-term memory about users including:
- Core memories (name, location, preferences)
- Learned facts and preferences
- Interaction patterns
- Custom user-defined memories

Uses SQLite for persistence with optional vector search for semantic retrieval.
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import aiosqlite


class MemoryType(str, Enum):
    """Types of user memories."""
    CORE = "core"           # Essential info: name, location, timezone
    PREFERENCE = "preference"  # User preferences: tone, formality, topics
    FACT = "fact"           # Learned facts about the user
    CONTEXT = "context"     # Contextual info: work, projects, goals
    RELATIONSHIP = "relationship"  # Relationships with other people/entities
    CUSTOM = "custom"       # User-defined memories


@dataclass
class Memory:
    """A single memory entry."""
    id: int | None = None
    user_id: str = ""
    memory_type: MemoryType = MemoryType.FACT
    key: str = ""           # Memory key (e.g., "name", "favorite_color")
    value: str = ""         # Memory content
    confidence: float = 1.0  # How confident we are (0-1)
    source: str = "user"    # Where it came from: user, inferred, conversation
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type.value,
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_row(cls, row: dict) -> "Memory":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            memory_type=MemoryType(row["memory_type"]),
            key=row["key"],
            value=row["value"],
            confidence=row.get("confidence", 1.0),
            source=row.get("source", "user"),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
            metadata=json.loads(row.get("metadata") or "{}"),
        )


# Default core memories to collect during onboarding
ONBOARDING_MEMORIES = [
    {"key": "name", "type": MemoryType.CORE, "prompt": "What's your name?", "required": True},
    {"key": "location", "type": MemoryType.CORE, "prompt": "Where are you located? (city/region)", "required": False},
    {"key": "timezone", "type": MemoryType.CORE, "prompt": "What timezone are you in?", "required": False},
    {"key": "preferred_name", "type": MemoryType.PREFERENCE, "prompt": "What should I call you?", "required": False},
    {"key": "tone", "type": MemoryType.PREFERENCE, "prompt": "How would you like me to communicate? (casual/professional/friendly)", "required": False},
    {"key": "verbosity", "type": MemoryType.PREFERENCE, "prompt": "Do you prefer brief or detailed responses?", "required": False},
]


class MemoryManager:
    """
    Synchronous memory manager for user memories.
    """
    
    def __init__(self, db_path: str | Path = "local_pigeon.db"):
        self.db_path = Path(db_path)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize memory tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS user_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    UNIQUE(user_id, memory_type, key)
                );
                
                CREATE INDEX IF NOT EXISTS idx_memories_user 
                    ON user_memories(user_id);
                CREATE INDEX IF NOT EXISTS idx_memories_type 
                    ON user_memories(user_id, memory_type);
            """)
            conn.commit()
    
    def set_memory(
        self,
        user_id: str,
        key: str,
        value: str,
        memory_type: MemoryType = MemoryType.FACT,
        confidence: float = 1.0,
        source: str = "user",
        metadata: dict | None = None,
    ) -> Memory:
        """Set or update a memory."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            now = datetime.now().isoformat()
            
            conn.execute(
                """
                INSERT INTO user_memories (user_id, memory_type, key, value, confidence, source, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, memory_type, key) 
                DO UPDATE SET value=excluded.value, confidence=excluded.confidence, 
                              source=excluded.source, metadata=excluded.metadata, updated_at=excluded.updated_at
                """,
                (user_id, memory_type.value, key, value, confidence, source, 
                 json.dumps(metadata or {}), now)
            )
            conn.commit()
            
            row = conn.execute(
                "SELECT * FROM user_memories WHERE user_id=? AND memory_type=? AND key=?",
                (user_id, memory_type.value, key)
            ).fetchone()
            
            return Memory.from_row(dict(row))
    
    def get_memory(
        self,
        user_id: str,
        key: str,
        memory_type: MemoryType | None = None,
    ) -> Memory | None:
        """Get a specific memory."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if memory_type:
                row = conn.execute(
                    "SELECT * FROM user_memories WHERE user_id=? AND memory_type=? AND key=?",
                    (user_id, memory_type.value, key)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM user_memories WHERE user_id=? AND key=?",
                    (user_id, key)
                ).fetchone()
            
            return Memory.from_row(dict(row)) if row else None
    
    def get_memories_by_type(
        self,
        user_id: str,
        memory_type: MemoryType,
    ) -> list[Memory]:
        """Get all memories of a specific type."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            rows = conn.execute(
                "SELECT * FROM user_memories WHERE user_id=? AND memory_type=? ORDER BY updated_at DESC",
                (user_id, memory_type.value)
            ).fetchall()
            
            return [Memory.from_row(dict(row)) for row in rows]
    
    def get_all_memories(self, user_id: str) -> list[Memory]:
        """Get all memories for a user."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            rows = conn.execute(
                "SELECT * FROM user_memories WHERE user_id=? ORDER BY memory_type, key",
                (user_id,)
            ).fetchall()
            
            return [Memory.from_row(dict(row)) for row in rows]
    
    def delete_memory(
        self,
        user_id: str,
        key: str,
        memory_type: MemoryType | None = None,
    ) -> bool:
        """Delete a memory."""
        with sqlite3.connect(self.db_path) as conn:
            if memory_type:
                cursor = conn.execute(
                    "DELETE FROM user_memories WHERE user_id=? AND memory_type=? AND key=?",
                    (user_id, memory_type.value, key)
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM user_memories WHERE user_id=? AND key=?",
                    (user_id, key)
                )
            conn.commit()
            return cursor.rowcount > 0
    
    def format_memories_for_prompt(self, user_id: str) -> str:
        """Format all memories as context for the LLM."""
        memories = self.get_all_memories(user_id)
        
        if not memories:
            return ""
        
        sections = {}
        for mem in memories:
            section = mem.memory_type.value.title()
            if section not in sections:
                sections[section] = []
            sections[section].append(f"- {mem.key}: {mem.value}")
        
        result = "\n\n## What I Know About You:\n"
        for section, items in sections.items():
            result += f"\n### {section}:\n" + "\n".join(items)
        
        return result
    
    def has_completed_onboarding(self, user_id: str) -> bool:
        """Check if user has completed onboarding."""
        # Check for essential core memory (name)
        name = self.get_memory(user_id, "name", MemoryType.CORE)
        return name is not None


class AsyncMemoryManager:
    """
    Async version of MemoryManager.
    """
    
    def __init__(self, db_path: str | Path = "local_pigeon.db"):
        self.db_path = Path(db_path)
        self._sync_manager = MemoryManager(db_path)
    
    async def set_memory(
        self,
        user_id: str,
        key: str,
        value: str,
        memory_type: MemoryType = MemoryType.FACT,
        confidence: float = 1.0,
        source: str = "user",
        metadata: dict | None = None,
    ) -> Memory:
        """Set or update a memory."""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now().isoformat()
            
            await db.execute(
                """
                INSERT INTO user_memories (user_id, memory_type, key, value, confidence, source, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, memory_type, key) 
                DO UPDATE SET value=excluded.value, confidence=excluded.confidence, 
                              source=excluded.source, metadata=excluded.metadata, updated_at=excluded.updated_at
                """,
                (user_id, memory_type.value, key, value, confidence, source, 
                 json.dumps(metadata or {}), now)
            )
            await db.commit()
            
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM user_memories WHERE user_id=? AND memory_type=? AND key=?",
                (user_id, memory_type.value, key)
            ) as cursor:
                row = await cursor.fetchone()
            
            return Memory.from_row(dict(row))
    
    async def get_memory(
        self,
        user_id: str,
        key: str,
        memory_type: MemoryType | None = None,
    ) -> Memory | None:
        """Get a specific memory."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if memory_type:
                async with db.execute(
                    "SELECT * FROM user_memories WHERE user_id=? AND memory_type=? AND key=?",
                    (user_id, memory_type.value, key)
                ) as cursor:
                    row = await cursor.fetchone()
            else:
                async with db.execute(
                    "SELECT * FROM user_memories WHERE user_id=? AND key=?",
                    (user_id, key)
                ) as cursor:
                    row = await cursor.fetchone()
            
            return Memory.from_row(dict(row)) if row else None
    
    async def get_memories_by_type(
        self,
        user_id: str,
        memory_type: MemoryType,
    ) -> list[Memory]:
        """Get all memories of a specific type."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute(
                "SELECT * FROM user_memories WHERE user_id=? AND memory_type=? ORDER BY updated_at DESC",
                (user_id, memory_type.value)
            ) as cursor:
                rows = await cursor.fetchall()
            
            return [Memory.from_row(dict(row)) for row in rows]
    
    async def get_all_memories(self, user_id: str) -> list[Memory]:
        """Get all memories for a user."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute(
                "SELECT * FROM user_memories WHERE user_id=? ORDER BY memory_type, key",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
            
            return [Memory.from_row(dict(row)) for row in rows]
    
    async def delete_memory(
        self,
        user_id: str,
        key: str,
        memory_type: MemoryType | None = None,
    ) -> bool:
        """Delete a memory."""
        async with aiosqlite.connect(self.db_path) as db:
            if memory_type:
                cursor = await db.execute(
                    "DELETE FROM user_memories WHERE user_id=? AND memory_type=? AND key=?",
                    (user_id, memory_type.value, key)
                )
            else:
                cursor = await db.execute(
                    "DELETE FROM user_memories WHERE user_id=? AND key=?",
                    (user_id, key)
                )
            await db.commit()
            return cursor.rowcount > 0
    
    async def format_memories_for_prompt(self, user_id: str) -> str:
        """Format all memories as context for the LLM."""
        memories = await self.get_all_memories(user_id)
        
        if not memories:
            return ""
        
        sections = {}
        for mem in memories:
            section = mem.memory_type.value.title()
            if section not in sections:
                sections[section] = []
            sections[section].append(f"- {mem.key}: {mem.value}")
        
        result = "\n\n## What I Know About You:\n"
        for section, items in sections.items():
            result += f"\n### {section}:\n" + "\n".join(items)
        
        return result
    
    async def has_completed_onboarding(self, user_id: str) -> bool:
        """Check if user has completed onboarding."""
        name = await self.get_memory(user_id, "name", MemoryType.CORE)
        return name is not None
