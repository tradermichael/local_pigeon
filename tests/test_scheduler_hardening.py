"""Regression tests for scheduler reliability and notification delivery."""

import asyncio
from datetime import datetime, timedelta

import pytest

from local_pigeon.config import Settings
from local_pigeon.core.agent import LocalPigeonAgent
from local_pigeon.core.scheduler import (
    ScheduleType,
    ScheduledTask,
    SchedulerStore,
    parse_schedule,
)


@pytest.mark.asyncio
async def test_scheduler_store_handles_pending_notifications(tmp_path):
    """Pending notifications are stored and can be marked delivered."""
    db_path = tmp_path / "scheduler_notifications.db"
    store = SchedulerStore(db_path)
    await store.initialize()

    notification_id = await store.add_notification(
        task_id="task-1",
        user_id="user-1",
        platform="web",
        message="scheduled result",
    )

    pending = await store.get_pending_notifications(platform="web", user_id="user-1")
    assert len(pending) == 1
    assert pending[0]["id"] == notification_id
    assert pending[0]["message"] == "scheduled result"

    await store.mark_notification_delivered(notification_id)
    pending_after = await store.get_pending_notifications(platform="web", user_id="user-1")
    assert pending_after == []


@pytest.mark.asyncio
async def test_agent_queues_then_flushes_notification(tmp_path):
    """If a platform sender is unavailable, messages are queued then flushed on registration."""
    settings = Settings()
    settings.storage.database = str(tmp_path / "agent_scheduler.db")

    agent = LocalPigeonAgent(settings=settings)
    await agent.scheduler.store.initialize()

    await agent._send_or_queue_scheduled_notification(
        user_id="user-abc",
        platform="discord",
        message="hello from scheduler",
        task_id="task-abc",
    )

    pending = await agent.scheduler.store.get_pending_notifications(platform="discord")
    assert len(pending) == 1

    delivered: list[tuple[str, str]] = []

    async def fake_sender(user_id: str, message: str, **kwargs):
        delivered.append((user_id, message))

    agent.register_message_handler("discord", fake_sender)

    # allow background flush task to run
    await asyncio.sleep(0.1)

    pending_after = await agent.scheduler.store.get_pending_notifications(platform="discord")
    assert pending_after == []
    assert delivered == [("user-abc", "hello from scheduler")]


def test_parse_schedule_supports_daily_am_pm_variants():
    """Natural language daily time variants are parsed deterministically."""
    schedule_type, schedule_data = parse_schedule("every day at 9am")
    assert schedule_type == ScheduleType.DAILY
    assert schedule_data == {"hour": 9, "minute": 0}

    schedule_type, schedule_data = parse_schedule("daily at 2:30pm")
    assert schedule_type == ScheduleType.DAILY
    assert schedule_data == {"hour": 14, "minute": 30}


def test_parse_schedule_raises_for_unrecognized_formats():
    """Unrecognized schedules fail instead of silently defaulting to 1 hour."""
    with pytest.raises(ValueError):
        parse_schedule("sometime later maybe")


@pytest.mark.asyncio
async def test_overdue_tasks_are_returned_after_offline_gap(tmp_path):
    """Overdue tasks are discoverable immediately on restart via next_run <= now."""
    db_path = tmp_path / "overdue_tasks.db"
    store = SchedulerStore(db_path)
    await store.initialize()

    overdue_task = ScheduledTask(
        id="task-overdue",
        user_id="web_user",
        name="Morning summary",
        prompt="Summarize morning emails",
        schedule_type=ScheduleType.DAILY,
        schedule_data={"hour": 9, "minute": 0},
        created_at=datetime.now() - timedelta(hours=2),
        next_run=datetime.now() - timedelta(minutes=30),
        platform="web",
    )
    await store.add_task(overdue_task)

    due = await store.get_due_tasks()
    assert len(due) == 1
    assert due[0].id == "task-overdue"
