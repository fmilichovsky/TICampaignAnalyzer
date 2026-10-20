"""Runtime settings: the thresholds and windows of the narrative rules, with their defaults in code.

A settings file is TOML whose tables mirror the dataclasses below (``[narrative.geopolitics]``,
``[narrative.space]``); a file names only the keys it changes, and every other key keeps its default. Validation
is strict: an unknown table or key, a value of the wrong type (``bool`` is not an integer here) or a value below
its minimum is a ``ConfigError``. The CLI resolves the file from ``--config``, then ``CONFIG_ENV_VAR``, then uses
``DEFAULT_SETTINGS`` (``docs/configuration.md``). Each default states its rule; the evidence behind it is in the
game-data notes (``higher-level-event-sources.md``, *Narrative rules (geopolitics)* and *Narrative rules (space)*).
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any

CONFIG_ENV_VAR = "TINARRATIVE_CONFIG"
_MINIMUM = "minimum"


def _int(default: int, minimum: int) -> Any:
    return field(default=default, metadata={_MINIMUM: minimum})


class ConfigError(ValueError):
    """A settings file that is not valid TOML or does not match the settings schema; the message names the key."""


@dataclass(frozen=True)
class GeopoliticsSettings:
    """Thresholds and windows of the geopolitical narrative rules (``narrative.geopolitics``), in game days."""

    top_gdp_nations: int = _int(10, 1)
    """A takeover is ``campaign_defining`` when its nation ranks this high or higher by ``GDP`` in the report after
    the anchor's interval."""
    takeover_consolidation_days: int = _int(180, 0)
    """Control changes of one nation to the same faction this soon after the first join one takeover; its
    control-point gains are attached over the same window."""
    takeover_precursor_days: int = _int(90, 0)
    """Unrest and opinion evidence of the nation this long before the takeover is attached as its precursors."""
    ledger_window_days: int = _int(28, 0)
    """A mission charge is attached when dated this long before the effect at most (the assignment-to-outcome bound
    of architecture 11.3)."""
    expansion_gap_days: int = _int(365, 0)
    """Gains of one nation chain into one expansion while each follows the previous one this soon."""
    release_window_days: int = _int(180, 0)
    """A released or breakaway nation's own events this soon after its independence are attached."""
    transformation_window_days: int = _int(120, 0)
    """Statistic shifts of one nation this soon after the first form one transformation."""


@dataclass(frozen=True)
class SpaceSettings:
    """Thresholds and windows of the space narrative rules (``narrative.space``); windows in game days."""

    campaign_gap_days: int = _int(365, 0)
    """Battle outcomes of one killer and victim pair chain into one space campaign while each follows the previous
    one this soon."""
    colonisation_window_days: int = _int(180, 0)
    """First habs on new bodies of one faction this soon after the first form one colonisation wave."""
    buildup_min_ships: int = _int(5, 2)
    """A fleet buildup needs at least this many ships of one hull appearing for one faction in one interval."""


@dataclass(frozen=True)
class NarrativeSettings:
    geopolitics: GeopoliticsSettings = field(default_factory=GeopoliticsSettings)
    space: SpaceSettings = field(default_factory=SpaceSettings)


@dataclass(frozen=True)
class Settings:
    narrative: NarrativeSettings = field(default_factory=NarrativeSettings)

    def to_dict(self) -> dict[str, Any]:
        """The settings as nested tables, every key included."""
        return _to_dict(self)

    def differences(self, other: Settings) -> dict[str, Any]:
        """The dotted keys whose value differs from ``other`` (usually the defaults), with this value."""
        mine, theirs = _flat(self.to_dict()), _flat(other.to_dict())
        return {key: value for key, value in mine.items() if theirs.get(key) != value}


DEFAULT_SETTINGS = Settings()


def load_settings(path: Path | None) -> Settings:
    """The settings of a TOML file over the defaults; ``None`` gives the defaults.

    Raises ``OSError`` when the file cannot be read and ``ConfigError`` when it is not valid settings.
    """
    if path is None:
        return DEFAULT_SETTINGS
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"not valid TOML: {error}") from None
    except UnicodeDecodeError:
        raise ConfigError("not valid TOML: the file is not UTF-8 text") from None
    settings: Settings = _apply(DEFAULT_SETTINGS, document, "")
    return settings


def _apply(current: Any, table: Mapping[str, Any], prefix: str) -> Any:
    known = {item.name: item for item in fields(current)}
    changes: dict[str, Any] = {}
    for key, value in table.items():
        dotted = f"{prefix}{key}"
        item = known.get(key)
        if item is None:
            raise ConfigError(f"unknown setting {dotted!r}")
        default = getattr(current, key)
        if is_dataclass(default):
            if not isinstance(value, Mapping):
                raise ConfigError(f"{dotted!r} must be a table")
            changes[key] = _apply(default, value, f"{dotted}.")
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{dotted!r} must be an integer")
        minimum = item.metadata.get(_MINIMUM)
        if minimum is not None and value < minimum:
            raise ConfigError(f"{dotted!r} must be at least {minimum}")
        changes[key] = value
    return replace(current, **changes)


def _to_dict(settings: Any) -> dict[str, Any]:
    table: dict[str, Any] = {}
    for item in fields(settings):
        value = getattr(settings, item.name)
        table[item.name] = _to_dict(value) if is_dataclass(value) else value
    return table


def _flat(table: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in table.items():
        if isinstance(value, Mapping):
            flat.update(_flat(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat
