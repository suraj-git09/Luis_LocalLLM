from nlp.intent_classifier import IntentClassifier


def test_intent_reminder():
    classifier = IntentClassifier()
    assert classifier.predict("remind me to drink water in 5 minutes") == "reminder"


def test_intent_calculate():
    classifier = IntentClassifier()
    assert classifier.predict("calculate 10 * 2") == "calculate"


def test_intent_calculate_with_symbols_and_numbers():
    classifier = IntentClassifier()
    assert classifier.predict("what is 15 + 4 * 2") == "calculate"
    assert classifier.predict("solve 20 / 5 % 3") == "calculate"


def test_intent_general_qa():
    classifier = IntentClassifier()
    assert classifier.predict("who built the pyramids") == "general_qa"


def test_intent_health():
    classifier = IntentClassifier()
    assert classifier.predict("system health") == "health"


def test_intent_does_not_hijack_non_math_with_symbols():
    """Critical regression test: stray + - * / % must NOT force calculate intent.

    Examples that previously wrongly triggered calculator:
    - "suggest me good/bad electronic company" (contains - and /)
    - "C++ is great", "pro/con list", "2024-2025 models", "rate it 4/5"
    """
    classifier = IntentClassifier()

    bad_cases = [
        "suggest me good/bad electronic company",
        "tell me about C++",
        "pros and cons of this approach",
        "what happened in 2023-2024",
        "rate this product 4/5 stars",
        "I prefer Python over JavaScript",
        "check the PR #42-1337 status",
        "version 2.0 / 3.0 release notes",
    ]

    for case in bad_cases:
        intent = classifier.predict(case)
        assert intent == "general_qa", f"Expected general_qa for: {case!r}, got {intent!r}"