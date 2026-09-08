"""Discover candidate save files."""

from pathlib import Path


def discover_saves(directory: Path) -> list[Path]:
    """Return files in a deterministic order until save naming is understood."""
    return sorted(path for path in directory.iterdir() if path.is_file())
