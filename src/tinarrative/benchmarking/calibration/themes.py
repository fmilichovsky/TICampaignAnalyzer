"""The themes a calibration review reads a campaign by, from ``benchmarks/themes.toml``; evaluation tooling only."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from tinarrative.kinds.registry import KINDS

THEMES_PATH: Final = Path("benchmarks") / "themes.toml"
"""The themes file, relative to the repository root."""


class ThemesError(ValueError):
    """A themes file that is not TOML or does not follow its shape."""


@dataclass(frozen=True)
class Theme:
    """An area of a campaign its history should follow; ``event_types`` is the tool's handle on it, never complete."""

    name: str
    description: str
    event_types: tuple[str, ...]


@dataclass(frozen=True)
class ThemeFile:
    """Every theme in file order, and the event types the file explicitly places in no theme."""

    themes: tuple[Theme, ...]
    unthemed: tuple[str, ...]


@dataclass(frozen=True)
class Coverage:
    """How a themes file decides the declared event types; it decides each exactly once when every field is empty."""

    undecided: tuple[str, ...]
    """Declared types in no theme and not in the no-theme list."""
    undeclared: tuple[str, ...]
    """Listed types that are not declared."""
    doubly_decided: tuple[str, ...]
    """Types both in a theme and in the no-theme list."""

    @property
    def complete(self) -> bool:
        return not (self.undecided or self.undeclared or self.doubly_decided)


def load_themes(path: Path = THEMES_PATH) -> ThemeFile:
    """The themes of ``path``, read afresh on every call so an edit shows on the next report; raises ``ThemesError``
    on a malformed file. Whether it decides every declared type is ``coverage``."""
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ThemesError(f"{path.name}: {error}") from error
    _reject_unknown_keys(document, {"themes", "unthemed"}, "the file")
    entries = document.get("themes")
    if not isinstance(entries, list) or not entries:
        raise ThemesError("the file lists no [[themes]]")
    themes = tuple(_theme(entry, position) for position, entry in enumerate(entries, 1))
    if repeated := _repeated([theme.name for theme in themes]):
        raise ThemesError(f"theme names repeated: {', '.join(repeated)}")
    unthemed = document.get("unthemed")
    if not isinstance(unthemed, dict):
        raise ThemesError("the file has no [unthemed] list")
    _reject_unknown_keys(unthemed, {"event_types"}, "[unthemed]")
    return ThemeFile(themes, _types(unthemed.get("event_types"), "[unthemed]"))


def coverage(themes: ThemeFile) -> Coverage:
    """How ``themes`` decides every declared event type."""
    known = set(KINDS)
    themed = {event_type for theme in themes.themes for event_type in theme.event_types}
    unthemed = set(themes.unthemed)
    return Coverage(
        undecided=tuple(sorted(known - themed - unthemed)),
        undeclared=tuple(sorted((themed | unthemed) - known)),
        doubly_decided=tuple(sorted(themed & unthemed)),
    )


def _theme(entry: Any, position: int) -> Theme:
    where = f"theme {position}"
    if not isinstance(entry, dict):
        raise ThemesError(f"{where} is not a table")
    _reject_unknown_keys(entry, {"name", "description", "event_types"}, where)
    name, description = entry.get("name"), entry.get("description")
    if not isinstance(name, str) or not name.strip():
        raise ThemesError(f"{where} needs a name")
    if not isinstance(description, str) or not description.strip():
        raise ThemesError(f"theme {name!r} needs a description")
    event_types = _types(entry.get("event_types"), f"theme {name!r}")
    if not event_types:
        raise ThemesError(f"theme {name!r} lists no event types")
    return Theme(name, description.strip(), event_types)


def _types(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ThemesError(f"{where}: event_types must be a list of event types")
    if repeated := _repeated(value):
        raise ThemesError(f"{where} repeats {', '.join(repeated)}")
    return tuple(value)


def _repeated(items: Sequence[str]) -> list[str]:
    return sorted({item for item in items if items.count(item) > 1})


def _reject_unknown_keys(table: Mapping[str, Any], allowed: set[str], where: str) -> None:
    if unknown := sorted(set(table) - allowed):
        raise ThemesError(f"{where} has unknown keys: {', '.join(unknown)}")
