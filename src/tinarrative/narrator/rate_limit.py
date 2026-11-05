"""In-process rolling-window limits for provider request attempts."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

WINDOW_SECONDS = 60.0


class RateLimiter:
    """Pace request attempts against optional request and reserved-token limits."""

    def __init__(
        self,
        requests_per_minute: int | None,
        tokens_per_minute: int | None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        on_wait: Callable[[float], None] | None = None,
        on_ready: Callable[[], None] | None = None,
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self._clock = clock
        self._sleep = sleep
        self._on_wait = on_wait
        self._on_ready = on_ready
        self._requests: deque[tuple[float, int]] = deque()
        self._tokens = 0

    def acquire(self, tokens: int) -> None:
        """Wait until one attempt and its reserved tokens fit, then record the reservation."""
        if self.tokens_per_minute is not None and tokens > self.tokens_per_minute:
            raise ValueError("request reservation exceeds tokens_per_minute")
        waiting = False
        while True:
            now = self._clock()
            self._expire(now)
            request_limited = self.requests_per_minute is not None and len(self._requests) >= self.requests_per_minute
            token_limited = self.tokens_per_minute is not None and self._tokens + tokens > self.tokens_per_minute
            if not request_limited and not token_limited:
                if waiting and self._on_ready is not None:
                    self._on_ready()
                self._requests.append((now, tokens))
                self._tokens += tokens
                return
            oldest = self._requests[0][0]
            wait = max(oldest + WINDOW_SECONDS - now, 0.0)
            if self._on_wait is not None:
                self._on_wait(wait)
            waiting = True
            self._sleep(wait)

    def _expire(self, now: float) -> None:
        while self._requests and now - self._requests[0][0] >= WINDOW_SECONDS:
            _, tokens = self._requests.popleft()
            self._tokens -= tokens


def estimate_tokens(system: str, user: str, chars_per_token: int, max_output_tokens: int) -> int:
    """Estimate input from request text and reserve the full configured output allowance."""
    characters = len(system) + len(user)
    return (characters + chars_per_token - 1) // chars_per_token + max_output_tokens
