"""Convert decoded saves into stable model objects."""

from ..model.snapshot import SaveSnapshot
from .raw_save import RawSave


def normalize(raw_save: RawSave, *, source: str) -> SaveSnapshot:
    """Normalize the minimal metadata available until game fields are mapped."""
    return SaveSnapshot(source=source, date=str(raw_save.get("date", "unknown")))
