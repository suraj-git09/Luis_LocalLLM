import logging

from utils.validation import InputValidationError, validate_user_input

logger = logging.getLogger("ai_assistant.core")


class AssistantCore:
    def __init__(self, router, max_input_chars: int = 2000, metrics=None):
        self.router = router
        self.max_input_chars = max_input_chars
        self.metrics = metrics

    async def handle_input(self, user_input: str) -> str:
        if self.metrics:
            self.metrics.record_request()

        try:
            safe_input = validate_user_input(user_input, max_length=self.max_input_chars)
        except InputValidationError as exc:
            if self.metrics:
                self.metrics.record_validation_error()
            logger.warning("Rejected invalid input: %s", exc)
            return f"Invalid input: {exc}"

        response = await self.router.route(safe_input)
        return response