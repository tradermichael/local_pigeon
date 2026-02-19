"""
Schedule Tools

Tools that allow users to schedule recurring tasks via natural language.

Examples:
- "Remind me every day at 9am to check my emails"
- "Every hour, search for news about AI"
- "In 30 minutes, remind me to call mom"
"""

from datetime import datetime
from typing import Any, TYPE_CHECKING

from local_pigeon.tools.registry import Tool
from local_pigeon.core.scheduler import (
    Scheduler,
    ScheduleType,
    ScheduledTask,
    parse_schedule,
)

if TYPE_CHECKING:
    pass


class CreateScheduleTool(Tool):
    """
    Tool for creating scheduled/recurring tasks.
    
    Allows users to set up cron-like jobs that run at specified intervals.
    """
    
    name = "create_schedule"
    description = (
        "Schedule a reminder or recurring task. This is NOT the calendar tool. "
        "Use this when the user says 'remind me', 'in X minutes', 'every hour', "
        "or wants you to DO something at a future time. The task will trigger "
        "the agent to act and send results to the user across all platforms.\n"
        "Examples: 'remind me in 1 minute to stretch', 'every 2 hours check my email', "
        "'in 10 minutes send me a summary of my inbox'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "A short name for the task (e.g., 'Morning email check', 'Hourly news scan')",
            },
            "task": {
                "type": "string",
                "description": "What to do when the scheduled time arrives. Write this as instructions for yourself (e.g., 'Check email and summarize new messages', 'Search for latest AI news')",
            },
            "schedule": {
                "type": "string",
                "description": "When to run. Natural language like: 'every 30 minutes', 'every 2 hours', 'daily at 9:00', 'daily at 14:30', 'in 5 minutes'",
            },
        },
        "required": ["name", "task", "schedule"],
    }
    requires_approval = False
    
    def __init__(self, scheduler: Scheduler):
        self.scheduler = scheduler
    
    async def execute(
        self,
        user_id: str,
        name: str,
        task: str,
        schedule: str,
        **kwargs,
    ) -> str:
        """Create a scheduled task."""
        try:
            # Parse the schedule string
            schedule_type, schedule_data = parse_schedule(schedule)
            
            # Get platform from kwargs if available
            platform = kwargs.get("platform", "web")
            
            # Create the task
            scheduled_task = await self.scheduler.schedule_task(
                user_id=user_id,
                name=name,
                prompt=task,
                schedule_type=schedule_type,
                schedule_data=schedule_data,
                platform=platform,
            )

            # Verify persistence before confirming success
            persisted = await self.scheduler.store.get_task(scheduled_task.id)
            if not persisted:
                return (
                    "❌ Failed to persist schedule. Please try again.\n\n"
                    "Tip: use formats like 'in 10 minutes', 'every 2 hours', or 'daily at 9:00'."
                )
            
            # Format confirmation
            next_run = scheduled_task.next_run.strftime("%Y-%m-%d %H:%M")
            
            if schedule_type == ScheduleType.ONCE:
                schedule_desc = f"once at {next_run}"
            elif schedule_type == ScheduleType.DAILY:
                hour = schedule_data.get("hour", 9)
                minute = schedule_data.get("minute", 0)
                schedule_desc = f"daily at {hour:02d}:{minute:02d}"
            elif schedule_type == ScheduleType.INTERVAL:
                parts = []
                if schedule_data.get("days"):
                    parts.append(f"{schedule_data['days']} day(s)")
                if schedule_data.get("hours"):
                    parts.append(f"{schedule_data['hours']} hour(s)")
                if schedule_data.get("minutes"):
                    parts.append(f"{schedule_data['minutes']} minute(s)")
                schedule_desc = f"every {', '.join(parts)}"
            else:
                schedule_desc = schedule
            
            return (
                f"✅ Scheduled task created!\n\n"
                f"**Name:** {name}\n"
                f"**Schedule:** {schedule_desc}\n"
                f"**Next run:** {next_run}\n"
                f"**Task ID:** `{scheduled_task.id}`\n\n"
                f"I'll automatically: {task}"
            )
            
        except ValueError as e:
            return f"❌ Invalid schedule format: {str(e)}"
        except Exception as e:
            return f"❌ Failed to create schedule: {str(e)}"


class ListSchedulesTool(Tool):
    """
    Tool for listing scheduled tasks.
    """
    
    name = "list_schedules"
    description = (
        "List all scheduled/recurring tasks for the user. "
        "Shows upcoming tasks and their next run times."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    requires_approval = False
    
    def __init__(self, scheduler: Scheduler):
        self.scheduler = scheduler
    
    async def execute(
        self,
        user_id: str,
        **kwargs,
    ) -> str:
        """List scheduled tasks."""
        try:
            tasks = await self.scheduler.store.get_user_tasks(user_id)
            
            if not tasks:
                return "📅 You have no scheduled tasks.\n\nYou can create one by saying things like:\n- 'Remind me every day at 9am to check my emails'\n- 'Every hour, search for news about Bitcoin'"
            
            lines = ["📅 **Your Scheduled Tasks**\n"]
            
            for task in tasks:
                status = "✅" if task.enabled else "⏸️"
                next_run = task.next_run.strftime("%Y-%m-%d %H:%M")
                
                # Format schedule description
                if task.schedule_type == ScheduleType.ONCE:
                    schedule_desc = "One-time"
                elif task.schedule_type == ScheduleType.DAILY:
                    hour = task.schedule_data.get("hour", 9)
                    minute = task.schedule_data.get("minute", 0)
                    schedule_desc = f"Daily at {hour:02d}:{minute:02d}"
                elif task.schedule_type == ScheduleType.INTERVAL:
                    parts = []
                    if task.schedule_data.get("days"):
                        parts.append(f"{task.schedule_data['days']}d")
                    if task.schedule_data.get("hours"):
                        parts.append(f"{task.schedule_data['hours']}h")
                    if task.schedule_data.get("minutes"):
                        parts.append(f"{task.schedule_data['minutes']}m")
                    schedule_desc = f"Every {' '.join(parts)}"
                else:
                    schedule_desc = task.schedule_type.value
                
                lines.append(f"{status} **{task.name}** ({schedule_desc})")
                lines.append(f"   Next: {next_run} | Runs: {task.run_count}")
                lines.append(f"   ID: `{task.id}`")
                lines.append("")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Failed to list schedules: {str(e)}"


class CancelScheduleTool(Tool):
    """
    Tool for canceling/deleting scheduled tasks.
    """
    
    name = "cancel_schedule"
    description = (
        "Cancel or delete a scheduled task. "
        "Use this when the user wants to stop a recurring task."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The ID of the task to cancel (from list_schedules). Can be partial (first 8 characters).",
            },
        },
        "required": ["task_id"],
    }
    requires_approval = False
    
    def __init__(self, scheduler: Scheduler):
        self.scheduler = scheduler
    
    async def execute(
        self,
        user_id: str,
        task_id: str,
        **kwargs,
    ) -> str:
        """Cancel a scheduled task."""
        try:
            # Handle partial IDs
            tasks = await self.scheduler.store.get_user_tasks(user_id)
            
            matching = [t for t in tasks if t.id.startswith(task_id)]
            
            if not matching:
                return f"❌ No task found with ID starting with `{task_id}`"
            
            if len(matching) > 1:
                return f"❌ Multiple tasks match `{task_id}`. Please be more specific."
            
            task = matching[0]
            success = await self.scheduler.store.delete_task(task.id)
            
            if success:
                return f"✅ Cancelled schedule: **{task.name}**"
            else:
                return f"❌ Failed to cancel task"
                
        except Exception as e:
            return f"❌ Failed to cancel schedule: {str(e)}"


class PauseScheduleTool(Tool):
    """
    Tool for pausing/resuming scheduled tasks.
    """
    
    name = "pause_schedule"
    description = "Pause or resume a scheduled task without deleting it."
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The ID of the task to pause/resume",
            },
            "action": {
                "type": "string",
                "enum": ["pause", "resume"],
                "description": "Whether to pause or resume the task",
            },
        },
        "required": ["task_id", "action"],
    }
    requires_approval = False
    
    def __init__(self, scheduler: Scheduler):
        self.scheduler = scheduler
    
    async def execute(
        self,
        user_id: str,
        task_id: str,
        action: str = "pause",
        **kwargs,
    ) -> str:
        """Pause or resume a scheduled task."""
        try:
            # Handle partial IDs
            tasks = await self.scheduler.store.get_user_tasks(user_id)
            matching = [t for t in tasks if t.id.startswith(task_id)]
            
            if not matching:
                return f"❌ No task found with ID starting with `{task_id}`"
            
            task = matching[0]
            
            if action == "pause":
                success = await self.scheduler.store.disable_task(task.id)
                if success:
                    return f"⏸️ Paused schedule: **{task.name}**\n\nUse resume to start it again."
            else:
                success = await self.scheduler.store.enable_task(task.id)
                if success:
                    return f"▶️ Resumed schedule: **{task.name}**\n\nNext run: {task.next_run.strftime('%Y-%m-%d %H:%M')}"
            
            return f"❌ Failed to {action} task"
                
        except Exception as e:
            return f"❌ Failed to {action} schedule: {str(e)}"
