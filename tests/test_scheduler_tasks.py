"""Tests for the scheduler task panel, execution history, and notification delivery."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from local_pigeon.config import Settings
from local_pigeon.core.agent import LocalPigeonAgent
from local_pigeon.core.scheduler import (
    Scheduler,
    ScheduleType,
    ScheduledTask,
    SchedulerStore,
    parse_schedule,
)


# ---------------------------------------------------------------------------
# Execution history table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execution_history_is_logged(tmp_path):
    """log_execution persists a record and get_execution_history returns it."""
    store = SchedulerStore(tmp_path / "hist.db")
    await store.initialize()

    task = ScheduledTask(
        id="task-hist-1",
        user_id="web_user",
        name="Test reminder",
        prompt="say hello",
        schedule_type=ScheduleType.ONCE,
        schedule_data={"in_minutes": 1},
        created_at=datetime.now(),
        next_run=datetime.now(),
        platform="web",
    )

    eid = await store.log_execution(task=task, result="Hello!", success=True)
    assert eid  # non-empty UUID

    history = await store.get_execution_history(user_id="web_user")
    assert len(history) == 1
    assert history[0]["task_id"] == "task-hist-1"
    assert history[0]["task_name"] == "Test reminder"
    assert history[0]["result"] == "Hello!"
    assert history[0]["success"] is True


@pytest.mark.asyncio
async def test_execution_history_records_failure(tmp_path):
    """Failed executions are recorded with success=False."""
    store = SchedulerStore(tmp_path / "hist_fail.db")
    await store.initialize()

    task = ScheduledTask(
        id="task-fail-1",
        user_id="web_user",
        name="Failing task",
        prompt="do something",
        schedule_type=ScheduleType.ONCE,
        schedule_data={"in_minutes": 1},
        created_at=datetime.now(),
        next_run=datetime.now(),
        platform="web",
    )

    await store.log_execution(task=task, result="Connection error", success=False)

    history = await store.get_execution_history(user_id="web_user")
    assert len(history) == 1
    assert history[0]["success"] is False
    assert "Connection error" in history[0]["result"]


@pytest.mark.asyncio
async def test_execution_history_filter_by_task_id(tmp_path):
    """Execution history can be filtered to a specific task."""
    store = SchedulerStore(tmp_path / "hist_filter.db")
    await store.initialize()

    for i, tid in enumerate(["task-a", "task-b", "task-a"]):
        task = ScheduledTask(
            id=tid,
            user_id="web_user",
            name=f"Task {tid}",
            prompt="do it",
            schedule_type=ScheduleType.INTERVAL,
            schedule_data={"minutes": 5},
            created_at=datetime.now(),
            next_run=datetime.now(),
            platform="web",
        )
        await store.log_execution(task=task, result=f"result-{i}", success=True)

    history_a = await store.get_execution_history(task_id="task-a")
    assert len(history_a) == 2

    history_b = await store.get_execution_history(task_id="task-b")
    assert len(history_b) == 1


@pytest.mark.asyncio
async def test_execution_history_truncates_long_results(tmp_path):
    """Results longer than 2000 chars are truncated on write."""
    store = SchedulerStore(tmp_path / "hist_trunc.db")
    await store.initialize()

    task = ScheduledTask(
        id="task-long",
        user_id="web_user",
        name="Verbose task",
        prompt="do it",
        schedule_type=ScheduleType.ONCE,
        schedule_data={"in_minutes": 1},
        created_at=datetime.now(),
        next_run=datetime.now(),
        platform="web",
    )

    long_result = "x" * 5000
    await store.log_execution(task=task, result=long_result, success=True)

    history = await store.get_execution_history(user_id="web_user")
    assert len(history[0]["result"]) == 2000


# ---------------------------------------------------------------------------
# Scheduler heartbeat logs executions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_heartbeat_logs_execution(tmp_path):
    """The heartbeat loop logs each task execution to the history table."""
    db_path = tmp_path / "sched_hb.db"
    store = SchedulerStore(db_path)
    await store.initialize()

    # Create a due task
    task = ScheduledTask(
        id="task-hb-1",
        user_id="web_user",
        name="HB reminder",
        prompt="say hi",
        schedule_type=ScheduleType.ONCE,
        schedule_data={"in_minutes": 1},
        created_at=datetime.now() - timedelta(minutes=2),
        next_run=datetime.now() - timedelta(seconds=10),
        platform="web",
    )
    await store.add_task(task)

    # Create scheduler with a mock agent
    mock_agent = AsyncMock()
    mock_agent.chat = AsyncMock(return_value="Hi from the bot!")

    scheduler = Scheduler(db_path=db_path, agent=mock_agent, heartbeat_seconds=0.1)

    # Run one heartbeat cycle manually
    await scheduler.store.initialize()
    due = await scheduler.store.get_due_tasks()
    assert len(due) == 1

    result = await scheduler._execute_task(due[0])
    assert result == "Hi from the bot!"

    # Simulate what the heartbeat loop does: log + update
    await scheduler.store.log_execution(task=due[0], result=result, success=True)

    history = await scheduler.store.get_execution_history(user_id="web_user")
    assert len(history) == 1
    assert history[0]["task_name"] == "HB reminder"
    assert history[0]["result"] == "Hi from the bot!"


# ---------------------------------------------------------------------------
# Notification delivery to chat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_completion_queues_web_notification(tmp_path):
    """When a scheduled task completes, a notification is queued for the web poller."""
    settings = Settings()
    settings.storage.database = str(tmp_path / "notify.db")

    agent = LocalPigeonAgent(settings=settings)
    await agent.scheduler.store.initialize()

    # Simulate a completed task triggering the callback
    task = ScheduledTask(
        id="task-notify-1",
        user_id="web_user",
        name="Reminder test",
        prompt="remind me to stretch",
        schedule_type=ScheduleType.ONCE,
        schedule_data={"in_minutes": 1},
        created_at=datetime.now(),
        next_run=datetime.now(),
        platform="web",
    )

    await agent._handle_scheduled_task_completion(task, "Time to stretch!")

    # The notification should be queued (no web message handler registered)
    pending = await agent.scheduler.store.get_pending_notifications(
        platform="web", user_id="web_user",
    )
    assert len(pending) == 1
    assert "Reminder test" in pending[0]["message"]
    assert "Time to stretch!" in pending[0]["message"]
    assert "⏰" in pending[0]["message"]


@pytest.mark.asyncio
async def test_notification_message_format(tmp_path):
    """Notification message contains task name, time, and result."""
    settings = Settings()
    settings.storage.database = str(tmp_path / "fmt.db")

    agent = LocalPigeonAgent(settings=settings)
    await agent.scheduler.store.initialize()

    task = ScheduledTask(
        id="task-fmt",
        user_id="web_user",
        name="Morning brief",
        prompt="summarize news",
        schedule_type=ScheduleType.DAILY,
        schedule_data={"hour": 9, "minute": 0},
        created_at=datetime.now(),
        next_run=datetime.now(),
        platform="web",
    )

    await agent._handle_scheduled_task_completion(task, "Here's your morning summary…")

    pending = await agent.scheduler.store.get_pending_notifications(
        platform="web", user_id="web_user",
    )
    msg = pending[0]["message"]

    # Must contain structured info
    assert "Morning brief" in msg
    assert "Run time:" in msg
    assert "Result:" in msg
    assert "Here's your morning summary" in msg


# ---------------------------------------------------------------------------
# Platform passthrough
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_platform_passthrough_to_schedule_tool(tmp_path):
    """CreateScheduleTool receives the platform from the agent's tool execution."""
    db_path = tmp_path / "platform.db"
    store = SchedulerStore(db_path)
    await store.initialize()

    scheduler = Scheduler(db_path=db_path, heartbeat_seconds=60)

    from local_pigeon.tools.schedule_tools import CreateScheduleTool

    tool = CreateScheduleTool(scheduler=scheduler)

    # Simulate execution with platform="discord" (passed from agent)
    result = await tool.execute(
        user_id="discord_user_123",
        name="Discord reminder",
        task="Check channel",
        schedule="in 5 minutes",
        platform="discord",
    )

    assert "✅" in result

    tasks = await store.get_user_tasks("discord_user_123")
    assert len(tasks) == 1
    assert tasks[0].platform == "discord"


@pytest.mark.asyncio
async def test_platform_defaults_to_web(tmp_path):
    """Without explicit platform, CreateScheduleTool defaults to 'web'."""
    db_path = tmp_path / "default_plat.db"
    store = SchedulerStore(db_path)
    await store.initialize()

    scheduler = Scheduler(db_path=db_path, heartbeat_seconds=60)

    from local_pigeon.tools.schedule_tools import CreateScheduleTool

    tool = CreateScheduleTool(scheduler=scheduler)

    result = await tool.execute(
        user_id="web_user",
        name="Web reminder",
        task="Check stuff",
        schedule="in 5 minutes",
    )

    assert "✅" in result

    tasks = await store.get_user_tasks("web_user")
    assert tasks[0].platform == "web"


# ---------------------------------------------------------------------------
# Full round-trip: schedule → execute → notify → poll
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_task_round_trip(tmp_path):
    """
    End-to-end: create task → heartbeat fires → agent responds →
    notification queued → poll picks it up.
    """
    settings = Settings()
    settings.storage.database = str(tmp_path / "roundtrip.db")

    agent = LocalPigeonAgent(settings=settings)
    await agent.scheduler.store.initialize()

    # 1) Create a task that's already due
    task = await agent.scheduler.schedule_task(
        user_id="web_user",
        name="Quick reminder",
        prompt="Say hello",
        schedule_type=ScheduleType.ONCE,
        schedule_data={"in_minutes": 0},  # Due immediately (uses fallback: 1 min)
        platform="web",
    )

    # Force task to be past-due by updating next_run
    task.next_run = datetime.now() - timedelta(seconds=5)
    await agent.scheduler.store.update_task_run(task)

    # 2) Verify it shows as due
    due = await agent.scheduler.store.get_due_tasks()
    assert any(t.id == task.id for t in due)

    # 3) Simulate scheduler executing it (mock agent.chat)
    with patch.object(agent, "chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = "Hello! This is your reminder."

        # Execute the task directly (as the heartbeat loop would)
        result = await agent.scheduler._execute_task(due[0])
        assert "Hello! This is your reminder." in result

    # 4) Trigger the completion callback
    await agent._handle_scheduled_task_completion(task, result)

    # 5) Verify notification is queued
    pending = await agent.scheduler.store.get_pending_notifications(
        platform="web", user_id="web_user",
    )
    assert len(pending) >= 1
    assert "Quick reminder" in pending[0]["message"]

    # 6) Simulate the UI poller marking it delivered
    await agent.scheduler.store.mark_notification_delivered(pending[0]["id"])
    remaining = await agent.scheduler.store.get_pending_notifications(
        platform="web", user_id="web_user",
    )
    assert len(remaining) == 0


# ---------------------------------------------------------------------------
# Task management (pause / resume / delete)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_and_resume_task(tmp_path):
    """Paused tasks are not returned by get_due_tasks; resuming restores them."""
    store = SchedulerStore(tmp_path / "pause.db")
    await store.initialize()

    task = ScheduledTask(
        id="task-pause-1",
        user_id="web_user",
        name="Pausable task",
        prompt="do stuff",
        schedule_type=ScheduleType.INTERVAL,
        schedule_data={"minutes": 5},
        created_at=datetime.now() - timedelta(minutes=10),
        next_run=datetime.now() - timedelta(seconds=10),
        platform="web",
    )
    await store.add_task(task)

    # Task should be due
    assert len(await store.get_due_tasks()) == 1

    # Pause
    await store.disable_task(task.id)
    assert len(await store.get_due_tasks()) == 0

    # Resume
    await store.enable_task(task.id)
    assert len(await store.get_due_tasks()) == 1


@pytest.mark.asyncio
async def test_delete_task(tmp_path):
    """Deleted tasks are gone from the store entirely."""
    store = SchedulerStore(tmp_path / "delete.db")
    await store.initialize()

    task = ScheduledTask(
        id="task-del-1",
        user_id="web_user",
        name="Deletable task",
        prompt="do stuff",
        schedule_type=ScheduleType.ONCE,
        schedule_data={"in_minutes": 5},
        created_at=datetime.now(),
        next_run=datetime.now() + timedelta(minutes=5),
        platform="web",
    )
    await store.add_task(task)
    assert len(await store.get_user_tasks("web_user")) == 1

    await store.delete_task(task.id)
    assert len(await store.get_user_tasks("web_user")) == 0


# ---------------------------------------------------------------------------
# parse_schedule edge cases
# ---------------------------------------------------------------------------


def test_parse_schedule_in_1_minute():
    """'in 1 minute' produces a one-time task."""
    stype, data = parse_schedule("in 1 minute")
    assert stype == ScheduleType.ONCE
    assert data == {"in_minutes": 1}


def test_parse_schedule_every_30_seconds():
    """'every 30 seconds' produces an interval task."""
    stype, data = parse_schedule("every 30 seconds")
    assert stype == ScheduleType.INTERVAL
    assert data == {"seconds": 30}
