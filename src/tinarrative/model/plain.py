"""The plain rendering mode of catalog text: names, dates and ``unknown`` without the default form's audit detail.

One switch the shared formatters consult, so no kind template carries it."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_PLAIN: ContextVar[bool] = ContextVar("plain_rendering", default=False)
_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}:\d{2}(?:\.\d+)?$")


def is_plain() -> bool:
    """Whether the surrounding block asked for the plain form."""
    return _PLAIN.get()


@contextmanager
def plain_rendering(enabled: bool) -> Iterator[None]:
    """Render catalog text in the plain form inside the block."""
    token = _PLAIN.set(enabled)
    try:
        yield
    finally:
        _PLAIN.reset(token)


def plain_timestamp(text: str) -> str:
    """``YYYY-MM-DD`` for an ISO timestamp in the plain form; anything else, and the default form, unchanged."""
    if not is_plain():
        return text
    match = _TIMESTAMP.match(text)
    return match.group(1) if match else text
