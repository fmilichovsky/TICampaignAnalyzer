"""Load save-file bytes without interpreting their game data."""

from pathlib import Path

from ..parsing.raw_save import RawSave, parse_raw_save


def load_save(path: Path) -> bytes:
    """Return a save's raw bytes; decoding belongs to :mod:`tinarrative.parsing`."""
    return path.read_bytes()


def load_raw_save(path: Path) -> RawSave:
    """Read and validate a save; ``OSError`` for the path, ``SaveLoadError`` for the content."""
    return parse_raw_save(load_save(path), source=str(path))
