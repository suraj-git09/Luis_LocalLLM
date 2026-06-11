import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Reminder:
    id: int
    message: str
    due_at: datetime
    delivered: bool


class ReminderStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_table()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _create_table(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )

    def add(self, message: str, due_at: datetime) -> int:
        now = datetime.now(timezone.utc).isoformat()
        due_iso = due_at.astimezone(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reminders (message, due_at, delivered, created_at)
                VALUES (?, ?, 0, ?)
                """,
                (message, due_iso, now),
            )
            return int(cursor.lastrowid)

    def list_pending(self) -> list[Reminder]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, message, due_at, delivered
                FROM reminders
                WHERE delivered = 0
                ORDER BY due_at ASC
                """
            ).fetchall()

        reminders = []
        for row in rows:
            reminders.append(
                Reminder(
                    id=row["id"],
                    message=row["message"],
                    due_at=datetime.fromisoformat(row["due_at"]),
                    delivered=bool(row["delivered"]),
                )
            )
        return reminders

    def due_reminders(self) -> list[Reminder]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, message, due_at, delivered
                FROM reminders
                WHERE delivered = 0 AND due_at <= ?
                ORDER BY due_at ASC
                """,
                (now,),
            ).fetchall()

        return [
            Reminder(
                id=row["id"],
                message=row["message"],
                due_at=datetime.fromisoformat(row["due_at"]),
                delivered=bool(row["delivered"]),
            )
            for row in rows
        ]

    def mark_delivered(self, reminder_id: int):
        with self._connect() as conn:
            conn.execute(
                "UPDATE reminders SET delivered = 1 WHERE id = ?",
                (reminder_id,),
            )