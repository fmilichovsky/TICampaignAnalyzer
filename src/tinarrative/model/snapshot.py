"""Immutable normalized snapshot of one save."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any

from .entities import EntityRef
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
    """Campaign-wide research facts from the ``TIGlobalResearchState`` singleton.

    These are the serialized collections the per-technology states are derived from; keeping both
    preserves the evidence (this object) next to the derived view (``SaveSnapshot.technologies``).
    """

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
    "control_points",
    "councilors",
    "armies",
    "fleets",
    "ships",
    "habs",
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
    ("control_points", "control points"),
    ("councilors", "councilors"),
    ("armies", "armies"),
    ("fleets", "fleets"),
    ("ships", "ships"),
    ("habs", "habs"),
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

    ``date`` is the ISO-8601 game timestamp (no timezone; game-calendar time) or ``Unknown``.
    ``campaign_day`` and ``campaign_quarter`` are the serialized turn-like counters.
    ``habs`` holds ``TIHabState`` objects (domain ``space object``); ``technologies`` are name-keyed
    states derived from ``research``; ``global_values`` holds the ``TIGlobalValuesState`` singleton as one
    in-save-ID entity, so its fields and records have an owner like any other entity's; ``notification_queue``
    holds the ``TINotificationQueueState`` singleton the same way (the owner of the notification log).
    ``records`` holds the save-carried records (dated logs and cumulative counters) of every entity, one
    ``RecordSet`` per entity and field, sorted by owner then field.
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
    control_points: tuple[EntityState, ...] = ()
    councilors: tuple[EntityState, ...] = ()
    armies: tuple[EntityState, ...] = ()
    fleets: tuple[EntityState, ...] = ()
    ships: tuple[EntityState, ...] = ()
    habs: tuple[EntityState, ...] = ()
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
