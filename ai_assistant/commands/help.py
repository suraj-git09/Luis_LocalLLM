from commands.base import Command


class HelpCommand(Command):
    name = "help"
    description = "Shows available commands"

    async def execute(self, user_input: str, context: dict) -> str:
        return (
            "I can help you with:\n"
            "- Calculations\n"
            "- Saving and showing notes\n"
            "- System information and current time\n"
            "- Weather (offline sample cities)\n"
            "- Reminders\n"
            "- System health and metrics\n"
            "- General questions (knowledge base then LLM — no stale cache)\n"
            "\nTry commands like:\n"
            "- calculate 5 + 3\n"
            "- save note buy milk\n"
            "- show notes\n"
            "- system info\n"
            "- what is the time\n"
            "- remind me to drink water in 5 minutes\n"
            "- show reminders\n"
            "- system health"
        )