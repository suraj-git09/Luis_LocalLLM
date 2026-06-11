import threading
import time


class RateLimiter:
    """Simple thread-safe rate limiter for outbound API calls."""

    def __init__(self, max_calls: int, period_seconds: float):
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.period_seconds
            self._timestamps = [ts for ts in self._timestamps if ts > cutoff]

            if len(self._timestamps) >= self.max_calls:
                oldest = self._timestamps[0]
                wait_for = self.period_seconds - (now - oldest)
                if wait_for > 0:
                    time.sleep(wait_for)
                now = time.monotonic()
                cutoff = now - self.period_seconds
                self._timestamps = [ts for ts in self._timestamps if ts > cutoff]

            self._timestamps.append(time.monotonic())