"""Golden comparison: every exact-output check goes through ``assert_golden``."""

from collections.abc import Callable
from pathlib import Path

UPDATE_OPTION = "--update-goldens"

AssertGolden = Callable[[str, Path], None]
"""The ``assert_golden`` fixture: compare ``actual`` with the golden at ``path``."""


def check_golden(actual: str, path: Path, *, update: bool) -> None:
    """Assert that ``actual`` equals the golden at ``path``, or rewrite the golden when ``update`` is set."""
    if update:
        if not path.is_file() or path.read_text(encoding="utf-8") != actual:
            path.write_text(actual, encoding="utf-8", newline="")
        return
    assert path.is_file(), f"missing golden {path}; run pytest {UPDATE_OPTION}"
    assert actual == path.read_text(encoding="utf-8"), f"{path} differs; run pytest {UPDATE_OPTION} and review the diff"
