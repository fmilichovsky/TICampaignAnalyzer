"""A deterministic host bundle shared by narrator and CLI tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tinarrative.host import Host, Transport


class UnusedTransport:
    def post(self, url: str, headers: object, body: bytes, timeout: float) -> object:
        raise AssertionError("this test does not send HTTP requests")


class FakeHost:
    def __init__(self, transport: Transport, *, now: datetime | None = None) -> None:
        self.transport = transport
        self.wall_time = now or datetime(2030, 1, 1, tzinfo=UTC)
        self.elapsed = 0.0
        self.waits: list[float] = []

    def now(self) -> datetime:
        return self.wall_time + timedelta(seconds=self.elapsed)

    def monotonic(self) -> float:
        return self.elapsed

    def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.elapsed += seconds

    def bundle(self) -> Host:
        return Host(self.now, self.monotonic, self.sleep, self.transport)
