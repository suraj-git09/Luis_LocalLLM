import pytest

from commands.health import HealthCommand
from config.settings import Settings
from services.health import HealthService
from services.metrics import MetricsCollector
from services.scheduler import BackgroundWorker


@pytest.fixture
def test_settings(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return Settings(
        project_root=tmp_path,
        data_dir=data_dir,
        log_level="INFO",
        openai_api_key=None,
        openai_base_url="https://api.openai.com/v1",
        openai_model="gpt-4o-mini",
        local_model="gemma2:2b",
        ollama_base_url="http://localhost:11434/v1",
        vosk_model_dir=data_dir / "vosk",
        whisper_model_size="tiny",
        wake_word="assistant",
        tts_rate=175,
        tts_volume=1.0,
        notes_file=data_dir / "notes.json",
        reminders_db_path=data_dir / "reminders.db",
        max_input_chars=2000,
        max_note_chars=500,
        max_reminder_chars=300,
        max_memory_messages=20,
        llm_timeout_seconds=30,
        llm_max_tokens=512,
        llm_rate_limit_calls=10,
        llm_rate_limit_period=60,
        log_max_bytes=1024,
        log_backup_count=1,
    )


def test_health_report_includes_metrics(test_settings):
    metrics = MetricsCollector()
    metrics.record_request()
    metrics.record_command_error()

    worker = BackgroundWorker(metrics=metrics)
    worker.start()

    health = HealthService(test_settings, metrics, worker=worker)
    report = health.format_report()

    worker.stop()

    assert "System status:" in report
    assert "Total requests: 1" in report
    assert "Command errors: 1" in report
    assert "reminder_worker" in report


@pytest.mark.asyncio
async def test_health_command(test_settings):
    metrics = MetricsCollector()
    health = HealthService(test_settings, metrics)
    command = HealthCommand(health)

    response = await command.execute("system health", {})
    assert "Components:" in response
    assert "Metrics:" in response