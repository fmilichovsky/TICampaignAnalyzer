"""Builders for synthetic snapshots and diffs used by the analyzer tests."""

from __future__ import annotations

from tests.fixtures import fixture_path
from tinarrative.analyzers.base import Analyzer
from tinarrative.diff.state_diff import diff_states
from tinarrative.io.save_loader import load_raw_save
from tinarrative.model.changes import StateDiff
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import Event
from tinarrative.model.evidence import SourceLocation
from tinarrative.model.records import RecordEntry, RecordKind, RecordSet
from tinarrative.model.snapshot import EntityState, SaveSnapshot
from tinarrative.model.values import Observed, Unknown
from tinarrative.parsing.normalization import normalize

BEFORE = "before.json"
AFTER = "after.json"
BEFORE_DATE = "2031-03-01T00:00:00"
AFTER_DATE = "2031-06-01T00:00:00"
FIXTURE_SET = "terra_invicta_json_v1"

STATE_TYPES = {
    EntityDomain.FACTION: ("TIFactionState", "factions"),
    EntityDomain.NATION: ("TINationState", "nations"),
    EntityDomain.REGION: ("TIRegionState", "regions"),
    EntityDomain.CONTROL_POINT: ("TIControlPoint", "control_points"),
    EntityDomain.COUNCILOR: ("TICouncilorState", "councilors"),
    EntityDomain.SPACE_OBJECT: ("TIHabState", "habs"),
    EntityDomain.ORGANIZATION: ("TIOrgState", "organizations"),
}


def ref(domain: EntityDomain, key: str) -> EntityRef:
    """A reference as the normalizer produces it inside a field: no display name."""
    return EntityRef(EntityId(domain, key), IdentityConfidence.IN_SAVE_ID, state_type=STATE_TYPES[domain][0])


def faction_ref(key: str) -> EntityRef:
    return ref(EntityDomain.FACTION, key)


def nation_ref(key: str) -> EntityRef:
    return ref(EntityDomain.NATION, key)


def region_ref(key: str) -> EntityRef:
    return ref(EntityDomain.REGION, key)


def point_ref(key: str) -> EntityRef:
    return ref(EntityDomain.CONTROL_POINT, key)


def councilor_ref(key: str) -> EntityRef:
    return ref(EntityDomain.COUNCILOR, key)


def state(domain: EntityDomain, key: str, save: str, **fields: Observed) -> EntityState:
    state_type, _ = STATE_TYPES[domain]
    own = EntityRef(EntityId(domain, key), IdentityConfidence.IN_SAVE_ID, state_type, f"Fixture {domain.value} {key}")
    location = SourceLocation(save, state_type, int(key), f"/gamestates/{state_type}/{key}/Value")
    return EntityState(own, tuple(fields.items()), location)


def snapshot(
    save: str, *states: EntityState, records: tuple[RecordSet, ...] = (), date: Observed = None
) -> SaveSnapshot:
    """A snapshot holding ``states`` in their collections; the date defaults by save name."""
    collections: dict[str, list[EntityState]] = {}
    for item in states:
        collections.setdefault(STATE_TYPES[item.ref.entity_id.domain][1], []).append(item)
    if date is None:
        date = BEFORE_DATE if save == BEFORE else AFTER_DATE
    return SaveSnapshot(
        source=save,
        date=date,
        records=records,
        **{name: tuple(items) for name, items in collections.items()},  # type: ignore[arg-type]
    )


def record_set(
    save: str, owner: EntityRef, field: str, kind: RecordKind, entries: tuple[RecordEntry, ...] | Unknown
) -> RecordSet:
    state_type = owner.state_type or ""
    path = f"/gamestates/{state_type}/{owner.entity_id.key}/Value/{field}"
    location = SourceLocation(save, state_type, int(owner.entity_id.key), path)
    return RecordSet(owner, field, kind, location, entries)


def pair(before: SaveSnapshot, after: SaveSnapshot) -> tuple[SaveSnapshot, SaveSnapshot, StateDiff]:
    return before, after, diff_states(before, after)


def fixture_pair(before_name: str, after_name: str) -> tuple[SaveSnapshot, SaveSnapshot, StateDiff]:
    before = normalize(load_raw_save(fixture_path("io", FIXTURE_SET, before_name)))
    after = normalize(load_raw_save(fixture_path("io", FIXTURE_SET, after_name)))
    return before, after, diff_states(before, after)


def analyze(analyzer: Analyzer, before: SaveSnapshot, after: SaveSnapshot) -> list[Event]:
    return analyzer.analyze(before, after, diff_states(before, after))


def by_type(events: list[Event] | tuple[Event, ...], event_type: str) -> list[Event]:
    return [event for event in events if event.event_type == event_type]


def only(events: list[Event] | tuple[Event, ...], event_type: str) -> Event:
    matches = by_type(events, event_type)
    assert len(matches) == 1, [event.id for event in events]
    return matches[0]
