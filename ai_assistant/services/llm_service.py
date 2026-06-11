import json
import logging
import os
import urllib.request
from typing import TYPE_CHECKING

import asyncio
from openai import APIConnectionError, APITimeoutError, NotFoundError, OpenAI

from services.prompt_optimizer import ResponseProfile, analyze_prompt, trim_context_messages
from services.rate_limiter import RateLimiter

if TYPE_CHECKING:
    from config.settings import Settings
    from services.conversation_memory import ConversationMemory

logger = logging.getLogger("ai_assistant.llm")


class LLMService:
    def __init__(
        self,
        conversation_memory: "ConversationMemory",
        settings: "Settings | None" = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.conversation_memory = conversation_memory
        self.timeout_seconds = 30.0
        self.max_tokens = 1536          # Safety cap for response length (overridable via settings/LLM_MAX_TOKENS)
        self.max_input_chars = 4000
        self._rate_limiter = RateLimiter(max_calls=10, period_seconds=60.0)
        self.using_ollama = False

        if settings is not None:
            self.timeout_seconds = settings.llm_timeout_seconds
            self.max_tokens = settings.llm_max_tokens
            self.max_input_chars = settings.max_input_chars
            self._rate_limiter = RateLimiter(
                max_calls=settings.llm_rate_limit_calls,
                period_seconds=settings.llm_rate_limit_period,
            )
            self._configure_from_settings(settings)
        else:
            self._configure_from_env(api_key, base_url, model)

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            max_retries=2,
        )

    def _ollama_tags_url(self, base_url: str) -> str:
        return base_url.replace("/v1", "") + "/api/tags"

    def _list_ollama_models(self, base_url: str) -> list[str]:
        try:
            with urllib.request.urlopen(self._ollama_tags_url(base_url), timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return [model["name"] for model in data.get("models", [])]
        except Exception as exc:
            logger.debug("Could not list Ollama models: %s", exc)
            return []

    def _ollama_is_running(self, base_url: str) -> bool:
        return bool(self._list_ollama_models(base_url))

    def _resolve_ollama_model(self, base_url: str, preferred: str) -> str:
        available = self._list_ollama_models(base_url)
        if not available:
            raise ValueError(
                "Ollama is running but no models are installed. "
                "Run: ollama pull gemma2:2b"
            )

        if preferred in available:
            return preferred

        # Match base name before tag, e.g. gemma2:9b -> gemma2:2b
        preferred_base = preferred.split(":")[0]
        for name in available:
            if name.split(":")[0] == preferred_base:
                logger.warning(
                    "Model '%s' not found; using '%s' instead. Available: %s",
                    preferred,
                    name,
                    ", ".join(available),
                )
                return name

        fallback = available[0]
        logger.warning(
            "Model '%s' not found; using '%s' instead. Available: %s",
            preferred,
            fallback,
            ", ".join(available),
        )
        return fallback

    def _configure_from_settings(self, settings: "Settings"):
        if self._ollama_is_running(settings.ollama_base_url):
            self.using_ollama = True
            self.api_key = "ollama"
            self.base_url = settings.ollama_base_url
            self.model = self._resolve_ollama_model(
                settings.ollama_base_url,
                settings.local_model,
            )
            logger.info("Connected to Ollama using model '%s'", self.model)
            return

        if not settings.openai_api_key:
            raise ValueError(
                "No LLM backend available. Start Ollama locally or set OPENAI_API_KEY in .env"
            )

        logger.info("Using online LLM API with model '%s'", settings.openai_model)
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url
        self.model = settings.openai_model

    def _configure_from_env(
        self,
        api_key: str | None,
        base_url: str | None,
        model: str | None,
    ):
        ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        if self._ollama_is_running(ollama_base):
            self.using_ollama = True
            self.api_key = "ollama"
            self.base_url = ollama_base
            preferred = model or os.getenv("LOCAL_MODEL", "gemma2:2b")
            self.model = self._resolve_ollama_model(ollama_base, preferred)
            logger.info("Connected to Ollama using model '%s'", self.model)
            return

        resolved_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_key:
            raise ValueError(
                "No LLM backend available. Start Ollama locally or set OPENAI_API_KEY in .env"
            )

        logger.info("Using online LLM API")
        self.api_key = resolved_key
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def _call_model(self, user_input: str, profile: ResponseProfile | None = None) -> str:
        if len(user_input) > self.max_input_chars:
            raise ValueError(f"Input exceeds {self.max_input_chars} character limit for LLM calls.")

        self._rate_limiter.acquire()

        # Get recent history before deciding on profile/context
        history = self.conversation_memory.get_messages()
        last_user_msg = self._get_last_user_message(history)

        # If no profile was provided by the caller (GeneralQA), analyze here with previous context
        if profile is None:
            profile = analyze_prompt(user_input, previous_user_input=last_user_msg)

        # Smart budgeting
        token_budget = min(profile.max_tokens, self.max_tokens)

        # Trim history intelligently (preserves original topic when possible)
        context = trim_context_messages(history)

        # === Key improvement for follow-ups and small models (gemma2:2b etc.) ===
        # Build a context-aware system prompt so short inputs like "5/5", "more", "the bad ones"
        # are interpreted relative to what the user actually asked before.
        system_prompt = self._build_context_aware_system_prompt(profile, user_input, last_user_msg)

        messages = (
            [{"role": "system", "content": system_prompt}]
            + context
            + [{"role": "user", "content": user_input}]
        )

        logger.debug(
            "LLM request style=%s max_tokens=%s input_chars=%s has_prev_context=%s",
            profile.style,
            token_budget,
            len(user_input),
            bool(last_user_msg),
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=token_budget,
                temperature=profile.temperature,
            )
        except APITimeoutError as exc:
            logger.error("LLM request timed out after %ss", self.timeout_seconds)
            raise TimeoutError("LLM request timed out.") from exc
        except NotFoundError as exc:
            if self.using_ollama:
                available = self._list_ollama_models(self.base_url)
                hint = (
                    f"Model '{self.model}' is not available in Ollama. "
                    f"Installed models: {', '.join(available) or 'none'}. "
                    f"Run: ollama pull {self.model}"
                )
                raise ValueError(hint) from exc
            raise ValueError("The configured LLM model was not found.") from exc
        except APIConnectionError as exc:
            if self.using_ollama:
                raise ConnectionError(
                    "Cannot connect to Ollama. Make sure Ollama is running."
                ) from exc
            raise ConnectionError("Cannot connect to the online LLM API.") from exc

        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty response.")
        return content.strip()

    def _get_last_user_message(self, history: list[dict]) -> str | None:
        """Return the most recent user message content, if any."""
        for msg in reversed(history):
            if msg.get("role") == "user":
                content = msg.get("content", "").strip()
                if content:
                    return content
        return None

    def _build_context_aware_system_prompt(
        self, profile: ResponseProfile, current_input: str, last_user_msg: str | None
    ) -> str:
        """Create a stronger system prompt for small models when the user gives short/ambiguous follow-ups."""
        base = profile.system_prompt or "Be helpful and concise."

        if not last_user_msg:
            return base

        current = current_input.strip()
        prev = last_user_msg.strip()

        # Detect if this is likely a short follow-up rather than a brand new topic
        is_short = len(current) <= 15 or len(current.split()) <= 5
        looks_like_rating_or_refinement = any(
            ch in current for ch in "0123456789/+-*%"
        ) or any(w in current.lower() for w in ("more", "the", "bad", "good", "list", "again", "other"))

        if is_short and looks_like_rating_or_refinement:
            # Explicitly anchor the model to the previous request.
            # This is especially important for tiny models like gemma2:2b that lose the thread easily.
            anchor = (
                f"Previous user request: \"{prev}\"\n"
                f"The user is now giving a short follow-up or rating: \"{current}\".\n\n"
                f"Instructions:\n"
                f"- Treat the new message as a direct continuation or refinement of the *previous request*.\n"
                f"- Stay strictly on the same topic (tech companies, good/bad lists, whatever was asked before).\n"
                f"- Be precise about quantities and categories the user originally requested.\n"
                f"- Do NOT make meta comments about 'ratings', 'being on a roll', the conversation, or the AI itself.\n"
                f"- Do NOT change the subject or start a new unrelated discussion.\n"
                f"- Just fulfill what the user is asking for right now, in the context of the previous request.\n\n"
                f"Base behavior: {base}"
            )
            return anchor

        # For normal (non-obvious-followup) short messages, still give a light reminder
        if is_short and len(prev) > 10:
            return (
                f"The ongoing topic from the user's last request was: {prev[:200]}.\n"
                f"Current user message: {current}\n\n"
                f"Answer the current message while staying relevant to the recent topic. "
                f"{base}"
            )

        return base

    async def answer_question(
        self,
        user_input: str,
        profile: ResponseProfile | None = None,
    ) -> tuple[str, ResponseProfile | None]:
        effective_profile = profile
        result = await asyncio.to_thread(self._call_model, user_input, effective_profile)
        return result, effective_profile