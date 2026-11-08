"""Coverage for rolling provider request and reserved-token limits."""

from __future__ import annotations

from tinarrative.narrator.rate_limit import RateLimiter, estimate_tokens


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.waits: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.now += seconds


def test_request_limit_waits_for_the_rolling_window() -> None:
    time = FakeTime()
    waits: list[float] = []
    ready: list[bool] = []
    limiter = RateLimiter(
        1, None, clock=time.clock, sleep=time.sleep, on_wait=waits.append, on_ready=lambda: ready.append(True)
    )

    limiter.acquire(10)
    limiter.acquire(10)

    assert time.waits == [60.0]
    assert time.now == 60.0
    assert waits == [60.0]
    assert ready == [True]


def test_token_limit_waits_until_reserved_tokens_expire() -> None:
    time = FakeTime()
    limiter = RateLimiter(None, 100, clock=time.clock, sleep=time.sleep)

    limiter.acquire(70)
    limiter.acquire(40)

    assert time.waits == [60.0]


def test_the_estimate_counts_characters_per_token_plus_the_output_reservation() -> None:
    assert estimate_tokens("1234", "123456", 2, 10) == 15


def test_both_limits_are_applied_together_and_unset_limits_do_not_wait() -> None:
    time = FakeTime()
    limiter = RateLimiter(2, 30, clock=time.clock, sleep=time.sleep)

    limiter.acquire(10)
    limiter.acquire(20)
    limiter.acquire(10)

    assert time.waits == [60.0]
    unlimited = RateLimiter(None, None, clock=time.clock, sleep=time.sleep)
    unlimited.acquire(1_000_000)
    assert time.waits == [60.0]
