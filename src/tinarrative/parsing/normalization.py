"""Convert decoded saves into stable model objects."""

from .raw_save import RawSave
from ..model.snapshot import SaveSnapshot


def normalize(raw_save: RawSave, *, source: str) -> SaveSnapshot:
    """Normalize the minimal metadata available until game fields are mapped."""
    return SaveSnapshot(source=source, date=str(raw_save.get("date", "unknown")))
