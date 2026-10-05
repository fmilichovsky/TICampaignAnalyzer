"""Immutable normalized snapshot of one save."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .entities import EntityRef
from .evidence import SourceLocation
from .values import FieldValue, Observed, Unknown, to_jsonable


@dataclass(frozen=True)
class EntityState:
    """Normalized state of one entity; absent fields are ``Unknown``, not defaults."""

    ref: EntityRef
    fields: tuple[tuple[str, Observed], ...] = ()
    location: SourceLocation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", tuple(sorted(self.fields, key=lambda item: item[0])))

    def get(self, name: str) -> Observed:
        for key, value in self.fields:
            if key == name:
                return value
        return Unknown()


@dataclass(frozen=True)
class CampaignMetadata:
    player_faction_name: Observed = field(default_factory=Unknown)
    difficulty: Observed = field(default_factory=Unknown)
    played_with_mods: Observed = field(default_factory=Unknown)


STATE_COLLECTIONS = ("factions", "nations", "regions", "councilors", "armies", "organizations", "technologies")
"""Every ``SaveSnapshot`` field holding entity states; extend this when adding a domain."""


def _sorted_states(states: tuple[EntityState, ...]) -> tuple[EntityState, ...]:
    return tuple(sorted(states, key=lambda state: state.ref.entity_id))


@dataclass(frozen=True)
class SaveSnapshot:
    source: str
    date: str
    game_version: str | None = None
    timestamp: datetime | None = None
    turn: int | None = None
    campaign: CampaignMetadata = field(default_factory=CampaignMetadata)
    factions: tuple[EntityState, ...] = ()
    nations: tuple[EntityState, ...] = ()
    regions: tuple[EntityState, ...] = ()
    councilors: tuple[EntityState, ...] = ()
    armies: tuple[EntityState, ...] = ()
    organizations: tuple[EntityState, ...] = ()
    technologies: tuple[EntityState, ...] = ()
    raw_metadata: tuple[tuple[str, FieldValue], ...] = ()

    def __post_init__(self) -> None:
        for name in STATE_COLLECTIONS:
            object.__setattr__(self, name, _sorted_states(getattr(self, name)))
        object.__setattr__(self, "raw_metadata", tuple(sorted(self.raw_metadata, key=lambda item: item[0])))

    def to_dict(self) -> dict[str, Any]:
        def states(items: tuple[EntityState, ...]) -> list[dict[str, Any]]:
            return [
                {
                    "id": str(state.ref.entity_id),
                    "confidence": state.ref.confidence.value,
                    "state_type": state.ref.state_type,
                    "location": state.location.to_dict() if state.location else None,
                    "fields": {name: to_jsonable(value) for name, value in state.fields},
                }
                for state in items
            ]

        return {
            "source": self.source,
            "date": self.date,
            "game_version": self.game_version,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "turn": self.turn,
            "campaign": {
                "player_faction_name": to_jsonable(self.campaign.player_faction_name),
                "difficulty": to_jsonable(self.campaign.difficulty),
                "played_with_mods": to_jsonable(self.campaign.played_with_mods),
            },
            **{name: states(getattr(self, name)) for name in STATE_COLLECTIONS},
            "raw_metadata": {key: to_jsonable(value) for key, value in self.raw_metadata},
        }
