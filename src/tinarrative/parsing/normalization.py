"""Convert decoded saves into stable model objects."""

from ..model.snapshot import SaveSnapshot
from .raw_save import RawSave


def normalize(raw_save: RawSave) -> SaveSnapshot:
    """Normalize the minimal metadata available until game fields are mapped."""
    return SaveSnapshot(source=raw_save.source, date="unknown", game_version=raw_save.game_version)
