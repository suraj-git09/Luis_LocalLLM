import logging

logger = logging.getLogger("ai_assistant.router")


class Router:
    def __init__(self, classifier, registry, fallback, metrics=None):
        self.classifier = classifier
        self.registry = registry
        self.fallback = fallback
        self.metrics = metrics

    async def route(self, user_input: str) -> str:
        intent = self.classifier.predict(user_input)
        logger.debug("Intent classified as '%s' for input: %s", intent, user_input)
        command = self.registry.get_command(intent)

        if command:
            try:
                response = await command.execute(user_input, context={})

                if response is None:
                    general_command = self.registry.get_command("general_qa")
                    if general_command:
                        return await general_command.execute(user_input, context={})
                    return self.fallback.get_response(user_input)

                return response

            except Exception:
                if self.metrics:
                    self.metrics.record_command_error()
                logger.exception("Command '%s' failed", intent)
                return self.fallback.get_response(user_input)

        general_command = self.registry.get_command("general_qa")
        if general_command:
            return await general_command.execute(user_input, context={})

        return self.fallback.get_response(user_input)