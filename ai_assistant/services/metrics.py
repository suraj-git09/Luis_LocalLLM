import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class MetricsSnapshot:
    total_requests: int = 0
    command_errors: int = 0
    llm_errors: int = 0
    validation_errors: int = 0
    reminders_delivered: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        uptime = datetime.now(timezone.utc) - self.started_at
        return {
            "total_requests": self.total_requests,
            "command_errors": self.command_errors,
            "llm_errors": self.llm_errors,
            "validation_errors": self.validation_errors,
            "reminders_delivered": self.reminders_delivered,
            "uptime_seconds": int(uptime.total_seconds()),
        }


class MetricsCollector:
    """Thread-safe in-process metrics for operational monitoring."""

    def __init__(self):
        self._lock = threading.Lock()
        self._snapshot = MetricsSnapshot()

    def record_request(self):
        with self._lock:
            self._snapshot.total_requests += 1

    def record_command_error(self):
        with self._lock:
            self._snapshot.command_errors += 1

    def record_llm_error(self):
        with self._lock:
            self._snapshot.llm_errors += 1

    def record_validation_error(self):
        with self._lock:
            self._snapshot.validation_errors += 1

    def record_reminder_delivered(self):
        with self._lock:
            self._snapshot.reminders_delivered += 1

    def get_snapshot(self) -> MetricsSnapshot:
        with self._lock:
            return MetricsSnapshot(
                total_requests=self._snapshot.total_requests,
                command_errors=self._snapshot.command_errors,
                llm_errors=self._snapshot.llm_errors,
                validation_errors=self._snapshot.validation_errors,
                reminders_delivered=self._snapshot.reminders_delivered,
                started_at=self._snapshot.started_at,
            )