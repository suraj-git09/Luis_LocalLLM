class OfflineFallback:
    """Simple fallback with no caching (cache layer fully removed to avoid stale answers)."""

    def get_response(self, user_input: str) -> str:
        return "Sorry, I could not understand that or the service is unavailable."