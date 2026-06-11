from commands.base import Command


class HealthCommand(Command):
    name = "health"
    description = "Reports system health and operational metrics"

    def __init__(self, health_service):
        self.health_service = health_service

    async def execute(self, user_input: str, context: dict) -> str:
        return self.health_service.format_report()