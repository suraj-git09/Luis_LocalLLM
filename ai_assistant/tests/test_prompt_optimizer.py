from services.prompt_optimizer import analyze_prompt, trim_context_messages


def test_code_prompt_gets_smaller_explanation_budget():
    profile = analyze_prompt("write a python code for prime numbers")
    assert profile.style == "code"
    # Coding responses now get a high token budget (1024+) to avoid mid-code truncation.
    # The exact number depends on whether "explain"/"with comments" is present.
    assert profile.max_tokens >= 1024


def test_brief_prompt_gets_tiny_budget():
    profile = analyze_prompt("what is AI? answer briefly")
    assert profile.style == "brief"
    # Brief style still gets a modest budget (we raised the floor for better UX).
    assert profile.max_tokens >= 64
    assert profile.max_tokens <= 256   # still relatively small compared to code/detailed


def test_trim_context_messages():
    messages = [{"role": "user", "content": str(i)} for i in range(10)]
    trimmed = trim_context_messages(messages, max_messages=4)
    assert len(trimmed) == 4
    # New behavior: we try to keep the *first* user message (original topic) + recent turns
    # instead of blindly taking only the last N. This helps follow-up relevance.
    assert trimmed[0]["content"] == "0"
    assert trimmed[-1]["content"] == "9"


def test_short_followup_gets_continuation_or_strong_list_profile():
    """Short ambiguous follow-ups (ratings like '5/5', 'more', 'the bad ones') after a
    substantive request should trigger strong profiles. The LLMService layer will further
    anchor them to the previous topic so small models (gemma2:2b) stay relevant.
    """
    prev = "suggest 5 good and 5 bad tech companies"

    for short in ["5/5", "5/5?", "the bad ones", "more good ones", "give exactly 5/5"]:
        prof = analyze_prompt(short, previous_user_input=prev)
        # Both "list" (good quantity instructions) and "continuation" are acceptable here.
        assert prof.style in ("continuation", "list"), f"{short} got unexpected style {prof.style}"
        assert prof.max_tokens >= 256  # we want room for proper lists of companies