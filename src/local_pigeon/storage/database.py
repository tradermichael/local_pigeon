"""
Database Module

SQLite database for local storage.
"""

import sqlite3
import aiosqlite
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager


class Database:
    """
    SQLite database wrapper with async support.
    
    Handles:
    - Connection management
    - Schema initialization
    - Migration support
    """
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._ensure_directory()
    
    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    @asynccontextmanager
    async def connection(self):
        """Get an async database connection."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db
    
    async def initialize(self) -> None:
        """Initialize database schema."""
        async with self.connection() as db:
            # Check schema version
            await db.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                )
            """)
            
            cursor = await db.execute("SELECT version FROM schema_version LIMIT 1")
            row = await cursor.fetchone()
            current_version = row["version"] if row else 0
            
            if current_version < self.SCHEMA_VERSION:
                await self._migrate(db, current_version)
            
            await db.commit()
    
    async def _migrate(self, db: aiosqlite.Connection, from_version: int) -> None:
        """Run database migrations."""
        if from_version < 1:
            # Initial schema
            await db.executescript("""
                -- Conversations table
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_conversations_user 
                ON conversations(user_id, platform);
                
                -- Messages table
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_calls TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE
                );
                
                CREATE INDEX IF NOT EXISTS idx_messages_conversation 
                ON messages(conversation_id);
                
                -- User credentials table (encrypted tokens)
                CREATE TABLE IF NOT EXISTS credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    service TEXT NOT NULL,
                    encrypted_data BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, service)
                );
                
                CREATE INDEX IF NOT EXISTS idx_credentials_user 
                ON credentials(user_id);
                
                -- User settings table
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    settings TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Tool executions (audit log)
                CREATE TABLE IF NOT EXISTS tool_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments TEXT,
                    result TEXT,
                    success BOOLEAN NOT NULL,
                    execution_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_tool_executions_user 
                ON tool_executions(user_id);
                
                -- Payment approvals table
                CREATE TABLE IF NOT EXISTS payment_approvals (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_payment_approvals_user 
                ON payment_approvals(user_id);
                
                -- Update schema version
                INSERT OR REPLACE INTO schema_version (version) VALUES (1);
            """)
    
    async def execute(
        self,
        query: str,
        params: tuple = (),
    ) -> list[dict[str, Any]]:
        """Execute a query and return results as dicts."""
        async with self.connection() as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def execute_insert(
        self,
        query: str,
        params: tuple = (),
    ) -> int:
        """Execute an insert and return the last row ID."""
        async with self.connection() as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor.lastrowid or 0
    
    async def execute_many(
        self,
        query: str,
        params_list: list[tuple],
    ) -> None:
        """Execute a query with multiple parameter sets."""
        async with self.connection() as db:
            await db.executemany(query, params_list)
            await db.commit()
    
    async def log_tool_execution(
        self,
        user_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None,
        result: str | None,
        success: bool,
        execution_time_ms: int,
    ) -> None:
        """Log a tool execution for audit purposes."""
        import json
        
        await self.execute_insert(
            """
            INSERT INTO tool_executions 
            (user_id, tool_name, arguments, result, success, execution_time_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                tool_name,
                json.dumps(arguments) if arguments else None,
                result[:10000] if result else None,  # Truncate long results
                success,
                execution_time_ms,
            ),
        )
    
    async def log_payment_approval(
        self,
        approval_id: str,
        user_id: str,
        tool_name: str,
        amount: float,
        description: str,
        status: str = "pending",
    ) -> None:
        """Log a payment approval request."""
        await self.execute_insert(
            """
            INSERT INTO payment_approvals 
            (id, user_id, tool_name, amount, description, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (approval_id, user_id, tool_name, amount, description, status),
        )
    
    async def update_payment_approval(
        self,
        approval_id: str,
        status: str,
    ) -> None:
        """Update a payment approval status."""
        async with self.connection() as db:
            await db.execute(
                """
                UPDATE payment_approvals 
                SET status = ?, resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, approval_id),
            )
            await db.commit()
