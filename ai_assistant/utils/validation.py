import re


class InputValidationError(ValueError):
    """Raised when user input fails security validation."""


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EXCESSIVE_WHITESPACE = re.compile(r"\s{10,}")


def sanitize_text(text: str, *, max_length: int = 2000) -> str:
    if not isinstance(text, str):
        raise InputValidationError("Input must be a string.")

    cleaned = text.strip()
    if not cleaned:
        raise InputValidationError("Input cannot be empty.")

    if len(cleaned) > max_length:
        raise InputValidationError(f"Input exceeds maximum length of {max_length} characters.")

    if _CONTROL_CHARS.search(cleaned):
        raise InputValidationError("Input contains invalid control characters.")

    cleaned = _EXCESSIVE_WHITESPACE.sub(" ", cleaned)
    return cleaned


def validate_user_input(text: str, *, max_length: int = 2000) -> str:
    """Validate and return sanitized user input."""
    return sanitize_text(text, max_length=max_length)