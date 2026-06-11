import pytest

from assistant.core import AssistantCore
from assistant.router import Router
from commands.registry import CommandRegistry
from nlp.intent_classifier import IntentClassifier
from services.conversation_memory import ConversationMemory
from utils.validation import InputValidationError, sanitize_text


class _DummyFallback:
    def get_response(self, user_input):
        return "fallback"


def test_rejects_control_characters():
    with pytest.raises(InputValidationError):
        sanitize_text("hello\x00world")


def test_rejects_oversized_input():
    with pytest.raises(InputValidationError):
        sanitize_text("a" * 2001, max_length=2000)


def test_conversation_memory_trims_old_messages():
    memory = ConversationMemory(max_messages=4)
    for i in range(6):
        memory.add_user_message(f"user-{i}")
        memory.add_assistant_message(f"assistant-{i}")

    messages = memory.get_messages()
    assert len(messages) == 4
    assert messages[0]["content"] == "user-4"
    assert messages[-1]["content"] == "assistant-5"


@pytest.mark.asyncio
async def test_assistant_core_rejects_invalid_input():
    router = Router(
        classifier=IntentClassifier(),
        registry=CommandRegistry(),
        fallback=_DummyFallback(),
    )
    core = AssistantCore(router, max_input_chars=100)

    response = await core.handle_input("x" * 200)
    assert "Invalid input" in response
    assert "maximum length" in response