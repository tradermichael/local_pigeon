"""
Failure Domain Logger

Tracks tool execution failures for the Ralph Loop pattern.
Enables:
- Pattern recognition of common failures
- Self-healing by allowing the model to read failure logs
- Engineering insights to fix recurring issues
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class FailureRecord:
    """A single failure record."""
    
    id: int | None
    timestamp: str
    tool_name: str
    error_type: str
    error_message: str
    arguments: dict[str, Any]
    user_id: str
    platform: str
    resolved: bool = False
    resolution_notes: str | None = None
    occurrence_count: int = 1


class FailureLog:
    """
    Tracks and analyzes tool execution failures.
    
    Implements the Ralph Loop principle of tracking failure domains
    so they can be fixed and never happen again.
    """
    
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the failure log database."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                arguments TEXT NOT NULL,
                user_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                resolved INTEGER DEFAULT 0,
                resolution_notes TEXT,
                occurrence_count INTEGER DEFAULT 1
            )
        """)
        
        # Index for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool_name ON failures(tool_name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_error_type ON failures(error_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_resolved ON failures(resolved)
        """)
        
        conn.commit()
        conn.close()
    
    def log_failure(
        self,
        tool_name: str,
        error: Exception | str,
        arguments: dict[str, Any],
        user_id: str,
        platform: str = "unknown",
    ) -> int:
        """
        Log a tool execution failure.
        
        If a similar failure exists (same tool + error type), increment count.
        Otherwise, create a new record.
        
        Returns:
            The failure record ID
        """
        error_type = type(error).__name__ if isinstance(error, Exception) else "Error"
        error_message = str(error)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check for existing similar failure
        cursor.execute("""
            SELECT id, occurrence_count FROM failures
            WHERE tool_name = ? AND error_type = ? AND resolved = 0
            ORDER BY timestamp DESC LIMIT 1
        """, (tool_name, error_type))
        
        existing = cursor.fetchone()
        
        if existing:
            # Increment occurrence count
            failure_id, count = existing
            cursor.execute("""
                UPDATE failures
                SET occurrence_count = ?, timestamp = ?, error_message = ?
                WHERE id = ?
            """, (count + 1, datetime.utcnow().isoformat(), error_message, failure_id))
        else:
            # Create new record
            cursor.execute("""
                INSERT INTO failures (timestamp, tool_name, error_type, error_message, arguments, user_id, platform)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat(),
                tool_name,
                error_type,
                error_message,
                json.dumps(arguments),
                user_id,
                platform,
            ))
            failure_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return failure_id
    
    def get_recent_failures(
        self,
        limit: int = 10,
        unresolved_only: bool = True,
    ) -> list[FailureRecord]:
        """Get recent failure records."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM failures"
        if unresolved_only:
            query += " WHERE resolved = 0"
        query += " ORDER BY timestamp DESC LIMIT ?"
        
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_record(row) for row in rows]
    
    def get_failures_by_tool(self, tool_name: str) -> list[FailureRecord]:
        """Get all failures for a specific tool."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM failures
            WHERE tool_name = ?
            ORDER BY occurrence_count DESC, timestamp DESC
        """, (tool_name,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_record(row) for row in rows]
    
    def get_failure_summary(self) -> dict[str, Any]:
        """
        Get a summary of failures for analysis.
        
        Returns statistics useful for identifying patterns.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total counts
        cursor.execute("SELECT COUNT(*) FROM failures WHERE resolved = 0")
        unresolved = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM failures WHERE resolved = 1")
        resolved = cursor.fetchone()[0]
        
        # Top failing tools
        cursor.execute("""
            SELECT tool_name, SUM(occurrence_count) as total
            FROM failures WHERE resolved = 0
            GROUP BY tool_name ORDER BY total DESC LIMIT 5
        """)
        top_failing_tools = [{"tool": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        # Most common error types
        cursor.execute("""
            SELECT error_type, COUNT(*) as count
            FROM failures WHERE resolved = 0
            GROUP BY error_type ORDER BY count DESC LIMIT 5
        """)
        common_errors = [{"type": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "unresolved_count": unresolved,
            "resolved_count": resolved,
            "top_failing_tools": top_failing_tools,
            "common_error_types": common_errors,
        }
    
    def mark_resolved(self, failure_id: int, notes: str | None = None) -> bool:
        """Mark a failure as resolved with optional notes."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE failures
            SET resolved = 1, resolution_notes = ?
            WHERE id = ?
        """, (notes, failure_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def get_failure_context(self, failure_id: int) -> FailureRecord | None:
        """Get full context for a specific failure."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM failures WHERE id = ?", (failure_id,))
        row = cursor.fetchone()
        conn.close()
        
        return self._row_to_record(row) if row else None
    
    def format_for_llm(self, failures: list[FailureRecord]) -> str:
        """
        Format failure records for consumption by the LLM.
        
        This enables self-healing by giving the model context about what went wrong.
        """
        if not failures:
            return "No recent failures found."
        
        lines = ["## Recent Failure Log\n"]
        
        for f in failures:
            lines.append(f"### Failure #{f.id}: {f.tool_name}")
            lines.append(f"- **Error Type:** {f.error_type}")
            lines.append(f"- **Message:** {f.error_message}")
            lines.append(f"- **Occurrences:** {f.occurrence_count}")
            lines.append(f"- **Last Seen:** {f.timestamp}")
            lines.append(f"- **Arguments:** `{json.dumps(f.arguments)}`")
            if f.resolved:
                lines.append(f"- **Status:** ✅ Resolved")
                if f.resolution_notes:
                    lines.append(f"- **Resolution:** {f.resolution_notes}")
            else:
                lines.append(f"- **Status:** ❌ Unresolved")
            lines.append("")
        
        return "\n".join(lines)
    
    def _row_to_record(self, row: tuple) -> FailureRecord:
        """Convert a database row to a FailureRecord."""
        return FailureRecord(
            id=row[0],
            timestamp=row[1],
            tool_name=row[2],
            error_type=row[3],
            error_message=row[4],
            arguments=json.loads(row[5]),
            user_id=row[6],
            platform=row[7],
            resolved=bool(row[8]),
            resolution_notes=row[9],
            occurrence_count=row[10],
        )


class AsyncFailureLog:
    """Async wrapper for FailureLog."""
    
    def __init__(self, db_path: str | Path):
        self._sync_log = FailureLog(db_path)
    
    async def log_failure(self, *args, **kwargs) -> int:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._sync_log.log_failure(*args, **kwargs)
        )
    
    async def get_recent_failures(self, *args, **kwargs) -> list[FailureRecord]:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._sync_log.get_recent_failures(*args, **kwargs)
        )
    
    async def get_failures_by_tool(self, tool_name: str) -> list[FailureRecord]:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._sync_log.get_failures_by_tool(tool_name)
        )
    
    async def get_failure_summary(self) -> dict[str, Any]:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_log.get_failure_summary
        )
    
    async def mark_resolved(self, failure_id: int, notes: str | None = None) -> bool:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._sync_log.mark_resolved(failure_id, notes)
        )
    
    def format_for_llm(self, failures: list[FailureRecord]) -> str:
        return self._sync_log.format_for_llm(failures)
