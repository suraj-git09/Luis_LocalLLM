import json
import logging
import os

logger = logging.getLogger("ai_assistant.storage")


class StorageService:
    def __init__(self, notes_file="data/notes.json", max_notes: int = 100):
        self.notes_file = notes_file
        self.max_notes = max_notes
        os.makedirs(os.path.dirname(self.notes_file), exist_ok=True)
        self._ensure_valid_file()

    def _ensure_valid_file(self):
        if not os.path.exists(self.notes_file) or os.path.getsize(self.notes_file) == 0:
            self._write_notes([])

    def _write_notes(self, notes: list[str]):
        with open(self.notes_file, "w", encoding="utf-8") as file:
            json.dump(notes, file, indent=4)

    def save_note(self, note: str):
        notes = self.get_notes()
        notes.append(note)
        if len(notes) > self.max_notes:
            notes = notes[-self.max_notes :]
            logger.warning("Notes limit reached; dropping oldest entries")
        self._write_notes(notes)

    def get_notes(self) -> list[str]:
        try:
            with open(self.notes_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, list):
                raise ValueError("Notes file must contain a JSON array")
            return data
        except (json.JSONDecodeError, ValueError, OSError):
            logger.warning("Notes file corrupt or unreadable; resetting to empty list")
            self._write_notes([])
            return []