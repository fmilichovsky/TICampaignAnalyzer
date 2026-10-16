"""Game-version detection and explicit compatibility boundaries.

Two serialized build strings are observed: an optional top-level ``game_version`` envelope member (absent from
every inspected real save) and ``TIGlobalValuesState.latestSaveVersion`` (present in every inspected real save).
``detect_game_version`` reports the first that exists. Only the envelope member is gated by
``require_supported_game_version``: the singleton value is reported, never used to accept or reject a save.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..identity import STATE_PREFIX
from ..log import fields, get_logger
from .errors import UnsupportedGameVersionError, UnsupportedSaveFormatError

logger = get_logger(__name__)

DEFAULT_FORMAT = "terra_invicta_json_v1"
SUPPORTED_SAVE_FORMATS = frozenset({DEFAULT_FORMAT})
"""Documented envelope identifiers, not Terra Invicta release numbers."""

__all__ = [
    "DEFAULT_FORMAT",
    "SUPPORTED_SAVE_FORMATS",
    "UnsupportedGameVersionError",
    "UnsupportedSaveFormatError",
    "detect_game_version",
    "require_supported_format",
    "require_supported_game_version",
]


GLOBAL_VALUES_KEY = STATE_PREFIX + "TIGlobalValuesState"
SAVE_VERSION_FIELD = "latestSaveVersion"


def _envelope_version(root: Mapping[str, Any]) -> str | None:
    value = root.get("game_version")
    return str(value) if value is not None else None


def _global_values_version(root: Mapping[str, Any]) -> str | None:
    """``latestSaveVersion`` of the first ``TIGlobalValuesState`` entry when it is a string; never raises."""
    gamestates = root.get("gamestates")
    container = gamestates.get(GLOBAL_VALUES_KEY) if isinstance(gamestates, Mapping) else None
    entry = container[0] if isinstance(container, list) and container else None
    value = entry.get("Value") if isinstance(entry, Mapping) else None
    version = value.get(SAVE_VERSION_FIELD) if isinstance(value, Mapping) else None
    return version if isinstance(version, str) else None


def detect_game_version(root: Mapping[str, Any]) -> str | None:
    """The envelope ``game_version``, else the global-values ``latestSaveVersion``, else ``None``."""
    version = _envelope_version(root)
    if version is not None:
        logger.debug("game_version detected %s", fields(source="envelope"))
        return version
    version = _global_values_version(root)
    logger.debug("game_version detected %s", fields(source="global_values" if version is not None else "none"))
    return version


def require_supported_format(format_identifier: str) -> str:
    """Return a documented format identifier or fail without guessing."""
    if format_identifier not in SUPPORTED_SAVE_FORMATS:
        known = ", ".join(sorted(SUPPORTED_SAVE_FORMATS))
        raise UnsupportedSaveFormatError(f"Unsupported save format {format_identifier!r}; supported formats: {known}.")
    return format_identifier


def require_supported_game_version(root: Mapping[str, Any]) -> str | None:
    """Allow absent envelope build metadata; reject every unverified explicit envelope build.

    The global-values ``latestSaveVersion`` is deliberately not checked (see the module docstring).
    """
    version = _envelope_version(root)
    if version is not None:
        logger.debug("game_version present, rejected %s", fields(version=version))
        raise UnsupportedGameVersionError(
            f"Unsupported Terra Invicta game version {version!r}; no explicit game build is documented as supported."
        )
    logger.debug("game_version absent, accepted")
    return None
