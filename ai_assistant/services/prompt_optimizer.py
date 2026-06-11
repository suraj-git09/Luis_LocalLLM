import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseProfile:
    style: str
    max_tokens: int
    system_prompt: str
    temperature: float = 0.4


_CODE_HINTS = (
    "code",
    "script",
    "program",
    "function",
    "implement",
    "write a",
    "create a",
    "build a",
    "algorithm",
    "snippet",
    "class ",
    "def ",
)

_BRIEF_HINTS = (
    "briefly",
    "short answer",
    "tldr",
    "in one sentence",
    "quick answer",
    "just tell me",
    "no explanation",
    "only the answer",
)

_EXPLAIN_HINTS = (
    "explain",
    "how does",
    "how do",
    "why does",
    "why do",
    "describe",
    "difference between",
)

_LIST_HINTS = ("list", "steps", "ways to", "examples of", "good and", "bad and", "companies", "pros and", "cons of")

_FOLLOWUP_HINTS = (
    "more",
    "again",
    "the other",
    "the bad",
    "the good",
    "details",
    "explain more",
    "what about",
    "how about",
    "and the",
    "now",
)

_RATING_LIKE = ("5/5", "4/5", "10/10", "9/10", "good/bad", "rate", "/5", "/10")


def analyze_prompt(user_input: str, previous_user_input: str | None = None) -> ResponseProfile:
    """Analyze the current user input (optionally with previous turn) and return a ResponseProfile.

    The previous_user_input helps detect true follow-ups vs topic changes.
    """
    text = user_input.lower().strip()
    word_count = len(text.split())

    is_very_short = word_count <= 6 or len(user_input.strip()) <= 12
    looks_like_followup = (
        is_very_short
        or any(h in text for h in _FOLLOWUP_HINTS)
        or any(r in text for r in _RATING_LIKE)
        or (previous_user_input and _looks_like_continuation(user_input, previous_user_input))
    )

    if any(hint in text for hint in _CODE_HINTS):
        wants_explanation = any(w in text for w in ("explain", "with comments", "how it works"))
        return ResponseProfile(
            style="code",
            max_tokens=1536 if wants_explanation else 1024,
            system_prompt=(
                "You are a precise coding assistant. "
                "Return only what was requested. "
                "For code: output the code block first using proper fenced ```python (or appropriate language) and preserve EXACT indentation, newlines, and ALL special characters. "
                "ALWAYS provide COMPLETE, full code — never truncate. No greetings, no filler."
            ),
            temperature=0.2,
        )

    if any(hint in text for hint in _BRIEF_HINTS):
        return ResponseProfile(
            style="brief",
            max_tokens=128,
            system_prompt="Answer in one short sentence. Direct answer only.",
            temperature=0.2,
        )

    if any(hint in text for hint in _LIST_HINTS) or (looks_like_followup and any(x in text for x in ("good", "bad", "list", "more", "5", "10"))):
        # Stronger list instructions, especially useful for "5 good and 5 bad" style requests and their follow-ups.
        return ResponseProfile(
            style="list",
            max_tokens=512,
            system_prompt=(
                "Provide a clear, well-structured list. Use markdown headings or bold labels when the user asks for categories (e.g. Good companies / Bad companies). "
                "Number or bullet the items. Be complete and precise about quantities the user requested (e.g. exactly 5 good + 5 bad). "
                "No unnecessary intro or conclusion unless the user asked for explanation."
            ),
            temperature=0.35,
        )

    if any(hint in text for hint in _EXPLAIN_HINTS):
        return ResponseProfile(
            style="explain",
            max_tokens=384,
            system_prompt=(
                "Explain clearly in 2-4 short sentences or 3 bullets. "
                "Skip background the user did not ask for."
            ),
            temperature=0.35,
        )

    if looks_like_followup:
        # Special profile for short follow-ups, ratings ("5/5"), refinements, "more", "the bad ones", etc.
        return ResponseProfile(
            style="continuation",
            max_tokens=384,
            system_prompt=(
                "You are continuing the user's previous request. The user often gives short follow-ups, ratings (like 5/5), refinements, or additional constraints. "
                "Interpret the new short message in the context of what they asked before. "
                "Stay strictly on the same topic. Do not change the subject. "
                "Do not make meta comments like 'I see what you did there', 'you're on a roll', or talk about the conversation itself unless the user explicitly asks about it. "
                "Just answer the request directly and relevantly. Be precise about numbers and categories the user mentioned."
            ),
            temperature=0.3,
        )

    if word_count <= 8 and ("?" in user_input or text.startswith(("what", "who", "when", "where", "which"))):
        return ResponseProfile(
            style="concise",
            max_tokens=192,
            system_prompt="Give a direct concise answer. 1-2 sentences maximum.",
            temperature=0.25,
        )

    if word_count <= 15:
        return ResponseProfile(
            style="balanced",
            max_tokens=384,
            system_prompt=(
                "Be helpful and concise. Match response length to question complexity. "
                "Avoid filler like 'Sure!' or 'Here is'."
            ),
            temperature=0.35,
        )

    return ResponseProfile(
        style="detailed",
        max_tokens=1024,
        system_prompt=(
            "Answer the specific question only. "
            "Use short paragraphs separated by blank lines. For code use ``` fenced blocks and keep exact indentation and newlines intact. "
            "Provide complete answers and full code examples without truncating."
        ),
        temperature=0.4,
    )


def _looks_like_continuation(current: str, previous: str) -> bool:
    """Heuristic: does the current short input seem related to the previous request?"""
    cur = current.lower().strip()
    prev = previous.lower().strip()

    if len(cur) > 20:
        return False  # long input is probably a new topic

    # Shared keywords or the current input is very short + numeric/symbolic
    prev_keywords = set(re.findall(r"[a-z]{4,}", prev))
    cur_keywords = set(re.findall(r"[a-z]{4,}", cur))

    if prev_keywords & cur_keywords:
        return True

    # Pure ratings, numbers, "more", "the others" etc. after a substantive request
    if len(cur) <= 8 and any(ch.isdigit() or ch in "+-*/%/" for ch in cur):
        return True

    if any(w in cur for w in ("more", "again", "other", "bad", "good", "list", "the")):
        return True

    return False


def trim_context_messages(messages: list[dict], max_messages: int = 6) -> list[dict]:
    """Keep recent conversation context small to save tokens.

    Tries to preserve the very first user request (the original topic) + the most recent turns.
    This helps small models stay on topic during follow-ups.
    """
    if len(messages) <= max_messages:
        return messages

    # Find the first user message (original topic)
    first_user_idx = None
    for i, m in enumerate(messages):
        if m.get("role") == "user":
            first_user_idx = i
            break

    if first_user_idx is None:
        return messages[-max_messages:]

    # Always keep the first user turn + as many recent messages as possible
    kept = [messages[first_user_idx]]

    remaining_budget = max_messages - 1
    recent = messages[-(remaining_budget * 2):]  # take more to have pairs

    # Merge without duplicating the first user if it's already in recent
    for m in recent:
        if m is not kept[0]:
            kept.append(m)

    # Trim to exact max while preferring recent + the anchor
    if len(kept) > max_messages:
        # Keep first (topic) + last (max_messages-1)
        kept = [kept[0]] + kept[-(max_messages - 1):]

    return kept[-max_messages:]  # final safety trim