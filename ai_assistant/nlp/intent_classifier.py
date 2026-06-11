import re


class IntentClassifier:
    def predict(self, user_input: str) -> str:
        text = user_input.lower().strip()

        if any(word in text for word in ["help", "what can you do", "what all can you do", "commands"]):
            return "help"

        if any(
            phrase in text
            for phrase in [
                "remind me",
                "set a reminder",
                "show reminders",
                "list reminders",
                "my reminders",
            ]
        ):
            return "reminder"

        note_phrases = [
            "save note",
            "show notes",
            "list notes",
            "my notes",
            "remember this",
            "take a note",
            "write a note",
            "make a note",
            "note to self",
        ]
        if any(phrase in text for phrase in note_phrases):
            return "notes"
        # Bare "note(s)" only in contexts that sound like the personal notes feature.
        # Avoid "release notes", "version notes", "keynote", "noted that", "take note of the news", etc.
        if re.search(r"\b(note|notes)\b", text) and any(
            ctx in text for ctx in ["personal", "my ", "save", "remember", "write down"]
        ):
            return "notes"

        if any(
            phrase in text
            for phrase in [
                "system health",
                "health check",
                "assistant status",
                "system status",
                "health status",
            ]
        ):
            return "health"

        if any(word in text for word in ["system info", "cpu", "memory", "battery"]):
            return "system_info"
        # "os" as whole word only (prevents "cons", "also", "most", "close" etc. from triggering system_info)
        if re.search(r"\bos\b", text):
            return "system_info"

        # Very specific time queries only — broad words like "time" or "times of india"
        # must fall through to general_qa / LLM so we don't return local clock for news etc.
        time_phrases = [
            "what time is it",
            "what is the time",
            "current time",
            "tell me the time",
            "system time",
            "what's the time",
            "time now",
        ]
        if any(phrase in text for phrase in time_phrases):
            return "system_info"

        if any(word in text for word in ["weather", "temperature", "forecast", "rain"]):
            return "weather"

        if self._is_math_query(text):
            return "calculate"

        return "general_qa"

    def _is_math_query(self, text: str) -> bool:
        """Strict heuristic to avoid hijacking normal sentences containing stray symbols.

        Triggers only when:
        - User uses explicit math words (calculate, solve, compute), OR
        - The text contains BOTH a digit AND a math operator symbol,
          and does not look like common non-math patterns (year ranges, versions, etc).
        """
        # Explicit math intent words (strong signal)
        if any(word in text for word in ["calculate", "solve", "compute"]):
            return True

        has_digit = bool(re.search(r"\d", text))
        has_operator = bool(re.search(r"[\+\-\*/%]", text))

        if not (has_digit and has_operator):
            # word-based operators as secondary signal
            word_ops = ["plus", "minus", "times", "divided by", "multiplied by"]
            if any(op in text for op in word_ops) and (has_digit or has_operator):
                return True
            return False

        # Anti-patterns: things that contain digit + operator but are not math questions
        # Year ranges: 2023-2024, 1999/2000, etc.
        if re.search(r"\b(19|20)\d{2}\s*[-/]\s*(19|20)?\d{2}\b", text):
            return False
        # Ticket / PR / issue ranges: #42-1337, 123-456, etc.
        if re.search(r"#?\d+\s*-\s*\d+", text):
            return False
        # Version-like numbers: 2.0 / 3.0 , v1.2.3 etc.
        if re.search(r"\b\d+\.\d+(\.\d+)?\s*[/]\s*\d+", text):
            return False
        # Simple "X/Y" or "X / Y" ratings/scores (very common false positive)
        if re.search(r"\b\d+\s*[/]\s*\d+\b", text) and not any(
            w in text for w in ["calculate", "solve", "compute"]
        ):
            # e.g. "rate 4/5", "score 9/10", "movie 4/5 stars"
            return False

        return True