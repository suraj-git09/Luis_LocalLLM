import os
from dataclasses import dataclass
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    log_level: str

    openai_api_key: str | None
    openai_base_url: str
    openai_model: str

    local_model: str
    ollama_base_url: str

    vosk_model_dir: Path
    whisper_model_size: str
    wake_word: str
    tts_rate: int
    tts_volume: float

    notes_file: Path
    reminders_db_path: Path

    max_input_chars: int
    max_note_chars: int
    max_reminder_chars: int
    max_memory_messages: int
    llm_timeout_seconds: float
    llm_max_tokens: int
    llm_rate_limit_calls: int
    llm_rate_limit_period: float

    log_max_bytes: int
    log_backup_count: int

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"


def get_settings() -> Settings:
    root = _project_root()
    data_dir = Path(os.getenv("DATA_DIR", root / "data"))
    if not data_dir.is_absolute():
        data_dir = root / data_dir

    vosk_dir = Path(os.getenv("VOSK_MODEL_DIR", data_dir / "vosk-model-small-en-us-0.15"))
    if not vosk_dir.is_absolute():
        vosk_dir = root / vosk_dir

    return Settings(
        project_root=root,
        data_dir=data_dir,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        local_model=os.getenv("LOCAL_MODEL", "gemma2:2b"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        vosk_model_dir=vosk_dir,
        whisper_model_size=os.getenv("WHISPER_MODEL_SIZE", "tiny"),
        wake_word=os.getenv("WAKE_WORD", "assistant"),
        tts_rate=int(os.getenv("TTS_RATE", "175")),
        tts_volume=float(os.getenv("TTS_VOLUME", "1.0")),
        notes_file=data_dir / "notes.json",
        reminders_db_path=data_dir / "reminders.db",
        max_input_chars=int(os.getenv("MAX_INPUT_CHARS", "4000")),
        max_note_chars=int(os.getenv("MAX_NOTE_CHARS", "500")),
        max_reminder_chars=int(os.getenv("MAX_REMINDER_CHARS", "300")),
        max_memory_messages=int(os.getenv("MAX_MEMORY_MESSAGES", "8")),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1536")),
        llm_rate_limit_calls=int(os.getenv("LLM_RATE_LIMIT_CALLS", "10")),
        llm_rate_limit_period=float(os.getenv("LLM_RATE_LIMIT_PERIOD", "60")),
        log_max_bytes=int(os.getenv("LOG_MAX_BYTES", str(5 * 1024 * 1024))),
        log_backup_count=int(os.getenv("LOG_BACKUP_COUNT", "3")),
    )