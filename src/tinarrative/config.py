"""Runtime settings: thresholds and windows of the narrative rules, the narrator's budget and provider, the workers.

A TOML file mirrors the dataclasses below and names only the keys it changes. Validation is strict (``bool`` is not
a number, an integer is a valid float); keys in docs/configuration.md, evidence for the narrative defaults in
docs/game-data-notes/higher-level-event-sources.md.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any, cast

CONFIG_ENV_VAR = "TINARRATIVE_CONFIG"
PROVIDERS = ("anthropic", "openai", "openrouter", "ollama")
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
    "requests_per_minute",
    "tokens_per_minute",
)
"""The ``narrator`` keys a profile may set; every other key is shared by all profiles."""
_KIND = "kind"
_MINIMUM = "minimum"
_MAXIMUM = "maximum"
_CHOICES = "choices"


def _int(default: int | None, minimum: int, maximum: int | None = None) -> Any:
    return field(default=default, metadata={_KIND: "int", _MINIMUM: minimum, _MAXIMUM: maximum})


def _float(default: float | None, minimum: float) -> Any:
    return field(default=default, metadata={_KIND: "float", _MINIMUM: minimum})


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
    takeover_wave_window_days: int = _int(180, 0)
    """Takeovers by one faction starting at most this long after the first of them ended form one takeover wave."""
    takeover_wave_min_nations: int = _int(3, 2)
    """A takeover wave needs at least this many nations below ``top_gdp_nations``."""
    takeover_precursor_days: int = _int(90, 0)
    """Unrest and opinion evidence of the nation this long before the takeover is attached as its precursors."""
    ledger_window_days: int = _int(28, 0)
    """A mission charge is attached when dated this long before the effect at most (the assignment-to-outcome bound
    of ADR-0010)."""
    expansion_gap_days: int = _int(365, 0)
    """Gains of one nation chain into one expansion while each follows the previous one this soon."""
    release_window_days: int = _int(180, 0)
    """A released or breakaway nation's own events this soon after its independence are attached."""
    realignment_window_days: int = _int(365, 0)
    """Alliance and rivalry changes of one nation chain into one diplomatic realignment while each follows the
    previous one this soon."""
    realignment_min_partners: int = _int(3, 1)
    """A diplomatic realignment needs the nation to gain or lose at least this many distinct partner nations as
    allies or rivals within one chain."""
    metric_shifts_max: int = _int(12, 0)
    """A narrative event keeps at most this many ``metric_shifts`` entries: its role nations' first, then nuclear
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
    """Thresholds and windows of the nation metric narrative rules (``narrative.nation_metrics``), in game days."""

    band_hold_days: int = _int(180, 0)
    """A band crossing must still hold in the next report when that report is dated this soon after it; a later
    report cannot refute it."""
    buildup_min_armies: int = _int(2, 1)
    """A military buildup or demobilization needs a nation's standard armies to move by at least this many."""
    space_assets_window_days: int = _int(365, 0)
    """Growth of one nation's boost or mission control chains into one space program while each follows the previous
    one this soon."""
    nuclear_window_days: int = _int(365, 0)
    """Nuclear arsenal shifts of one nation chain into one arc while each follows the previous one this soon."""
    nuclear_buildup_min: int = _int(5, 1)
    """A nuclear buildup gains at least this many weapons, or half the arsenal it started from."""
    ranking_top_n: int = _int(10, 1)
    """A ranking change is a change of the top this many by a metric (at most 20, the places the analyzer reports);
    reports list this many spaceports."""


POWER_WEIGHT_TOLERANCE = 1e-3


@dataclass(frozen=True)
class PowerSettings:
    """The weights of a nation's power share (``narrative.significance.power``): its shares of world GDP, population
    and strength. They sum to 1 (within ``POWER_WEIGHT_TOLERANCE``), so the power share is still a share."""

    w_gdp: float = _float(1 / 3, 0.0)
    w_pop: float = _float(1 / 3, 0.0)
    w_str: float = _float(1 / 3, 0.0)

    def __post_init__(self) -> None:
        if abs(self.w_gdp + self.w_pop + self.w_str - 1.0) > POWER_WEIGHT_TOLERANCE:
            raise ConfigError("'narrative.significance.power' weights must sum to 1")


@dataclass(frozen=True)
class ReferenceSettings:
    """The share at which a stake leaves a score at its base (``narrative.significance.reference``), one per measure,
    and the escalation bonus of a war between nuclear-armed nations."""

    power: float = _float(0.01, 1e-6)
    """Nation power share; also the unit of every nation-scaled event type."""
    population: float = _float(0.01, 1e-6)
    """Share of world population: the territory a region or territory event moved."""
    organization: float = _float(0.01, 1e-6)
    """Organization tier² share."""
    nuclear_bonus: int = _int(5, 0, 100)
    """Points added to a war between two nations that both hold nuclear weapons."""


@dataclass(frozen=True)
class SignificanceSettings:
    """How far an event's stake may move its score from its type's base, and how stakes are measured (ADR-0011)."""

    scale_min: int = _int(-20, -100, 0)
    """The stake lowers a score by at most this many points."""
    scale_max: int = _int(15, 0, 100)
    """The stake raises a score by at most this many points."""
    tier_exponent: int = _int(2, 1)
    """An organization's stake is its tier to this power over the total of all organizations; also ranks the
    councilors of the dossier."""
    power: PowerSettings = field(default_factory=PowerSettings)
    reference: ReferenceSettings = field(default_factory=ReferenceSettings)


@dataclass(frozen=True)
class NarrativeSettings:
    geopolitics: GeopoliticsSettings = field(default_factory=GeopoliticsSettings)
    space: SpaceSettings = field(default_factory=SpaceSettings)
    nation_metrics: NationMetricsSettings = field(default_factory=NationMetricsSettings)
    significance: SignificanceSettings = field(default_factory=SignificanceSettings)


@dataclass(frozen=True)
class NarratorSettings:
    """The chapter planner and the provider of ``tinarrative narrate`` ; never changes what ``events`` builds."""

    max_input_tokens: int = _int(200_000, 1_000)
    """The estimated input of one request (system prompt, request block and chapter package) stays within this."""
    chars_per_token: float = _float(2.4, 1.0)
    """The estimate divides the serialized request's characters by this; a low value is conservative."""
    quarter_span_days: int = _int(730, 0)
    """A campaign spanning this many game days or fewer is told by quarter."""
    half_span_days: int = _int(1825, 0)
    """A longer campaign spanning this many game days or fewer is told by half year, a longer one by year."""
    recalled_narrative_events: int = _int(40, 0)
    """Each chapter is reminded of at most this many earlier ``major``-or-above narrative events (most significant, then
    most recent); 0 turns the reminder off."""
    top_economies: int = _int(10, 0)
    """A chapter's situation reports keep the nations the chapter references and this many more, the largest by
    ``GDP``."""
    provider: str | None = _str(PROVIDERS)
    """The wire format requests are sent in."""
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
    temperature: float | None = _float(None, 0.0)
    """The sampling temperature sent with each request; unset sends none."""
    timeout_seconds: int = _int(600, 1)
    """One HTTP request is abandoned after this many seconds."""
    requests_per_minute: int | None = _int(None, 1)
    """Maximum provider request attempts in any rolling 60-second window; unset is unlimited."""
    tokens_per_minute: int | None = _int(None, 1)
    """Maximum reserved request tokens in any rolling 60-second window; unset is unlimited."""
    profiles: Mapping[str, Mapping[str, Any]] = field(default_factory=dict, metadata={_KIND: "profiles"})
    """Named sets of ``PROFILE_KEYS`` values over the keys above, chosen with ``narrate --profile``."""

    def with_profile(self, name: str) -> NarratorSettings:
        """These settings with the profile ``name`` applied; raises ``KeyError`` for an unknown profile."""
        return replace(self, **self.profiles[name])


@dataclass(frozen=True)
class CouncilorSettings:
    """Selection and size of the councilor dossier of ``tinarrative councilors`` (``councilors``)."""

    rivals_per_faction: int = _int(2, 0)
    """The most prominent councilors of each other human faction that join the player's councilors."""
    min_tenure_days: int = _int(365, 0)
    """A councilor is selected only after being employed this many game days."""
    missions_per_councilor: int = _int(3, 0)
    """A player councilor's dossier keeps this many mission types, the most frequent first."""
    missions_window_years: int = _int(2, 1)
    """The dossier counts the missions resolved in this many years before the latest save."""
    article_words: int = _int(300, 1)
    """The length each article request asks for; also carried in the dossier header."""


@dataclass(frozen=True)
class ProcessingSettings:
    """How the save-input commands use the machine (``processing``); never changes what they report."""

    jobs: int | None = _int(None, 1)
    """Worker processes for surveying the saves and analyzing the intervals; unset picks a count bounded by the CPUs
    and the memory the saves need, and 1 runs everything in one process."""


@dataclass(frozen=True)
class Settings:
    narrative: NarrativeSettings = field(default_factory=NarrativeSettings)
    narrator: NarratorSettings = field(default_factory=NarratorSettings)
    councilors: CouncilorSettings = field(default_factory=CouncilorSettings)
    processing: ProcessingSettings = field(default_factory=ProcessingSettings)

    def to_dict(self) -> dict[str, Any]:
        """The settings as nested tables; unset (``None``) keys are left out."""
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
    # Keep the runtime rule objects private to the implementation. The TOML
    # surface groups player controls by their effect rather than pipeline stage.
    allowed = {"events", "llm", "councilors", "processing"}
    for key in document:
        if key not in allowed:
            raise ConfigError(f"unknown setting {key!r}")
    events = document.get("events", {})
    llm = document.get("llm", {})
    if not isinstance(events, Mapping):
        raise ConfigError("'events' must be a table")
    if not isinstance(llm, Mapping):
        raise ConfigError("'llm' must be a table")
    event_keys = {"episode_gap_days", "top_nations", "recalled_narrative_events"}
    for key in events:
        if key not in event_keys:
            raise ConfigError(f"unknown setting 'events.{key}'")
    llm_keys = set(PROFILE_KEYS) | {"profiles"}
    for key in llm:
        if key not in llm_keys:
            raise ConfigError(f"unknown setting 'llm.{key}'")
    normalized: dict[str, Any] = {
        "councilors": document.get("councilors", {}),
        "processing": document.get("processing", {}),
    }
    # One episode gap controls the related event chains.
    if events:
        gap = events.get("episode_gap_days", 365)
        top = events.get("top_nations", 10)
        recalled = events.get("recalled_narrative_events", 40)
        if isinstance(gap, bool) or not isinstance(gap, int) or gap < 0:
            raise ConfigError("'events.episode_gap_days' must be an integer at least 0")
        if isinstance(top, bool) or not isinstance(top, int) or top < 1:
            raise ConfigError("'events.top_nations' must be an integer at least 1")
        top = min(top, 20)
        normalized["narrative"] = {
            "geopolitics": {"expansion_gap_days": gap, "realignment_window_days": gap},
            "space": {"campaign_gap_days": gap},
            "nation_metrics": {"space_assets_window_days": gap, "nuclear_window_days": gap, "ranking_top_n": top},
        }
        normalized["narrator"] = {"recalled_narrative_events": recalled}
    if llm:
        normalized.setdefault("narrator", {}).update(llm)
    councilors = normalized.get("councilors", {})
    if isinstance(councilors, Mapping):
        for key in councilors:
            if key not in {"rivals_per_faction", "min_tenure_days", "article_words"}:
                raise ConfigError(f"unknown setting 'councilors.{key}'")
    try:
        return cast(Settings, _apply(DEFAULT_SETTINGS, normalized, ""))
    except ConfigError as error:
        # These runtime objects retain their historical attribute names; errors
        # always speak in the public TOML vocabulary.
        message = str(error).replace("narrator.recalled_narrative_events", "events.recalled_narrative_events")
        raise ConfigError(message.replace("narrator", "llm")) from None


def override(settings: NarratorSettings, key: str, value: Any) -> NarratorSettings:
    """``settings`` with one key replaced, validated as in a settings file; raises ``ConfigError``."""
    changed: NarratorSettings = _apply(settings, {key: value}, "llm.")
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
    maximum = metadata.get(_MAXIMUM)
    if maximum is not None and value > maximum:
        raise ConfigError(f"{dotted!r} must be at most {maximum}")
    return value


def _to_dict(settings: Any) -> dict[str, Any]:
    """Unset (``None``) keys are left out, as a TOML file leaves them out."""
    table: dict[str, Any] = {}
    if isinstance(settings, Settings):
        narrator = settings.narrator
        gap = settings.narrative.geopolitics.expansion_gap_days
        result: dict[str, Any] = {
            "events": {
                "episode_gap_days": gap,
                "top_nations": settings.narrative.nation_metrics.ranking_top_n,
                "recalled_narrative_events": narrator.recalled_narrative_events,
            },
            "llm": {},
            "councilors": {
                "rivals_per_faction": settings.councilors.rivals_per_faction,
                "min_tenure_days": settings.councilors.min_tenure_days,
                "article_words": settings.councilors.article_words,
            },
            "processing": {},
        }
        for name in PROFILE_KEYS:
            value = getattr(narrator, name)
            if value is not None:
                result["llm"][name] = value
        result["llm"]["profiles"] = {name: dict(profile) for name, profile in narrator.profiles.items()}
        if settings.processing.jobs is not None:
            result["processing"]["jobs"] = settings.processing.jobs
        return result
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
