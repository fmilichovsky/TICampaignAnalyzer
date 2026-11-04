"""Opt-in diagnostic logging: ``LEVEL logger: key=value`` lines on stderr, silent by default.

The success path must not log above INFO (the CLI promises an empty stderr), and a log must stay safe to paste
into an issue: log paths through :func:`safe_path` and save strings through :func:`shape` or :func:`excerpt`.
See docs/debugging.md.
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
TIMING_LOGGER = "tinarrative.timing"
"""Stage durations for the runtime benchmark; silent unless ``configure_logging(timing=True)``, at any level."""
TIMING_ENV_VAR = "TINARRATIVE_TIMING"
LINE_FORMAT = "%(levelname)s %(name)s: %(message)s"

_BARE_VALUE = re.compile(r"^[\w./:+~-]+$")
_TIMING_OFF = logging.CRITICAL + 1
_handler: logging.Handler | None = None
logging.getLogger(TIMING_LOGGER).setLevel(_TIMING_OFF)


def get_logger(name: str) -> logging.Logger:
    """The logger for one module; pass ``__name__`` so lines name their origin."""
    return logging.getLogger(name)


def configure_logging(level: str, stream: TextIO | None = None, *, timing: bool = False) -> None:
    """Send package log lines at ``level`` or above to ``stream`` (default: current stderr).

    Replaces the previous call's handler, so repeated ``main()`` runs never log twice or to a stale stream. Timing
    lines are opt-in and independent of ``level``, because durations would make two runs' logs differ.
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
    logging.getLogger(TIMING_LOGGER).setLevel(logging.INFO if timing else _TIMING_OFF)


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
