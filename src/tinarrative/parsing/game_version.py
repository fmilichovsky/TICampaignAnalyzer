"""Game-version detection and explicit compatibility boundaries."""

from .raw_save import RawSave

SUPPORTED_SAVE_FORMATS = frozenset({"terra_invicta_json_v1"})
"""Documented envelope identifiers, not Terra Invicta release numbers."""


class UnsupportedSaveFormatError(ValueError):
    """Raised when no parser contract has been documented for a format."""


class UnsupportedGameVersionError(ValueError):
    """Raised for an explicit game build that has no documented support."""


def detect_game_version(raw_save: RawSave) -> str | None:
    value = raw_save.get("game_version")
    return str(value) if value is not None else None


def require_supported_format(format_identifier: str) -> str:
    """Return a documented format identifier or fail without guessing."""
    if format_identifier not in SUPPORTED_SAVE_FORMATS:
        known = ", ".join(sorted(SUPPORTED_SAVE_FORMATS))
        raise UnsupportedSaveFormatError(f"Unsupported save format {format_identifier!r}; supported formats: {known}.")
    return format_identifier


def require_supported_game_version(raw_save: RawSave) -> str | None:
    """Allow absent build metadata; reject every unverified explicit build."""
    version = detect_game_version(raw_save)
    if version is not None:
        raise UnsupportedGameVersionError(
            f"Unsupported Terra Invicta game version {version!r}; no explicit game build is documented as supported."
        )
    return None
