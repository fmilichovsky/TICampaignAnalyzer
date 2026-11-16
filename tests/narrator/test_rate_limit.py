"""Coverage for rolling provider request and reserved-token limits."""

from __future__ import annotations

from tests.fake_host import FakeHost, UnusedTransport
from tinarrative.narrator.rate_limit import RateLimiter, estimate_tokens


def test_request_limit_waits_for_the_rolling_window() -> None:
    host = FakeHost(UnusedTransport())
    waits: list[float] = []
    ready: list[bool] = []
    limiter = RateLimiter(
        1,
        None,
        clock=host.monotonic,
        sleep=host.sleep,
        on_wait=waits.append,
        on_ready=lambda: ready.append(True),
    )

    limiter.acquire(10)
    limiter.acquire(10)

    assert host.waits == [60.0]
    assert host.elapsed == 60.0
    assert waits == [60.0]
    assert ready == [True]


def test_token_limit_waits_until_reserved_tokens_expire() -> None:
    host = FakeHost(UnusedTransport())
    limiter = RateLimiter(None, 100, clock=host.monotonic, sleep=host.sleep)

    limiter.acquire(70)
    limiter.acquire(40)

    assert host.waits == [60.0]


def test_the_estimate_counts_characters_per_token_plus_the_output_reservation() -> None:
    assert estimate_tokens("1234", "123456", 2, 10) == 15


def test_both_limits_are_applied_together_and_unset_limits_do_not_wait() -> None:
    host = FakeHost(UnusedTransport())
    limiter = RateLimiter(2, 30, clock=host.monotonic, sleep=host.sleep)

    limiter.acquire(10)
    limiter.acquire(20)
    limiter.acquire(10)

    assert host.waits == [60.0]
    unlimited = RateLimiter(None, None, clock=host.monotonic, sleep=host.sleep)
    unlimited.acquire(1_000_000)
    assert host.waits == [60.0]
