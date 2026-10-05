"""Game-version detection and explicit compatibility boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import UnsupportedGameVersionError, UnsupportedSaveFormatError

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


def detect_game_version(root: Mapping[str, Any]) -> str | None:
    value = root.get("game_version")
    return str(value) if value is not None else None


def require_supported_format(format_identifier: str) -> str:
    """Return a documented format identifier or fail without guessing."""
    if format_identifier not in SUPPORTED_SAVE_FORMATS:
        known = ", ".join(sorted(SUPPORTED_SAVE_FORMATS))
        raise UnsupportedSaveFormatError(f"Unsupported save format {format_identifier!r}; supported formats: {known}.")
    return format_identifier


def require_supported_game_version(root: Mapping[str, Any]) -> str | None:
    """Allow absent build metadata; reject every unverified explicit build."""
    version = detect_game_version(root)
    if version is not None:
        raise UnsupportedGameVersionError(
            f"Unsupported Terra Invicta game version {version!r}; no explicit game build is documented as supported."
        )
    return None
