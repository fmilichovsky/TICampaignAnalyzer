"""Game-version detection belongs here, isolated from semantic analysis."""

from .raw_save import RawSave


def detect_game_version(raw_save: RawSave) -> str | None:
    value = raw_save.get("game_version")
    return str(value) if value is not None else None
