import logging
import os
import sqlite3
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from config.settings import Settings
from services.metrics import MetricsCollector

logger = logging.getLogger("ai_assistant.health")


@dataclass
class ComponentHealth:
    name: str
    status: str
    detail: str


class HealthService:
    def __init__(
        self,
        settings: Settings,
        metrics: MetricsCollector,
        worker=None,
        llm_service=None,
    ):
        self.settings = settings
        self.metrics = metrics
        self.worker = worker
        self.llm_service = llm_service

    def check_all(self) -> list[ComponentHealth]:
        return [
            self._check_data_directory(),
            self._check_sqlite(self.settings.reminders_db_path, "reminders_db"),
            self._check_notes_file(),
            self._check_logs(),
            self._check_background_worker(),
            self._check_llm_backend(),
        ]

    def _check_data_directory(self) -> ComponentHealth:
        if self.settings.data_dir.exists():
            return ComponentHealth("data_dir", "healthy", str(self.settings.data_dir))
        return ComponentHealth("data_dir", "unhealthy", "Data directory missing")

    def _check_sqlite(self, db_path: Path, name: str) -> ComponentHealth:
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1")
            conn.close()
            return ComponentHealth(name, "healthy", str(db_path))
        except Exception as exc:
            logger.warning("%s health check failed: %s", name, exc)
            return ComponentHealth(name, "unhealthy", str(exc))

    def _check_notes_file(self) -> ComponentHealth:
        notes_path = self.settings.notes_file
        try:
            if not notes_path.exists():
                notes_path.parent.mkdir(parents=True, exist_ok=True)
                notes_path.write_text("[]", encoding="utf-8")
            return ComponentHealth("notes_file", "healthy", str(notes_path))
        except Exception as exc:
            return ComponentHealth("notes_file", "unhealthy", str(exc))

    def _check_logs(self) -> ComponentHealth:
        logs_dir = self.settings.logs_dir
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
            probe = logs_dir / ".health_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            log_file = logs_dir / "assistant.log"
            size = log_file.stat().st_size if log_file.exists() else 0
            return ComponentHealth("logging", "healthy", f"log_size={size} bytes")
        except Exception as exc:
            return ComponentHealth("logging", "unhealthy", str(exc))

    def _check_background_worker(self) -> ComponentHealth:
        if self.worker is None:
            return ComponentHealth("reminder_worker", "unknown", "Worker not initialized")
        if self.worker.running and self.worker.thread and self.worker.thread.is_alive():
            return ComponentHealth("reminder_worker", "healthy", "Background worker running")
        return ComponentHealth("reminder_worker", "unhealthy", "Background worker not running")

    def _check_llm_backend(self) -> ComponentHealth:
        if self.llm_service is None:
            return ComponentHealth("llm_backend", "unknown", "LLM service not configured")

        base_url = self.llm_service.base_url
        if self.llm_service.api_key == "ollama":
            try:
                tags_url = base_url.replace("/v1", "") + "/api/tags"
                with urllib.request.urlopen(tags_url, timeout=1.0) as resp:
                    if resp.status == 200:
                        import json

                        data = json.loads(resp.read().decode("utf-8"))
                        available = [m["name"] for m in data.get("models", [])]
                        model = self.llm_service.model
                        if model in available:
                            return ComponentHealth(
                                "llm_backend",
                                "healthy",
                                f"Ollama model ready ({model})",
                            )
                        return ComponentHealth(
                            "llm_backend",
                            "unhealthy",
                            f"Model '{model}' missing. Installed: {', '.join(available) or 'none'}",
                        )
            except Exception as exc:
                return ComponentHealth("llm_backend", "unhealthy", f"Ollama unreachable: {exc}")

        if os.getenv("OPENAI_API_KEY") or self.settings.openai_api_key:
            return ComponentHealth(
                "llm_backend",
                "healthy",
                f"Online API ({self.llm_service.model})",
            )
        return ComponentHealth("llm_backend", "unhealthy", "No LLM backend configured")

    def format_report(self) -> str:
        components = self.check_all()
        snapshot = self.metrics.get_snapshot()
        metrics = snapshot.to_dict()

        unhealthy = [c for c in components if c.status == "unhealthy"]
        overall = "healthy" if not unhealthy else "degraded"

        lines = [
            f"System status: {overall.upper()}",
            "",
            "Components:",
        ]
        for component in components:
            icon = {"healthy": "[OK]", "unhealthy": "[FAIL]", "unknown": "[??]"}.get(
                component.status, "[??]"
            )
            lines.append(f"  {icon} {component.name}: {component.detail}")

        lines.extend(
            [
                "",
                "Metrics:",
                f"  Uptime: {metrics['uptime_seconds']}s",
                f"  Total requests: {metrics['total_requests']}",
                f"  Command errors: {metrics['command_errors']}",
                f"  LLM errors: {metrics['llm_errors']}",
                f"  Validation errors: {metrics['validation_errors']}",
                f"  Reminders delivered: {metrics['reminders_delivered']}",
            ]
        )
        return "\n".join(lines)