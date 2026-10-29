"""The HTTP transport of the providers: one JSON POST behind a small protocol, so tests replace it with a fake.

Standard library only, as the project keeps no runtime dependencies. An HTTP error status is a response like any
other; only a missing response is an exception.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
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
