"""Process-edge resources used by commands that send provider requests."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import Message
from typing import Protocol


@dataclass(frozen=True)
class HttpResponse:
    """Header names are lower case."""

    status: int
    headers: Mapping[str, str]
    body: bytes


class TransportError(Exception):
    """No response arrived."""

    def __init__(self, reason: str, *, timeout: bool) -> None:
        super().__init__(reason)
        self.timeout = timeout


class Transport(Protocol):
    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> HttpResponse:
        """Raises ``TransportError`` when no response arrives."""
        ...


class UrllibTransport:
    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> HttpResponse:
        request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return HttpResponse(response.status, _headers(response.headers), response.read())
        except urllib.error.HTTPError as error:
            return HttpResponse(error.code, _headers(error.headers), error.read())
        except urllib.error.URLError as error:
            timeout_hit = isinstance(error.reason, TimeoutError)
            raise TransportError(str(error.reason), timeout=timeout_hit) from None
        except TimeoutError:
            raise TransportError("timed out", timeout=True) from None
        except OSError as error:
            raise TransportError(str(error) or type(error).__name__, timeout=False) from None


def _headers(message: Message) -> dict[str, str]:
    return {name.lower(): value for name, value in message.items()}


@dataclass(frozen=True)
class Host:
    """Clock, wait and HTTP resources supplied at the process edge."""

    now: Callable[[], datetime]
    monotonic: Callable[[], float]
    sleep: Callable[[float], None]
    transport: Transport

    @classmethod
    def real(cls) -> Host:
        """Build the standard library resources for a real command run."""
        return cls(lambda: datetime.now(UTC), time.monotonic, time.sleep, UrllibTransport())
