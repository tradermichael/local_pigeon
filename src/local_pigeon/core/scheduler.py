"""
Scheduler Module

Provides a heartbeat/scheduling system for the agent to run tasks periodically.
Supports one-time and recurring scheduled tasks with persistence.
"""

import asyncio
import json
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Awaitable
from pathlib import Path

import aiosqlite


logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """Type of schedule."""
    ONCE = "once"           # Run once at a specific time
    INTERVAL = "interval"   # Run every N seconds/minutes/hours
    DAILY = "daily"         # Run daily at a specific time
    CRON = "cron"           # Cron-like scheduling (future)


@dataclass
class ScheduledTask:
    """A scheduled task."""
    id: str
    user_id: str
    name: str
    prompt: str  # What to tell the agent to do
    schedule_type: ScheduleType
    schedule_data: dict[str, Any]  # Type-specific schedule info
    created_at: datetime
    next_run: datetime
    last_run: datetime | None = None
    run_count: int = 0
    enabled: bool = True
    platform: str = "scheduler"  # Platform context for the task
    
    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "ScheduledTask":
        """Create from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            prompt=row["prompt"],
            schedule_type=ScheduleType(row["schedule_type"]),
            schedule_data=json.loads(row["schedule_data"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            next_run=datetime.fromisoformat(row["next_run"]),
            last_run=datetime.fromisoformat(row["last_run"]) if row["last_run"] else None,
            run_count=row["run_count"],
            enabled=bool(row["enabled"]),
            platform=row["platform"] or "scheduler",
        )
    
    def calculate_next_run(self) -> datetime:
        """Calculate the next run time based on schedule type."""
        now = datetime.now()
        
        if self.schedule_type == ScheduleType.ONCE:
            # One-time tasks don't reschedule
            return self.next_run
        
        elif self.schedule_type == ScheduleType.INTERVAL:
            # Run every N units
            interval_seconds = self.schedule_data.get("seconds", 0)
            interval_seconds += self.schedule_data.get("minutes", 0) * 60
            interval_seconds += self.schedule_data.get("hours", 0) * 3600
            interval_seconds += self.schedule_data.get("days", 0) * 86400
            
            if interval_seconds <= 0:
                interval_seconds = 3600  # Default: 1 hour
            
            return now + timedelta(seconds=interval_seconds)
        
        elif self.schedule_type == ScheduleType.DAILY:
            # Run daily at a specific time
            hour = self.schedule_data.get("hour", 9)
            minute = self.schedule_data.get("minute", 0)
            
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            
            return next_run
        
        return now + timedelta(hours=1)  # Default fallback


class SchedulerStore:
    """Database storage for scheduled tasks."""
    
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the scheduler table."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    schedule_type TEXT NOT NULL,
                    schedule_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    next_run TEXT NOT NULL,
                    last_run TEXT,
                    run_count INTEGER DEFAULT 0,
                    enabled INTEGER DEFAULT 1,
                    platform TEXT DEFAULT 'scheduler'
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_next_run 
                ON scheduled_tasks(next_run) WHERE enabled = 1
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_user 
                ON scheduled_tasks(user_id)
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_notifications (
                    id TEXT PRIMARY KEY,
                    task_id TEXT,
                    user_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    delivered INTEGER DEFAULT 0,
                    delivered_at TEXT
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_scheduled_notifications_pending
                ON scheduled_notifications(platform, delivered, created_at)
            """)
            await db.commit()
        
        self._initialized = True
    
    async def add_task(self, task: ScheduledTask) -> None:
        """Add a new scheduled task."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO scheduled_tasks 
                (id, user_id, name, prompt, schedule_type, schedule_data, 
                 created_at, next_run, last_run, run_count, enabled, platform)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id,
                task.user_id,
                task.name,
                task.prompt,
                task.schedule_type.value,
                json.dumps(task.schedule_data),
                task.created_at.isoformat(),
                task.next_run.isoformat(),
                task.last_run.isoformat() if task.last_run else None,
                task.run_count,
                1 if task.enabled else 0,
                task.platform,
            ))
            await db.commit()
    
    async def get_task(self, task_id: str) -> ScheduledTask | None:
        """Get a task by ID."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM scheduled_tasks WHERE id = ?",
                (task_id,),
            )
            row = await cursor.fetchone()
            if row:
                return ScheduledTask.from_row(row)
        return None
    
    async def get_due_tasks(self) -> list[ScheduledTask]:
        """Get all tasks that are due to run."""
        await self.initialize()
        
        now = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM scheduled_tasks 
                WHERE enabled = 1 AND next_run <= ?
                ORDER BY next_run ASC
            """, (now,))
            rows = await cursor.fetchall()
            return [ScheduledTask.from_row(row) for row in rows]
    
    async def get_user_tasks(self, user_id: str) -> list[ScheduledTask]:
        """Get all tasks for a user."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM scheduled_tasks WHERE user_id = ? ORDER BY next_run ASC",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [ScheduledTask.from_row(row) for row in rows]
    
    async def update_task_run(self, task: ScheduledTask) -> None:
        """Update task after a run."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE scheduled_tasks 
                SET last_run = ?, next_run = ?, run_count = ?
                WHERE id = ?
            """, (
                task.last_run.isoformat() if task.last_run else None,
                task.next_run.isoformat(),
                task.run_count,
                task.id,
            ))
            await db.commit()
    
    async def disable_task(self, task_id: str) -> bool:
        """Disable a task."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE scheduled_tasks SET enabled = 0 WHERE id = ?",
                (task_id,),
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def enable_task(self, task_id: str) -> bool:
        """Enable a task."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE scheduled_tasks SET enabled = 1 WHERE id = ?",
                (task_id,),
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM scheduled_tasks WHERE id = ?",
                (task_id,),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def add_notification(
        self,
        *,
        task_id: str | None,
        user_id: str,
        platform: str,
        message: str,
    ) -> str:
        """Persist a notification for later delivery."""
        await self.initialize()

        notification_id = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO scheduled_notifications
                (id, task_id, user_id, platform, message, created_at, delivered, delivered_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
                """,
                (
                    notification_id,
                    task_id,
                    user_id,
                    platform,
                    message,
                    datetime.now().isoformat(),
                ),
            )
            await db.commit()

        return notification_id

    async def get_pending_notifications(
        self,
        *,
        platform: str,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch pending notifications, optionally scoped to a user."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if user_id:
                cursor = await db.execute(
                    """
                    SELECT * FROM scheduled_notifications
                    WHERE delivered = 0 AND platform = ? AND user_id = ?
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (platform, user_id, limit),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT * FROM scheduled_notifications
                    WHERE delivered = 0 AND platform = ?
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (platform, limit),
                )

            rows = await cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "task_id": row["task_id"],
                    "user_id": row["user_id"],
                    "platform": row["platform"],
                    "message": row["message"],
                    "created_at": row["created_at"],
                    "delivered": bool(row["delivered"]),
                    "delivered_at": row["delivered_at"],
                }
                for row in rows
            ]

    async def mark_notification_delivered(self, notification_id: str) -> None:
        """Mark a notification as delivered."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE scheduled_notifications
                SET delivered = 1, delivered_at = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(), notification_id),
            )
            await db.commit()


class Scheduler:
    """
    Background scheduler that runs tasks on a heartbeat.
    
    Usage:
        scheduler = Scheduler(db_path, agent)
        await scheduler.start()  # Starts background loop
        
        # To stop:
        await scheduler.stop()
    """
    
    def __init__(
        self,
        db_path: str | Path,
        agent: Any = None,  # LocalPigeonAgent, but avoid circular import
        heartbeat_seconds: float = 30.0,
    ):
        self.store = SchedulerStore(db_path)
        self.agent = agent
        self.heartbeat_seconds = heartbeat_seconds
        self._running = False
        self._task: asyncio.Task | None = None
        self._callbacks: list[Callable[[ScheduledTask, str], Awaitable[None]]] = []
    
    def set_agent(self, agent: Any) -> None:
        """Set the agent (for deferred initialization)."""
        self.agent = agent
    
    def add_callback(self, callback: Callable[[ScheduledTask, str], Awaitable[None]]) -> None:
        """Add a callback to be called when a task completes."""
        self._callbacks.append(callback)
    
    async def start(self) -> None:
        """Start the scheduler background loop."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
    
    async def _heartbeat_loop(self) -> None:
        """Main heartbeat loop that checks for due tasks."""
        await self.store.initialize()
        
        while self._running:
            try:
                # Get tasks that are due
                due_tasks = await self.store.get_due_tasks()
                
                for task in due_tasks:
                    try:
                        result = await self._execute_task(task)
                        
                        # Update task
                        task.last_run = datetime.now()
                        task.run_count += 1
                        
                        if task.schedule_type == ScheduleType.ONCE:
                            # One-time task - disable after running
                            await self.store.disable_task(task.id)
                        else:
                            # Calculate next run
                            task.next_run = task.calculate_next_run()
                            await self.store.update_task_run(task)
                        
                        # Notify callbacks
                        for callback in self._callbacks:
                            try:
                                await callback(task, result)
                            except Exception:
                                pass
                    
                    except Exception as e:
                        # Log error but continue with other tasks
                        logger.exception("Scheduler error running task %s: %s", task.id, e)
                
            except Exception as e:
                logger.exception("Scheduler heartbeat error: %s", e)
            
            # Wait for next heartbeat
            await asyncio.sleep(self.heartbeat_seconds)
    
    async def _execute_task(self, task: ScheduledTask) -> str:
        """Execute a scheduled task by sending it to the agent."""
        if not self.agent:
            return "Error: No agent configured"
        
        try:
            # Send the prompt to the agent
            response = await self.agent.chat(
                user_message=f"[Scheduled Task: {task.name}]\n\n{task.prompt}",
                user_id=task.user_id,
                session_id=f"scheduled_{task.id}",
                platform=task.platform,
            )
            return response
        except Exception as e:
            return f"Error executing task: {e}"
    
    async def schedule_task(
        self,
        user_id: str,
        name: str,
        prompt: str,
        schedule_type: ScheduleType,
        schedule_data: dict[str, Any],
        platform: str = "scheduler",
    ) -> ScheduledTask:
        """
        Schedule a new task.
        
        Args:
            user_id: User who owns this task
            name: Human-readable name for the task
            prompt: What to tell the agent when it's time to run
            schedule_type: Type of schedule (once, interval, daily)
            schedule_data: Schedule-specific data
            platform: Platform context for the task
        
        Returns:
            The created ScheduledTask
        """
        task = ScheduledTask(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            prompt=prompt,
            schedule_type=schedule_type,
            schedule_data=schedule_data,
            created_at=datetime.now(),
            next_run=self._calculate_initial_run(schedule_type, schedule_data),
            platform=platform,
        )
        
        await self.store.add_task(task)
        return task
    
    def _calculate_initial_run(
        self,
        schedule_type: ScheduleType,
        schedule_data: dict[str, Any],
    ) -> datetime:
        """Calculate when to first run a task."""
        now = datetime.now()
        
        if schedule_type == ScheduleType.ONCE:
            # Parse the target time
            if "datetime" in schedule_data:
                return datetime.fromisoformat(schedule_data["datetime"])
            elif "in_minutes" in schedule_data:
                return now + timedelta(minutes=schedule_data["in_minutes"])
            elif "in_hours" in schedule_data:
                return now + timedelta(hours=schedule_data["in_hours"])
            else:
                return now + timedelta(minutes=1)
        
        elif schedule_type == ScheduleType.INTERVAL:
            # First run is after the first interval
            interval_seconds = schedule_data.get("seconds", 0)
            interval_seconds += schedule_data.get("minutes", 0) * 60
            interval_seconds += schedule_data.get("hours", 0) * 3600
            interval_seconds += schedule_data.get("days", 0) * 86400
            
            if interval_seconds <= 0:
                interval_seconds = 3600
            
            return now + timedelta(seconds=interval_seconds)
        
        elif schedule_type == ScheduleType.DAILY:
            hour = schedule_data.get("hour", 9)
            minute = schedule_data.get("minute", 0)
            
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            
            return next_run
        
        return now + timedelta(minutes=1)


def parse_schedule(schedule_str: str) -> tuple[ScheduleType, dict[str, Any]]:
    """
    Parse a natural language schedule string.
    
    Examples:
        "every 30 minutes" -> (INTERVAL, {"minutes": 30})
        "every 2 hours" -> (INTERVAL, {"hours": 2})
        "daily at 9:00" -> (DAILY, {"hour": 9, "minute": 0})
        "daily at 14:30" -> (DAILY, {"hour": 14, "minute": 30})
        "in 5 minutes" -> (ONCE, {"in_minutes": 5})
        "once at 2026-02-15T10:00:00" -> (ONCE, {"datetime": "..."})
    """
    schedule_str = schedule_str.lower().strip()
    
    # Check for "every X minutes/hours"
    import re
    
    interval_match = re.match(r"every\s+(\d+)\s+(second|minute|hour|day)s?", schedule_str)
    if interval_match:
        amount = int(interval_match.group(1))
        unit = interval_match.group(2)
        
        data = {}
        if unit == "second":
            data["seconds"] = amount
        elif unit == "minute":
            data["minutes"] = amount
        elif unit == "hour":
            data["hours"] = amount
        elif unit == "day":
            data["days"] = amount
        
        return ScheduleType.INTERVAL, data

    # Check for daily variants with optional AM/PM
    daily_match = re.match(
        r"(?:daily|every\s+day|everyday)\s*(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
        schedule_str,
    )
    if daily_match:
        hour = int(daily_match.group(1))
        minute = int(daily_match.group(2) or 0)
        meridiem = daily_match.group(3)
        if meridiem:
            if meridiem == "pm" and hour < 12:
                hour += 12
            if meridiem == "am" and hour == 12:
                hour = 0
        if hour > 23 or minute > 59:
            raise ValueError("Invalid daily schedule time")
        return ScheduleType.DAILY, {"hour": hour, "minute": minute}

    # Common language shortcuts
    if schedule_str in {"every morning", "daily morning"}:
        return ScheduleType.DAILY, {"hour": 9, "minute": 0}
    if schedule_str in {"every evening", "daily evening"}:
        return ScheduleType.DAILY, {"hour": 18, "minute": 0}
    if schedule_str in {"every night", "daily night"}:
        return ScheduleType.DAILY, {"hour": 21, "minute": 0}

    # Check for "every hour/day" without an explicit amount
    simple_interval_match = re.match(r"every\s+(second|minute|hour|day)s?", schedule_str)
    if simple_interval_match:
        unit = simple_interval_match.group(1)
        data = {}
        if unit == "second":
            data["seconds"] = 1
        elif unit == "minute":
            data["minutes"] = 1
        elif unit == "hour":
            data["hours"] = 1
        elif unit == "day":
            data["days"] = 1
        return ScheduleType.INTERVAL, data
    
    # Check for "in X minutes/hours"
    in_match = re.match(r"in\s+(\d+)\s+(minute|minutes|min|hour|hours|hr|hrs)s?", schedule_str)
    if in_match:
        amount = int(in_match.group(1))
        unit = in_match.group(2)
        
        if unit in {"minute", "minutes", "min"}:
            return ScheduleType.ONCE, {"in_minutes": amount}
        else:
            return ScheduleType.ONCE, {"in_hours": amount}
    
    # Check for ISO datetime
    try:
        dt = datetime.fromisoformat(schedule_str.replace("once at ", "").strip())
        return ScheduleType.ONCE, {"datetime": dt.isoformat()}
    except ValueError:
        pass
    
    raise ValueError(
        "Couldn't parse schedule. Try formats like: 'in 10 minutes', 'every 2 hours', or 'daily at 9:00'."
    )
