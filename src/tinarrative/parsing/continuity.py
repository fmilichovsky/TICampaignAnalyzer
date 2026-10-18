"""The campaign identity of one save, read from the raw save without normalizing it.

The format has no campaign ID (``docs/game-data-notes/campaign-grouping.md``), so a campaign is identified by
continuity evidence: the sole human player's faction, the readable faction name, the scenario and the real-world
time the campaign was started (``TIGlobalValuesState.realWorldCampaignStart``). A save whose human player cannot be
resolved is unclassified and never grouped with another.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..identity import read_id_value
from .containers import decode_state_map
from .dates import game_datetime
from .raw_save import RawSave

CampaignIdentity = tuple[int, str | None, tuple[str | None, str | None], datetime | None]
"""Human faction reference, faction name, (master, scenario) template names, real-world start."""


@dataclass(frozen=True)
class CampaignProfile:
    """The continuity signals of one save; ``human_faction`` is ``None`` unless exactly one human player resolves."""

    human_faction: int | None
    human_players: int
    faction_name: str | None
    scenario: tuple[str | None, str | None]
    started: datetime | None

    @property
    def identity(self) -> CampaignIdentity | None:
        """Equal for saves of one campaign; ``None`` for an unclassified save."""
        if self.human_faction is None:
            return None
        return (self.human_faction, self.faction_name, self.scenario, self.started)


def _text(value: dict[str, Any], name: str) -> str | None:
    member = value.get(name)
    return member if isinstance(member, str) else None


def _first(gamestates: dict[str, Any], short_type: str) -> dict[str, Any]:
    entries = decode_state_map(gamestates, short_type)
    return entries[0].value if entries else {}


def campaign_profile(raw_save: RawSave) -> CampaignProfile:
    """Read the continuity signals; a missing singleton or member leaves its signal ``None``.

    Raises ``UnsupportedSaveShapeError`` only for a container that does not follow the documented pair shape.
    """
    gamestates: dict[str, Any] = raw_save.root["gamestates"]
    humans = [
        entry.value for entry in decode_state_map(gamestates, "TIPlayerState") if entry.value.get("isAI") is False
    ]
    factions = {entry.map_id for entry in decode_state_map(gamestates, "TIFactionState")}
    human_faction = read_id_value(humans[0].get("faction")) if len(humans) == 1 else None
    if human_faction not in factions:
        human_faction = None
    time_state = _first(gamestates, "TITimeState")
    return CampaignProfile(
        human_faction=human_faction,
        human_players=len(humans),
        faction_name=_text(_first(gamestates, "TIMetadataState"), "playerFactionName"),
        scenario=(_text(time_state, "masterMetaTemplateName"), _text(time_state, "scenarioMetaTemplateName")),
        started=game_datetime(_first(gamestates, "TIGlobalValuesState").get("realWorldCampaignStart")),
    )
