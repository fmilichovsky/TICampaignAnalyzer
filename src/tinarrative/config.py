"""Runtime settings: the thresholds and windows of the narrative rules and the narrator's budget and provider, with
their defaults in code.

A settings file is TOML whose tables mirror the dataclasses below (``[narrative.geopolitics]``,
``[narrative.space]``, ``[narrator]``, plus named ``[narrator.profiles.<name>]`` tables); a file names only the keys
it changes, and every other key keeps its default. Validation is strict: an unknown table or key, a value of the wrong
type (``bool`` is not a number here, an integer is a valid float), a string outside its choices or a value below its
minimum is a ``ConfigError``. The CLI resolves the file from ``--config``, then
``CONFIG_ENV_VAR``, then uses ``DEFAULT_SETTINGS`` (``docs/configuration.md``). Each default states its rule; the
evidence behind the narrative rules' defaults is in the game-data notes (``higher-level-event-sources.md``,
*Narrative rules (geopolitics)* and *Narrative rules (space)*).
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any

CONFIG_ENV_VAR = "TINARRATIVE_CONFIG"
PROVIDERS = ("anthropic", "openai", "ollama")
PROFILE_KEYS = (
    "provider",
    "model",
    "base_url",
    "api_key_env",
    "max_input_tokens",
    "max_output_tokens",
    "chars_per_token",
    "context_window",
    "temperature",
    "timeout_seconds",
)
"""The ``narrator`` keys a profile may set; every other key is shared by all profiles."""
_KIND = "kind"
_MINIMUM = "minimum"
_CHOICES = "choices"


def _int(default: int | None, minimum: int) -> Any:
    return field(default=default, metadata={_KIND: "int", _MINIMUM: minimum})


def _float(minimum: float) -> Any:
    return field(default=None, metadata={_KIND: "float", _MINIMUM: minimum})


def _str(choices: tuple[str, ...] | None = None) -> Any:
    return field(default=None, metadata={_KIND: "str", _CHOICES: choices})


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
    metric_shifts_max: int = _int(12, 0)
    """A development keeps at most this many ``metric_shifts`` entries: its role nations' first, then nuclear
    weapons, then the largest relative change; the rest are counted as ``metric_shifts_omitted``."""


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
class NationMetricsSettings:
    """Windows of the nation metric narrative rules (``narrative.nation_metrics``), in game days."""

    band_hold_days: int = _int(180, 0)
    """A band crossing must still hold in the next report when that report is dated this soon after it; a later
    report cannot refute it."""


@dataclass(frozen=True)
class NarrativeSettings:
    geopolitics: GeopoliticsSettings = field(default_factory=GeopoliticsSettings)
    space: SpaceSettings = field(default_factory=SpaceSettings)
    nation_metrics: NationMetricsSettings = field(default_factory=NationMetricsSettings)


@dataclass(frozen=True)
class NarratorSettings:
    """The chapter planner and the provider of ``tinarrative narrate`` (``narrator``, architecture 20.3 and 20.5);
    never changes what ``events`` builds. An unset optional key is ``None``."""

    max_input_tokens: int = _int(200_000, 1_000)
    """The estimated input of one request, system prompt, request block and chapter package together, stays within
    this many tokens."""
    chars_per_token: int = _int(3, 1)
    """The estimate divides the serialized request's characters by this; a low value is conservative."""
    quarter_span_days: int = _int(730, 0)
    """A campaign spanning this many game days or fewer is told by quarter."""
    half_span_days: int = _int(1825, 0)
    """A longer campaign spanning this many game days or fewer is told by half year, a longer one by year."""
    recalled_developments: int = _int(40, 0)
    """Each chapter is reminded of at most this many developments of earlier chapters (``major`` and above, the most
    significant and then the most recent kept, the rest counted), so the model can refer back without retelling
    them; 0 turns the reminder off."""
    top_economies: int = _int(10, 0)
    """A chapter's situation reports keep the nations the chapter references and this many more, the largest by
    ``GDP``."""
    provider: str | None = _str(PROVIDERS)
    """The wire format requests are sent in: the Anthropic Messages API, OpenAI Chat Completions or Ollama's chat
    API."""
    model: str | None = _str()
    """The model every request names; there is no default, so a stale model ID is never sent."""
    base_url: str | None = _str()
    """The provider's API root; unset gives the provider's public endpoint (Ollama: the local server)."""
    api_key_env: str | None = _str()
    """The name of the environment variable holding the API key; the key itself is never a setting."""
    max_output_tokens: int = _int(16_000, 1)
    """One request's completion stops at this many tokens; a completion that reaches it fails its chapter."""
    context_window: int | None = _int(None, 1)
    """The model's context window, when stated: ``max_input_tokens`` plus ``max_output_tokens`` above it is
    rejected before sending."""
    temperature: float | None = _float(0.0)
    """The sampling temperature sent with each request; unset sends none."""
    timeout_seconds: int = _int(600, 1)
    """One HTTP request is abandoned after this many seconds."""
    profiles: Mapping[str, Mapping[str, Any]] = field(default_factory=dict, metadata={_KIND: "profiles"})
    """Named sets of ``PROFILE_KEYS`` values over the keys above, chosen with ``narrate --profile``."""

    def with_profile(self, name: str) -> NarratorSettings:
        """These settings with the profile ``name`` applied; raises ``KeyError`` for an unknown profile."""
        return replace(self, **self.profiles[name])


@dataclass(frozen=True)
class Settings:
    narrative: NarrativeSettings = field(default_factory=NarrativeSettings)
    narrator: NarratorSettings = field(default_factory=NarratorSettings)

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


def override(settings: NarratorSettings, key: str, value: Any) -> NarratorSettings:
    """``settings`` with one key replaced, validated as in a settings file; raises ``ConfigError``."""
    changed: NarratorSettings = _apply(settings, {key: value}, "narrator.")
    return changed


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
        elif item.metadata.get(_KIND) == "profiles":
            changes[key] = _profiles(known, value, dotted)
        else:
            changes[key] = _value(item.metadata, value, dotted)
    return replace(current, **changes)


def _profiles(known: Mapping[str, Any], table: Any, dotted: str) -> dict[str, dict[str, Any]]:
    if not isinstance(table, Mapping):
        raise ConfigError(f"{dotted!r} must be a table")
    profiles: dict[str, dict[str, Any]] = {}
    for name, profile in table.items():
        if not isinstance(profile, Mapping):
            raise ConfigError(f"'{dotted}.{name}' must be a table")
        values: dict[str, Any] = {}
        for key, value in profile.items():
            if key not in PROFILE_KEYS:
                raise ConfigError(f"unknown setting '{dotted}.{name}.{key}' (a profile sets {', '.join(PROFILE_KEYS)})")
            values[key] = _value(known[key].metadata, value, f"{dotted}.{name}.{key}")
        profiles[name] = values
    return profiles


def _value(metadata: Mapping[str, Any], value: Any, dotted: str) -> Any:
    kind = metadata.get(_KIND)
    if kind == "str":
        if not isinstance(value, str) or not value:
            raise ConfigError(f"{dotted!r} must be a non-empty string")
        choices = metadata.get(_CHOICES)
        if choices is not None and value not in choices:
            raise ConfigError(f"{dotted!r} must be one of: {', '.join(choices)}")
        return value
    if kind == "float":
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ConfigError(f"{dotted!r} must be a number")
        value = float(value)
    elif isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{dotted!r} must be an integer")
    minimum = metadata.get(_MINIMUM)
    if minimum is not None and value < minimum:
        raise ConfigError(f"{dotted!r} must be at least {minimum}")
    return value


def _to_dict(settings: Any) -> dict[str, Any]:
    """Unset (``None``) keys are left out, as a TOML file leaves them out."""
    table: dict[str, Any] = {}
    for item in fields(settings):
        value = getattr(settings, item.name)
        if is_dataclass(value):
            table[item.name] = _to_dict(value)
        elif isinstance(value, Mapping):
            table[item.name] = {name: dict(entry) for name, entry in value.items()}
        elif value is not None:
            table[item.name] = value
    return table


def _flat(table: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in table.items():
        if isinstance(value, Mapping):
            flat.update(_flat(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat
