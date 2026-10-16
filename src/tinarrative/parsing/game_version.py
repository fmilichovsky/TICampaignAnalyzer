"""Game-build detection and the explicit save-format boundary.

The only serialized build string is ``TIGlobalValuesState.latestSaveVersion``; saves have no top-level
``game_version`` member. ``detect_game_version`` reports that string. It is never used to accept or reject a
save: the format has stayed additive across builds, so parsing does not depend on a game build.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..identity import STATE_PREFIX
from ..log import fields, get_logger
from .errors import UnsupportedSaveFormatError

logger = get_logger(__name__)

DEFAULT_FORMAT = "terra_invicta_json_v1"
SUPPORTED_SAVE_FORMATS = frozenset({DEFAULT_FORMAT})
"""Documented envelope identifiers, not Terra Invicta release numbers."""

__all__ = [
    "DEFAULT_FORMAT",
    "SUPPORTED_SAVE_FORMATS",
    "UnsupportedSaveFormatError",
    "detect_game_version",
    "require_supported_format",
]


GLOBAL_VALUES_KEY = STATE_PREFIX + "TIGlobalValuesState"
SAVE_VERSION_FIELD = "latestSaveVersion"


def detect_game_version(root: Mapping[str, Any]) -> str | None:
    """``latestSaveVersion`` of the first ``TIGlobalValuesState`` entry when it is a string, else ``None``."""
    gamestates = root.get("gamestates")
    container = gamestates.get(GLOBAL_VALUES_KEY) if isinstance(gamestates, Mapping) else None
    entry = container[0] if isinstance(container, list) and container else None
    value = entry.get("Value") if isinstance(entry, Mapping) else None
    version = value.get(SAVE_VERSION_FIELD) if isinstance(value, Mapping) else None
    detected = version if isinstance(version, str) else None
    logger.debug("game_version detected %s", fields(source="global_values" if detected is not None else "none"))
    return detected


def require_supported_format(format_identifier: str) -> str:
    """Return a documented format identifier or fail without guessing."""
    if format_identifier not in SUPPORTED_SAVE_FORMATS:
        known = ", ".join(sorted(SUPPORTED_SAVE_FORMATS))
        raise UnsupportedSaveFormatError(f"Unsupported save format {format_identifier!r}; supported formats: {known}.")
    return format_identifier
