"""The game settings one save records about its campaign, read from the survey containers without normalizing.

``None`` is a setting the save does not carry (``docs/game-data-notes/campaign-settings.md``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .containers import decode_state_map
from .continuity import campaign_profile_from_states

_PERCENT = re.compile(r"(\d+(?:\.\d+)?)%")


@dataclass(frozen=True)
class CampaignSettings:
    """``player_faction`` and ``factions`` are faction template names; speeds are multipliers (1.0 is 100%)."""

    player_faction: str | None = None
    difficulty: str | None = None
    custom_difficulty: bool | None = None
    scenario: str | None = None
    factions: tuple[str, ...] | None = None
    mods: bool | None = None
    alien_progression_speed: float | None = None
    research_speed: float | None = None


def _first(gamestates: dict[str, Any], short_type: str) -> dict[str, Any]:
    entries = decode_state_map(gamestates, short_type)
    return entries[0].value if entries else {}


def _text(value: dict[str, Any], name: str) -> str | None:
    member = value.get(name)
    return member if isinstance(member, str) else None


def _flag(value: dict[str, Any], name: str) -> bool | None:
    member = value.get(name)
    return member if isinstance(member, bool) else None


def _multiplier(value: dict[str, Any], name: str) -> float | None:
    match = _PERCENT.fullmatch(_text(value, name) or "")
    return float(match.group(1)) / 100 if match else None


def _player_faction(gamestates: dict[str, Any]) -> str | None:
    human = campaign_profile_from_states(gamestates).human_faction
    for entry in decode_state_map(gamestates, "TIFactionState"):
        if entry.map_id == human:
            return _text(entry.value, "templateName")
    return None


def _any_true(*flags: bool | None) -> bool | None:
    if True in flags:
        return True
    return False if False in flags else None


def campaign_settings_from_states(gamestates: dict[str, Any]) -> CampaignSettings:
    """Raises only for a malformed pair container."""
    metadata = _first(gamestates, "TIMetadataState")
    time_state = _first(gamestates, "TITimeState")
    master, scenario = _text(time_state, "masterMetaTemplateName"), _text(time_state, "scenarioMetaTemplateName")
    factions = metadata.get("selectedFactionsForScenario")
    return CampaignSettings(
        player_faction=_player_faction(gamestates),
        difficulty=_text(metadata, "difficulty"),
        custom_difficulty=_flag(metadata, "customDifficulty"),
        scenario=f"{master}/{scenario}" if master is not None and scenario is not None else None,
        factions=(
            tuple(sorted(factions))
            if isinstance(factions, list) and all(isinstance(name, str) for name in factions)
            else None
        ),
        mods=_any_true(
            _flag(metadata, "playedWithMods"),
            _flag(_first(gamestates, "TIGlobalValuesState"), "moddingUsedAnytime"),
        ),
        alien_progression_speed=_multiplier(metadata, "alienProgressionSpeed"),
        research_speed=_multiplier(metadata, "researchSpeedMultiplier"),
    )
