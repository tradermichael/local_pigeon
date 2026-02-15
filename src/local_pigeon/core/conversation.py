"""
Conversation Manager

Handles conversation history storage and retrieval using SQLite.
Supports multiple users and conversation threading.
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from local_pigeon.core.llm_client import Message, ToolCall


class ConversationManager:
    """
    Manages conversation history with SQLite storage.
    
    Supports:
    - Multiple users with separate conversation histories
    - Conversation sessions/threads
    - Message retrieval with limits
    - History pruning
    """
    
    def __init__(
        self,
        db_path: str | Path = "local_pigeon.db",
        max_history: int = 20,
    ):
        self.db_path = Path(db_path)
        self.max_history = max_history
        self._ensure_db()
    
    def _ensure_db(self) -> None:
        """Ensure the database and tables exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    platform TEXT DEFAULT 'cli',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                );
                
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_calls TEXT,
                    tool_call_id TEXT,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_conversations_user 
                    ON conversations(user_id);
                CREATE INDEX IF NOT EXISTS idx_conversations_session 
                    ON conversations(user_id, session_id);
                CREATE INDEX IF NOT EXISTS idx_messages_conversation 
                    ON messages(conversation_id);
            """)
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def get_or_create_conversation(
        self,
        user_id: str,
        session_id: str | None = None,
        platform: str = "cli",
    ) -> int:
        """
        Get or create a conversation for a user.
        
        Args:
            user_id: The user's identifier
            session_id: Optional session/thread identifier
            platform: Platform name (cli, discord, telegram, web)
            
        Returns:
            Conversation ID
        """
        with self._get_connection() as conn:
            # Try to find existing conversation
            if session_id:
                row = conn.execute(
                    """
                    SELECT id FROM conversations 
                    WHERE user_id = ? AND session_id = ?
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    (user_id, session_id)
                ).fetchone()
            else:
                # Get most recent conversation for user on this platform
                row = conn.execute(
                    """
                    SELECT id FROM conversations 
                    WHERE user_id = ? AND platform = ?
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    (user_id, platform)
                ).fetchone()
            
            if row:
                return row["id"]
            
            # Create new conversation
            cursor = conn.execute(
                """
                INSERT INTO conversations (user_id, session_id, platform)
                VALUES (?, ?, ?)
                """,
                (user_id, session_id, platform)
            )
            conn.commit()
            return cursor.lastrowid
    
    def add_message(
        self,
        conversation_id: int,
        message: Message,
    ) -> int:
        """
        Add a message to a conversation.
        
        Args:
            conversation_id: The conversation ID
            message: The message to add
            
        Returns:
            Message ID
        """
        tool_calls_json = None
        if message.tool_calls:
            tool_calls_json = json.dumps([
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                }
                for tc in message.tool_calls
            ])
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO messages (
                    conversation_id, role, content, 
                    tool_calls, tool_call_id, name
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    message.role,
                    message.content,
                    tool_calls_json,
                    message.tool_call_id,
                    message.name,
                )
            )
            
            # Update conversation timestamp
            conn.execute(
                """
                UPDATE conversations 
                SET updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
                """,
                (conversation_id,)
            )
            
            conn.commit()
            return cursor.lastrowid
    
    def get_messages(
        self,
        conversation_id: int,
        limit: int | None = None,
    ) -> list[Message]:
        """
        Get messages from a conversation.
        
        Args:
            conversation_id: The conversation ID
            limit: Maximum number of messages to return (most recent)
            
        Returns:
            List of messages
        """
        limit = limit or self.max_history
        
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT role, content, tool_calls, tool_call_id, name
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (conversation_id, limit)
            ).fetchall()
        
        messages = []
        for row in reversed(rows):  # Reverse to get chronological order
            tool_calls = []
            if row["tool_calls"]:
                for tc_data in json.loads(row["tool_calls"]):
                    tool_calls.append(ToolCall(
                        id=tc_data["id"],
                        name=tc_data["name"],
                        arguments=tc_data["arguments"],
                    ))
            
            messages.append(Message(
                role=row["role"],
                content=row["content"],
                tool_calls=tool_calls,
                tool_call_id=row["tool_call_id"],
                name=row["name"],
            ))
        
        return messages
    
    def clear_conversation(self, conversation_id: int) -> None:
        """Clear all messages from a conversation."""
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conversation_id,)
            )
            conn.commit()
    
    def delete_conversation(self, conversation_id: int) -> None:
        """Delete a conversation and all its messages."""
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conversation_id,)
            )
            conn.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation_id,)
            )
            conn.commit()
    
    def get_user_conversations(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get recent conversations for a user.
        
        Args:
            user_id: The user's identifier
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversation metadata
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT 
                    c.id,
                    c.session_id,
                    c.platform,
                    c.created_at,
                    c.updated_at,
                    COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (user_id, limit)
            ).fetchall()
        
        return [dict(row) for row in rows]
    
    def prune_old_messages(
        self,
        days: int = 90,
    ) -> int:
        """
        Delete messages older than specified days.
        
        Args:
            days: Age threshold in days
            
        Returns:
            Number of messages deleted
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM messages
                WHERE created_at < datetime('now', ?)
                """,
                (f"-{days} days",)
            )
            conn.commit()
            return cursor.rowcount


class AsyncConversationManager:
    """
    Async version of ConversationManager for use with async platforms.
    """
    
    def __init__(
        self,
        db_path: str | Path = "local_pigeon.db",
        max_history: int = 20,
    ):
        self.db_path = Path(db_path)
        self.max_history = max_history
        self._sync_manager = ConversationManager(db_path, max_history)
    
    async def get_or_create_conversation(
        self,
        user_id: str,
        session_id: str | None = None,
        platform: str = "cli",
    ) -> int:
        """Get or create a conversation for a user."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if session_id:
                async with db.execute(
                    """
                    SELECT id FROM conversations 
                    WHERE user_id = ? AND session_id = ?
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    (user_id, session_id)
                ) as cursor:
                    row = await cursor.fetchone()
            else:
                async with db.execute(
                    """
                    SELECT id FROM conversations 
                    WHERE user_id = ? AND platform = ?
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    (user_id, platform)
                ) as cursor:
                    row = await cursor.fetchone()
            
            if row:
                return row["id"]
            
            async with db.execute(
                """
                INSERT INTO conversations (user_id, session_id, platform)
                VALUES (?, ?, ?)
                """,
                (user_id, session_id, platform)
            ) as cursor:
                await db.commit()
                return cursor.lastrowid
    
    async def add_message(
        self,
        conversation_id: int,
        message: Message,
    ) -> int:
        """Add a message to a conversation."""
        tool_calls_json = None
        if message.tool_calls:
            tool_calls_json = json.dumps([
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                }
                for tc in message.tool_calls
            ])
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                INSERT INTO messages (
                    conversation_id, role, content, 
                    tool_calls, tool_call_id, name
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    message.role,
                    message.content,
                    tool_calls_json,
                    message.tool_call_id,
                    message.name,
                )
            ) as cursor:
                message_id = cursor.lastrowid
            
            await db.execute(
                """
                UPDATE conversations 
                SET updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
                """,
                (conversation_id,)
            )
            
            await db.commit()
            return message_id
    
    async def get_messages(
        self,
        conversation_id: int,
        limit: int | None = None,
    ) -> list[Message]:
        """Get messages from a conversation."""
        limit = limit or self.max_history
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute(
                """
                SELECT role, content, tool_calls, tool_call_id, name
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (conversation_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
        
        messages = []
        for row in reversed(rows):
            tool_calls = []
            if row["tool_calls"]:
                for tc_data in json.loads(row["tool_calls"]):
                    tool_calls.append(ToolCall(
                        id=tc_data["id"],
                        name=tc_data["name"],
                        arguments=tc_data["arguments"],
                    ))
            
            messages.append(Message(
                role=row["role"],
                content=row["content"],
                tool_calls=tool_calls,
                tool_call_id=row["tool_call_id"],
                name=row["name"],
            ))
        
        return messages
    
    async def clear_conversation(self, conversation_id: int) -> None:
        """Clear all messages from a conversation."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conversation_id,)
            )
            await db.commit()
    
    async def get_recent_activity(
        self,
        limit: int = 50,
        platforms: list[str] | None = None,
    ) -> list[dict]:
        """
        Get recent messages across all platforms for the activity log.
        
        Args:
            limit: Maximum number of messages to return
            platforms: Filter to specific platforms (None = all)
            
        Returns:
            List of message dicts with platform, user_id, timestamp, etc.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            if platforms:
                placeholders = ",".join("?" * len(platforms))
                query = f"""
                    SELECT 
                        m.id,
                        m.role,
                        m.content,
                        m.tool_calls,
                        m.name,
                        m.created_at,
                        c.user_id,
                        c.platform
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE c.platform IN ({placeholders})
                    ORDER BY m.created_at DESC
                    LIMIT ?
                """
                params = platforms + [limit]
            else:
                query = """
                    SELECT 
                        m.id,
                        m.role,
                        m.content,
                        m.tool_calls,
                        m.name,
                        m.created_at,
                        c.user_id,
                        c.platform
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    ORDER BY m.created_at DESC
                    LIMIT ?
                """
                params = [limit]
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
        
        return [
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"][:200] + "..." if len(row["content"] or "") > 200 else row["content"],
                "tool_calls": row["tool_calls"],
                "name": row["name"],
                "timestamp": row["created_at"],
                "user_id": row["user_id"],
                "platform": row["platform"],
            }
            for row in rows
        ]
