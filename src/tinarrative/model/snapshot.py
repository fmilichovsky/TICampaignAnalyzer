"""Immutable normalized snapshot of one save."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from datetime import datetime
from functools import cached_property
from typing import Any

from .entities import EntityId, EntityRef
from .evidence import SourceLocation
from .records import RecordSet
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
    """Campaign-level facts from ``TIMetadataState`` and ``TITimeState``."""

    player_faction_name: Observed = field(default_factory=Unknown)
    difficulty: Observed = field(default_factory=Unknown)
    played_with_mods: Observed = field(default_factory=Unknown)
    game_time_string: Observed = field(default_factory=Unknown)
    scenario_master_template: Observed = field(default_factory=Unknown)
    scenario_template: Observed = field(default_factory=Unknown)
    selected_factions_for_scenario: Observed = field(default_factory=Unknown)

    def to_dict(self) -> dict[str, Any]:
        return {item.name: to_jsonable(getattr(self, item.name)) for item in fields(self)}


@dataclass(frozen=True)
class ResearchState:
    """``TIGlobalResearchState`` facts: the evidence behind the derived ``SaveSnapshot.technologies``."""

    finished_techs_names: Observed = field(default_factory=Unknown)
    finished_one_time_only_project_names: Observed = field(default_factory=Unknown)
    tech_progress: Observed = field(default_factory=Unknown)
    campaign_start_year: Observed = field(default_factory=Unknown)
    end_game_techs_completed_by_category: Observed = field(default_factory=Unknown)
    location: SourceLocation | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            item.name: to_jsonable(getattr(self, item.name)) for item in fields(self) if item.name != "location"
        }
        data["location"] = self.location.to_dict() if self.location else None
        return data


STATE_COLLECTIONS = (
    "factions",
    "nations",
    "regions",
    "mission_control_facilities",
    "control_points",
    "councilors",
    "missions",
    "armies",
    "fleets",
    "ships",
    "habs",
    "space_bodies",
    "organizations",
    "technologies",
    "wars",
    "federations",
    "region_alien_states",
    "global_values",
    "notification_queue",
)
"""Every ``SaveSnapshot`` field holding entity states; extend this when adding a domain."""

NORMALIZED_COLLECTION_LABELS = (
    ("factions", "factions"),
    ("nations", "nations"),
    ("regions", "regions"),
    ("mission_control_facilities", "mission control facilities"),
    ("control_points", "control points"),
    ("councilors", "councilors"),
    ("missions", "missions"),
    ("armies", "armies"),
    ("fleets", "fleets"),
    ("ships", "ships"),
    ("habs", "habs"),
    ("space_bodies", "space bodies"),
    ("organizations", "organizations"),
    ("technologies", "technologies"),
    ("wars", "wars"),
    ("federations", "federations"),
    ("region_alien_states", "region alien states"),
    ("global_values", "global values"),
    ("notification_queue", "notification queue"),
)
"""(attribute, display label) for the collections the normalizer currently fills."""


def _sorted_states(states: tuple[EntityState, ...]) -> tuple[EntityState, ...]:
    return tuple(sorted(states, key=lambda state: state.ref.entity_id.sort_key))


@dataclass(frozen=True)
class SaveSnapshot:
    """One save, normalized.

    ``date`` is the ISO-8601 game-calendar timestamp (no timezone) or ``Unknown``. ``technologies`` are
    name-keyed states derived from ``research``. ``global_values`` and ``notification_queue`` hold their
    singletons as one entity each, so their fields and records have an owner like any other entity's.
    """

    source: str
    date: Observed
    game_version: str | None = None
    timestamp: datetime | None = None
    campaign_day: Observed = field(default_factory=Unknown)
    campaign_quarter: Observed = field(default_factory=Unknown)
    campaign: CampaignMetadata = field(default_factory=CampaignMetadata)
    factions: tuple[EntityState, ...] = ()
    nations: tuple[EntityState, ...] = ()
    regions: tuple[EntityState, ...] = ()
    mission_control_facilities: tuple[EntityState, ...] = ()
    control_points: tuple[EntityState, ...] = ()
    councilors: tuple[EntityState, ...] = ()
    missions: tuple[EntityState, ...] = ()
    armies: tuple[EntityState, ...] = ()
    fleets: tuple[EntityState, ...] = ()
    ships: tuple[EntityState, ...] = ()
    habs: tuple[EntityState, ...] = ()
    space_bodies: tuple[EntityState, ...] = ()
    organizations: tuple[EntityState, ...] = ()
    technologies: tuple[EntityState, ...] = ()
    wars: tuple[EntityState, ...] = ()
    federations: tuple[EntityState, ...] = ()
    region_alien_states: tuple[EntityState, ...] = ()
    global_values: tuple[EntityState, ...] = ()
    notification_queue: tuple[EntityState, ...] = ()
    research: ResearchState = field(default_factory=ResearchState)
    records: tuple[RecordSet, ...] = ()
    raw_metadata: tuple[tuple[str, FieldValue], ...] = ()

    def __post_init__(self) -> None:
        for name in STATE_COLLECTIONS:
            object.__setattr__(self, name, _sorted_states(getattr(self, name)))
        object.__setattr__(self, "records", tuple(sorted(self.records, key=lambda record: record.sort_key)))
        object.__setattr__(self, "raw_metadata", tuple(sorted(self.raw_metadata, key=lambda item: item[0])))

    # The indexes are cached on the instance; that is sound only because a snapshot is never mutated.
    @cached_property
    def collection_index(self) -> Mapping[str, Mapping[EntityId, EntityState]]:
        """Each collection of ``STATE_COLLECTIONS``, by entity ID."""
        return {name: {state.ref.entity_id: state for state in getattr(self, name)} for name in STATE_COLLECTIONS}

    @cached_property
    def state_index(self) -> Mapping[EntityId, EntityState]:
        """Every entity state by ID, over all collections."""
        return {entity_id: state for states in self.collection_index.values() for entity_id, state in states.items()}

    @cached_property
    def record_index(self) -> Mapping[tuple[EntityId, str], RecordSet]:
        """Every record set by owner and field."""
        return {(record.owner.entity_id, record.field): record for record in self.records}

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
            "date": to_jsonable(self.date),
            "game_version": self.game_version,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "campaign_day": to_jsonable(self.campaign_day),
            "campaign_quarter": to_jsonable(self.campaign_quarter),
            "campaign": self.campaign.to_dict(),
            **{name: states(getattr(self, name)) for name in STATE_COLLECTIONS},
            "research": self.research.to_dict(),
            "records": [record.to_dict() for record in self.records],
            "raw_metadata": {key: to_jsonable(value) for key, value in self.raw_metadata},
        }
