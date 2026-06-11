import re
from datetime import datetime, timedelta, timezone

from commands.base import Command
from utils.validation import InputValidationError, sanitize_text


_TIME_UNITS = {
    "second": 1,
    "seconds": 1,
    "sec": 1,
    "s": 1,
    "minute": 60,
    "minutes": 60,
    "min": 60,
    "m": 60,
    "hour": 3600,
    "hours": 3600,
    "hr": 3600,
    "h": 3600,
}


class ReminderCommand(Command):
    name = "reminder"
    description = "Creates and lists reminders"

    def __init__(self, reminder_store, max_reminder_chars: int = 300):
        self.reminder_store = reminder_store
        self.max_reminder_chars = max_reminder_chars

    async def execute(self, user_input: str, context: dict) -> str:
        text = user_input.strip()
        lower = text.lower()

        if lower in {"show reminders", "list reminders", "my reminders"}:
            return self._list_reminders()

        parsed = self._parse_reminder(text)
        if parsed is None:
            return (
                "I couldn't parse that reminder.\n\n"
                "Try:\n"
                "• remind me to drink water in 15 minutes\n"
                "• remind me to call mom at 3pm\n"
                "• remind me to take medicine at 22:30\n"
                "• show reminders"
            )

        message, due_at = parsed
        try:
            message = sanitize_text(message, max_length=self.max_reminder_chars)
        except InputValidationError as exc:
            return f"Could not set reminder: {exc}"

        reminder_id = self.reminder_store.add(message, due_at)
        due_local = due_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        return f"Reminder #{reminder_id} set: '{message}' at {due_local}"

    def _list_reminders(self) -> str:
        pending = self.reminder_store.list_pending()
        if not pending:
            return "No pending reminders."

        lines = []
        for reminder in pending:
            due_local = reminder.due_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"- #{reminder.id}: {reminder.message} (due {due_local})")
        return "Pending reminders:\n" + "\n".join(lines)

    def _parse_reminder(self, text: str) -> tuple[str, datetime] | None:
        # Expanded patterns for much more flexible phrasing (task + time)
        patterns = [
            # "remind me to do X in 15 minutes"
            r"remind me to (.+?) in (\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)\b",
            r"set a reminder to (.+?) in (\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)\b",
            # "remind me in 20 min to call mom"
            r"remind me in (\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)\s*to (.+)",
            # "remind me to take medicine at 3pm" or "at 15:30"
            r"remind me to (.+?) at (\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b",
            r"remind me to (.+?) at (\d{1,2}:\d{2})\b",
            # "set reminder for X at 9:30"
            r"(?:set )?reminder (?:for|to) (.+?) at (\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue

            if "remind me in" in pattern:
                amount = int(match.group(1))
                unit = match.group(2).lower()
                message = match.group(3).strip()
                seconds = amount * _TIME_UNITS.get(unit, 60)
                due_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
                return message, due_at

            # "in ..." style (first two patterns)
            if " in " in pattern or pattern.startswith("set a reminder"):
                message = match.group(1).strip()
                amount = int(match.group(2))
                unit = match.group(3).lower()
                seconds = amount * _TIME_UNITS.get(unit, 60)
                due_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
                return message, due_at

            # "at TIME" styles — parse simple clock times (today)
            message = match.group(1).strip()
            time_str = match.group(2).strip().lower()

            due_at = self._parse_clock_time(time_str)
            if due_at:
                return message, due_at

        return None

    def _parse_clock_time(self, time_str: str) -> datetime | None:
        """Very lightweight parser for common 'at 3pm', 'at 15:30', 'at 9' etc. (today)."""
        now = datetime.now()
        try:
            # Normalize
            t = time_str.replace(" ", "").lower()

            hour = None
            minute = 0
            is_pm = "pm" in t
            is_am = "am" in t

            # Strip am/pm for parsing
            t = t.replace("am", "").replace("pm", "")

            if ":" in t:
                parts = t.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
            else:
                hour = int(t)

            if is_pm and hour < 12:
                hour += 12
            if is_am and hour == 12:
                hour = 0

            if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                return None

            due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # If the time has already passed today, schedule for tomorrow
            if due <= now:
                due += timedelta(days=1)

            return due.astimezone(timezone.utc)
        except Exception:
            return None