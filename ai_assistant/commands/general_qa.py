import logging

from commands.base import Command
from services.prompt_optimizer import analyze_prompt

logger = logging.getLogger("ai_assistant.general_qa")


class GeneralQACommand(Command):
    name = "general_qa"
    description = "Handles general questions using offline-first logic (knowledge base then LLM)"

    def __init__(
        self,
        knowledge_base_service,
        llm_service=None,
        conversation_memory=None,
        metrics=None,
    ):
        self.knowledge_base_service = knowledge_base_service
        self.llm_service = llm_service
        self.conversation_memory = conversation_memory
        self.metrics = metrics

    async def execute(self, user_input: str, context: dict) -> str:
        # Cache completely removed to prevent stale or irrelevant answers from old cached responses.
        # Always go fresh: knowledge base first, then LLM with good context anchoring.
        offline_answer = self.knowledge_base_service.answer(user_input)
        if offline_answer:
            return offline_answer

        if self.llm_service is not None:
            try:
                # Pass previous user message so analyze_prompt can better detect follow-ups
                # ("5/5", "more", "the bad ones" etc.) and choose a "continuation" profile.
                prev = self.conversation_memory.get_last_user_message() if self.conversation_memory else None
                profile = analyze_prompt(user_input, previous_user_input=prev)
                llm_answer, _ = await self.llm_service.answer_question(user_input, profile=profile)

                if self.conversation_memory:
                    self.conversation_memory.add_user_message(user_input)
                    self.conversation_memory.add_assistant_message(llm_answer)

                return llm_answer
            except TimeoutError:
                if self.metrics:
                    self.metrics.record_llm_error()
                return "The AI service took too long to respond. Please try again."
            except ConnectionError as exc:
                if self.metrics:
                    self.metrics.record_llm_error()
                return str(exc)
            except ValueError as exc:
                if self.metrics:
                    self.metrics.record_llm_error()
                logger.warning("LLM request rejected: %s", exc)
                return str(exc)
            except Exception as exc:
                if self.metrics:
                    self.metrics.record_llm_error()
                logger.exception("LLM request failed")
                return (
                    "I could not reach the AI service. "
                    f"Details: {exc.__class__.__name__}. "
                    "Check that Ollama is running or OPENAI_API_KEY is set in .env."
                )

        return (
            "I do not have an offline answer for that. "
            "Start Ollama (ollama serve) or set OPENAI_API_KEY in your .env file."
        )