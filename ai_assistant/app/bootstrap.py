import logging
from dataclasses import dataclass

from assistant.core import AssistantCore
from assistant.fallback import OfflineFallback
from assistant.router import Router
from commands.calculator import CalculatorCommand
from commands.general_qa import GeneralQACommand
from commands.health import HealthCommand
from commands.help import HelpCommand
from commands.notes import NotesCommand
from commands.registry import CommandRegistry
from commands.reminders import ReminderCommand
from commands.system_info import SystemInfoCommand
from commands.weather import WeatherCommand
from config.settings import Settings, get_settings
from nlp.intent_classifier import IntentClassifier
from services.conversation_memory import ConversationMemory
from services.health import HealthService
from services.knowledge_base import KnowledgeBaseService
from services.llm_service import LLMService
from services.logging_config import setup_logging
from services.metrics import MetricsCollector
from services.reminder_store import ReminderStore
from services.scheduler import BackgroundWorker
from services.storage import StorageService

logger = logging.getLogger("ai_assistant.bootstrap")


@dataclass
class Application:
    settings: Settings
    assistant: AssistantCore
    worker: BackgroundWorker
    reminder_store: ReminderStore
    metrics: MetricsCollector
    health_service: HealthService


def build_application(settings: Settings | None = None) -> Application:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(
        settings.log_level,
        settings.logs_dir,
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backup_count,
    )
    logger.info("Initializing AI Assistant")

    metrics = MetricsCollector()
    storage_service = StorageService(notes_file=str(settings.notes_file))
    reminder_store = ReminderStore(db_path=settings.reminders_db_path)
    fallback_service = OfflineFallback()  # No cache — simple fallback only
    knowledge_base_service = KnowledgeBaseService()
    conversation_memory = ConversationMemory(max_messages=settings.max_memory_messages)
    llm_service = LLMService(conversation_memory=conversation_memory, settings=settings)

    worker = BackgroundWorker(reminder_store=reminder_store, metrics=metrics)
    health_service = HealthService(
        settings=settings,
        metrics=metrics,
        worker=worker,
        llm_service=llm_service,
    )

    intent_classifier = IntentClassifier()
    registry = CommandRegistry()
    registry.register(CalculatorCommand())
    registry.register(NotesCommand(storage_service, max_note_chars=settings.max_note_chars))
    registry.register(SystemInfoCommand())
    registry.register(HealthCommand(health_service))
    registry.register(HelpCommand())
    registry.register(WeatherCommand())
    registry.register(
        ReminderCommand(reminder_store, max_reminder_chars=settings.max_reminder_chars)
    )
    registry.register(
        GeneralQACommand(
            knowledge_base_service=knowledge_base_service,
            llm_service=llm_service,
            conversation_memory=conversation_memory,
            metrics=metrics,
        )
    )

    router = Router(
        classifier=intent_classifier,
        registry=registry,
        fallback=fallback_service,
        metrics=metrics,
    )
    assistant = AssistantCore(router, max_input_chars=settings.max_input_chars, metrics=metrics)
    worker.start()

    logger.info("AI Assistant ready")
    return Application(
        settings=settings,
        assistant=assistant,
        worker=worker,
        reminder_store=reminder_store,
        metrics=metrics,
        health_service=health_service,
    )