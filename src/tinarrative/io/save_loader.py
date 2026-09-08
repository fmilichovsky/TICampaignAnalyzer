"""Load save-file bytes without interpreting their game data."""

from pathlib import Path


def load_save(path: Path) -> bytes:
    """Return a save's raw bytes; decoding belongs to :mod:`tinarrative.parsing`."""
    return path.read_bytes()
