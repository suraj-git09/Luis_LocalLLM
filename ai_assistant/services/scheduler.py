import logging
import threading
import time
from typing import Callable

from services.reminder_store import ReminderStore

logger = logging.getLogger("ai_assistant.scheduler")


class BackgroundWorker:
    """Background worker that polls and delivers due reminders."""

    def __init__(
        self,
        reminder_store: ReminderStore | None = None,
        on_reminder: Callable[[str], None] | None = None,
        poll_interval: float = 2.0,
        metrics=None,
    ):
        self.reminder_store = reminder_store
        self.on_reminder = on_reminder or self._default_handler
        self.poll_interval = poll_interval
        self.metrics = metrics
        self.running = False
        self.thread: threading.Thread | None = None

    @staticmethod
    def _default_handler(message: str):
        print(f"\n⏰ REMINDER: {message}\n", flush=True)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self.run, daemon=True, name="reminder-worker")
        self.thread.start()
        logger.info("Background reminder worker started")

    def run(self):
        while self.running:
            try:
                self._process_due_reminders()
            except Exception:
                logger.exception("Reminder worker encountered an error")
            time.sleep(self.poll_interval)

    def _process_due_reminders(self):
        if self.reminder_store is None:
            return

        due = self.reminder_store.due_reminders()
        for reminder in due:
            try:
                self.on_reminder(reminder.message)
                self.reminder_store.mark_delivered(reminder.id)
                if self.metrics:
                    self.metrics.record_reminder_delivered()
                logger.info("Delivered reminder #%s", reminder.id)
            except Exception:
                logger.exception("Failed to deliver reminder #%s", reminder.id)

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        logger.info("Background reminder worker stopped")