class ConversationMemory:
    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self.messages: list[dict[str, str]] = []

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_message(self, content: str):
        self.messages.append({"role": "assistant", "content": content})
        self._trim()

    def _trim(self):
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def get_messages(self):
        return self.messages.copy()

    def get_last_user_message(self) -> str | None:
        """Return the content of the most recent user message, if any."""
        for msg in reversed(self.messages):
            if msg.get("role") == "user":
                content = msg.get("content", "").strip()
                if content:
                    return content
        return None

    def clear(self):
        self.messages = []