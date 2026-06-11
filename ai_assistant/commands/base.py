from abc import ABC, abstractmethod


class Command(ABC):
    name = "base"
    description = "Base command"

    def can_handle(self, intent: str) -> bool:
        return intent == self.name

    @abstractmethod
    async def execute(self, user_input: str, context: dict) -> str:
        pass