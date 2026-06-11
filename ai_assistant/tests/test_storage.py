import json

import pytest

from services.storage import StorageService


def test_storage_handles_empty_file(tmp_path):
    notes_file = tmp_path / "notes.json"
    notes_file.write_text("", encoding="utf-8")

    storage = StorageService(notes_file=str(notes_file))
    assert storage.get_notes() == []

    storage.save_note("hello")
    assert storage.get_notes() == ["hello"]


def test_storage_handles_corrupt_json(tmp_path):
    notes_file = tmp_path / "notes.json"
    notes_file.write_text("{not valid", encoding="utf-8")

    storage = StorageService(notes_file=str(notes_file))
    assert storage.get_notes() == []