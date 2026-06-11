from commands.base import Command


class WeatherCommand(Command):
    name = "weather"
    description = "Provides weather information"

    async def execute(self, user_input: str, context: dict) -> str | None:
        text = user_input.lower()

        if "delhi" in text:
            return "Weather in Delhi: Sunny, around 35°C. (offline sample response)"

        if "mumbai" in text:
            return "Weather in Mumbai: Humid, around 30°C. (offline sample response)"

        if "london" in text:
            return "Weather in London: Cloudy, around 18°C. (offline sample response)"

        # Local weather command does not know the answer
        return None