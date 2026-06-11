import pytest

from commands.calculator import CalculatorCommand


@pytest.mark.asyncio
async def test_calculator_basic():
    command = CalculatorCommand()
    result = await command.execute("calculate 5 + 3", {})
    assert result == "Result: 8"


@pytest.mark.asyncio
async def test_calculator_rejects_unsafe_input():
    command = CalculatorCommand()
    result = await command.execute("calculate __import__('os').system('echo hi')", {})
    # After stripping dangerous payload there may be no expression left.
    # We should still refuse to fall through to LLM for an explicit "calculate" request.
    result_lower = (result or "").lower()
    assert any(
        phrase in result_lower for phrase in ["could not calculate", "provide a math expression", "sorry"]
    ), f"Expected rejection message, got: {result!r}"


@pytest.mark.asyncio
async def test_calculator_returns_none_for_non_math_with_symbols():
    """Calculator should be defensive: for sentence-like input with symbols but
    no explicit math intent, it should avoid returning a 'Result:' (return None
    or a rejection). This is defense-in-depth even if the classifier already
    blocked most cases.
    """
    command = CalculatorCommand()

    cases = [
        "suggest me good/bad electronic company",
        "tell me about C++",
        "pros and cons of using this",
        "what happened during 2023-2024",
        "rate the movie 4/5",
    ]

    for case in cases:
        result = await command.execute(case, {})
        result_str = result or ""
        assert "result:" not in result_str.lower(), (
            f"Calculator should not have answered with a Result for non-math: {case!r} -> {result!r}"
        )


@pytest.mark.asyncio
async def test_calculator_still_errors_on_malformed_actual_math():
    """If it looks like math (numbers + operators) but is invalid, give the friendly error."""
    command = CalculatorCommand()
    result = await command.execute("calculate 5 + apple", {})
    assert "could not calculate" in result.lower()