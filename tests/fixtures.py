"""Stable lookup for checked-in test fixture files."""

from pathlib import Path


FIXTURES_ROOT = Path(__file__).parent / "fixtures"


def fixture_path(*parts: str) -> Path:
    """Return the path to a fixture addressed relative to ``tests/fixtures``."""
    path = FIXTURES_ROOT.joinpath(*parts)
    if not path.is_file():
        raise FileNotFoundError(f"Test fixture does not exist: {path}")
    return path
