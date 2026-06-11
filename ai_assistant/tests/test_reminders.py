from datetime import datetime, timedelta, timezone

import pytest

from commands.reminders import ReminderCommand
from services.reminder_store import ReminderStore


@pytest.mark.asyncio
async def test_create_and_list_reminder(tmp_data_dir):
    store = ReminderStore(tmp_data_dir / "reminders.db")
    command = ReminderCommand(store)

    response = await command.execute("remind me to stretch in 10 minutes", {})
    assert "Reminder #1 set" in response
    assert "stretch" in response

    listed = await command.execute("show reminders", {})
    assert "stretch" in listed


def test_reminder_store_due_detection(tmp_data_dir):
    store = ReminderStore(tmp_data_dir / "reminders.db")
    due_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    reminder_id = store.add("test reminder", due_at)

    due = store.due_reminders()
    assert len(due) == 1
    assert due[0].id == reminder_id

    store.mark_delivered(reminder_id)
    assert store.due_reminders() == []