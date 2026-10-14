"""Opt-in diagnostic logging for the pipeline.

Every module logs through ``logger = get_logger(__name__)`` and writes one line per
decision in the form ``LEVEL logger: message key=value key=value``. Lines go to stderr
only, carry no timestamps, and are emitted only when the CLI (or a test) has called
:func:`configure_logging`; the default level, ``warning``, keeps normal runs silent.

Levels:

- ``INFO``: one line per command stage (start, done).
- ``DEBUG``: parser decisions and per-state-type aggregates. Never one line per entity;
  real saves hold tens of thousands of entries.
- ``WARNING`` and above: something the user should see without opting in. The success
  path must not log at this level, because the CLI promises an empty stderr there.

Redaction rules, so a debug log can be pasted into an issue:

- Safe verbatim: counts, byte offsets, JSON pointers, state-type and field names, map IDs,
  format identifiers, ``game_version`` strings, exception class names, and the messages
  of this package's own errors.
- Never verbatim: file paths (log :func:`safe_path`, the base name only) and any string
  value read from a save, such as a faction or player name (log :func:`shape`, or at most
  a bounded :func:`excerpt`).
"""

from __future__ import annotations

import logging
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO

ROOT_LOGGER = "tinarrative"
LEVELS: Mapping[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}
DEFAULT_LEVEL = "warning"
ENV_VAR = "TINARRATIVE_LOG_LEVEL"
LINE_FORMAT = "%(levelname)s %(name)s: %(message)s"

_BARE_VALUE = re.compile(r"^[\w./:+~-]+$")
_handler: logging.Handler | None = None


def get_logger(name: str) -> logging.Logger:
    """The logger for one module; pass ``__name__`` so lines name their origin."""
    return logging.getLogger(name)


def configure_logging(level: str, stream: TextIO | None = None) -> None:
    """Send package log lines at ``level`` or above to ``stream`` (default: current stderr).

    Calling it again replaces the handler installed by the previous call, so a process
    that runs ``main()`` several times (tests) never logs twice or to a stale stream.
    """
    global _handler
    if level not in LEVELS:
        known = ", ".join(LEVELS)
        raise ValueError(f"unknown log level {level!r}; expected one of: {known}")
    root = logging.getLogger(ROOT_LOGGER)
    if _handler is not None:
        root.removeHandler(_handler)
    _handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    _handler.setFormatter(logging.Formatter(LINE_FORMAT))
    root.addHandler(_handler)
    root.setLevel(LEVELS[level])


def fields(**values: object) -> str:
    """Render ``key=value`` pairs in call order for the tail of a log message."""
    return " ".join(f"{key}={_render(value)}" for key, value in values.items())


def _render(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value if _BARE_VALUE.match(value) else repr(value)
    return str(value)


def safe_path(path: str | os.PathLike[str]) -> str:
    """The base name of a path; directories may reveal user or machine names."""
    return Path(path).name


def shape(value: object) -> str:
    """Describe a decoded save value by JSON type and size without exposing its content."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return f"string[{len(value)}]"
    if isinstance(value, list | tuple):
        return f"array[{len(value)}]"
    if isinstance(value, Mapping):
        return f"object{{{len(value)}}}"
    return type(value).__name__


def excerpt(text: str, limit: int = 40) -> str:
    """At most ``limit`` characters of ``text`` as a quoted literal, marking what was cut."""
    if len(text) <= limit:
        return repr(text)
    return f"{text[:limit]!r}...(+{len(text) - limit} chars)"
