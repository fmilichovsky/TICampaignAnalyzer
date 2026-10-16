"""Acceptance for the army, space and technology families over the checked-in fixture pairs."""

import json
from collections import Counter

import pytest

from tests.analyzers.support import fixture_pair
from tinarrative.analyzers import (
    ALL_ANALYZERS,
    MILITARY_ANALYZERS,
    SPACE_ANALYZERS,
    TECHNOLOGY_ANALYZERS,
    run_analyzers,
)
from tinarrative.analyzers.military.armies import HANDLED_LISTS as ARMY_LISTS
from tinarrative.analyzers.render import describe_event
from tinarrative.analyzers.space.fleets import HANDLED_LISTS as FLEET_LISTS
from tinarrative.analyzers.space.ships import HANDLED_LISTS as SHIP_LISTS
from tinarrative.model.changes import ChangeKind, MembershipDetail, StateDiff
from tinarrative.model.entities import EntityRef
from tinarrative.model.events import Confidence, DateBasis, Event, EventStatus, SourceRole
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.model.values import Unknown, UnknownReason

ASSET_ANALYZERS = MILITARY_ANALYZERS + SPACE_ANALYZERS + TECHNOLOGY_ANALYZERS
PAIRS = [
    ("interval_before.json", "interval_after.json"),
    ("assets_before.json", "assets_after.json"),
]
ALL_PAIRS = PAIRS + [
    ("records_before.json", "records_after.json"),
    ("politics_before.json", "politics_after.json"),
    ("wars_before.json", "wars_after.json"),
    ("aliens_before.json", "aliens_after.json"),
    ("global_values_before.json", "global_values_after.json"),
    ("notifications_before.json", "notifications_after.json"),
]
FORBIDDEN = (
    "purg", "coup", "annex", "defect", "kill", "recruit", "join", "conquer", "captur", "seiz",
    "assassin", "died", "death", "creat", "battle", "merge", "lost", "won",
)  # fmt: skip
FIELD_BACKED = {"destroy": ("destroyed", "HabDestructionLog"), "refit": ("lastRefitDate",)}
"""Words allowed only when the event's primary source is the save field that literally carries them."""
HANDLED = {(domain.value, field) for domain, field in ARMY_LISTS + FLEET_LISTS + SHIP_LISTS}


def run(before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> tuple[Event, ...]:
    return run_analyzers(ASSET_ANALYZERS, before, after, diff)


def ids(events: tuple[Event, ...]) -> list[str]:
    return [event.id for event in events]


@pytest.mark.fixture
def test_interval_pair_yields_the_expected_events() -> None:
    before, after, diff = fixture_pair(*PAIRS[0])
    events = run(before, after, diff)
    assert ids(events) == [
        "army.appeared/army:112",
        "army.region_changed/army:110",
        "army.strength_changed/army:110",
        "fleet.appeared/fleet:121",
        "fleet.docked_location_changed/fleet:120",
        "fleet.orbit_changed/fleet:120",
        "fleet.ships_changed/fleet:120/unresolved",
        "hab.tier_changed/space object:140",
        "nation.armies_changed/nation:20/army:110/removed",
        "nation.armies_changed/nation:21/army:110/added",
        "ship.fleet_changed/ship:131",
        "technology.appeared/technology:FixtureTechC",
        "technology.completed/technology:FixtureTechB",
    ]
    by_id = {event.id: event for event in events}
    moved = by_id["army.region_changed/army:110"]
    assert [(s.role, s.change.field) for s in moved.sources] == [
        (SourceRole.PRIMARY, "currentRegion"),
        (SourceRole.CORROBORATING, "armies"),
        (SourceRole.CORROBORATING, "armies"),
    ]
    assert by_id["ship.fleet_changed/ship:131"].confidence is Confidence.LOW
    assert by_id["fleet.ships_changed/fleet:120/unresolved"].confidence is Confidence.LOW
    assert by_id["technology.completed/technology:FixtureTechB"].sources[1].member == "FixtureTechB"
    assert all(event.date_basis is DateBasis.INTERVAL for event in events)


@pytest.mark.fixture
def test_assets_pair_covers_every_transition_once() -> None:
    before, after, diff = fixture_pair(*PAIRS[1])
    events = run(before, after, diff)
    assert Counter(event.event_type for event in events) == {
        "faction.hab_destruction_recorded": 2,
        "army.appeared": 1,
        "army.disappeared": 1,
        "army.region_changed": 1,
        "army.faction_changed": 1,
        "army.destroyed_changed": 1,
        "army.strength_changed": 1,
        "army.type_changed": 1,
        "nation.armies_changed": 2,
        "fleet.appeared": 1,
        "fleet.faction_changed": 1,
        "fleet.docked_location_changed": 1,
        "fleet.orbit_changed": 1,
        "fleet.parent_fleet_changed": 1,
        "fleet.in_combat_changed": 1,
        "hab.docked_fleets_changed": 1,
        "ship.appeared": 1,
        "ship.disappeared": 1,
        "ship.fleet_changed": 1,
        "ship.last_refit_date_changed": 1,
        "hab.disappeared": 1,
        "hab.faction_changed": 1,
        "hab.tier_changed": 1,
        "hab.under_assault_changed": 1,
        "technology.completed": 2,
        "technology.appeared": 1,
        "technology.disappeared": 1,
    }
    by_id = {event.id: event for event in events}
    gone = by_id["army.disappeared/army:113"]
    assert [(s.role, str(s.change.entity_id)) for s in gone.sources] == [
        (SourceRole.PRIMARY, "army:113"),
        (SourceRole.CORROBORATING, "faction:15"),
        (SourceRole.CORROBORATING, "nation:20"),
        (SourceRole.CORROBORATING, "region:41"),
    ]
    assert len(by_id["ship.fleet_changed/ship:131"].sources) == 3
    assert len(by_id["fleet.appeared/fleet:122"].sources) == 3
    recorded = by_id["faction.hab_destruction_recorded/faction:15/1"]
    assert (recorded.date, recorded.date_basis) == ("2032-05-20T00:00:00", DateBasis.RECORD)
    assert recorded.sources[0].entry is not None and recorded.sources[0].entry.path.endswith("/HabDestructionLog/1")  # type: ignore[union-attr]
    assert by_id["faction.hab_destruction_recorded/faction:15/2"].confidence is Confidence.LOW
    assert by_id["fleet.parent_fleet_changed/fleet:120"].confidence is Confidence.LOW
    assert by_id["technology.completed/technology:FixtureTechC"].attribute("side") == "after"
    assert all(event.date_basis is DateBasis.INTERVAL for event in events if "recorded" not in event.event_type)
    # churn fields changed in the fixture and must not have produced an event
    for field in ("priorRegion", "propellant_tons", "progress", "tech_progress"):
        assert not any(source.change.field == field for event in events for source in event.sources), field


@pytest.mark.fixture
@pytest.mark.parametrize(("before_name", "after_name"), PAIRS)
def test_every_event_is_evidenced_objective_and_deterministic(before_name: str, after_name: str) -> None:
    before, after, diff = fixture_pair(before_name, after_name)
    events = run(before, after, diff)
    assert events and len(ids(events)) == len(set(ids(events)))
    assert events == run(before, after, diff)
    assert json.dumps([e.to_dict() for e in events]) == json.dumps([e.to_dict() for e in run(before, after, diff)])
    changes = set(diff.changes)
    for event in events:
        assert event.status is EventStatus.OBJECTIVE
        assert event.sources and any(source.role is SourceRole.PRIMARY for source in event.sources)
        assert all(source.change in changes for source in event.sources)
        assert event.entities
        assert event.not_before == before.date
        unresolved = [
            value
            for _, value in event.attributes
            if isinstance(value, Unknown) and value.reason is UnknownReason.UNRESOLVED_REFERENCE
        ]
        assert event.confidence is (Confidence.LOW if unresolved else Confidence.HIGH)
        if event.date_basis is DateBasis.INTERVAL:
            assert event.date == after.date
        json.loads(json.dumps(event.to_dict()))


@pytest.mark.fixture
@pytest.mark.parametrize(("before_name", "after_name"), PAIRS)
def test_every_member_of_a_handled_list_is_cited(before_name: str, after_name: str) -> None:
    before, after, diff = fixture_pair(before_name, after_name)
    cited = {
        (source.change, source.member.entity_id)
        for event in run(before, after, diff)
        for source in event.sources
        if isinstance(source.member, EntityRef)
    }
    for change in diff.changes:
        if (change.domain, change.field) not in HANDLED or change.kind is not ChangeKind.MEMBERSHIP:
            continue
        assert isinstance(change.detail, MembershipDetail)
        for member in change.detail.added + change.detail.removed:
            assert isinstance(member, EntityRef) and (change, member.entity_id) in cited, (change.entity_id, member)


@pytest.mark.fixture
@pytest.mark.parametrize(("before_name", "after_name"), PAIRS)
def test_types_and_messages_never_name_a_cause_unless_the_save_field_does(before_name: str, after_name: str) -> None:
    before, after, diff = fixture_pair(before_name, after_name)
    for event in run(before, after, diff):
        text = f"{event.event_type} {describe_event(event)}".lower()
        for word in FORBIDDEN:
            assert word not in text, (event.id, word)
        for word, fields in FIELD_BACKED.items():
            if word in text:
                assert event.sources[0].role is SourceRole.PRIMARY
                assert event.sources[0].change.field in fields, (event.id, word)


@pytest.mark.fixture
@pytest.mark.parametrize(("before_name", "after_name"), ALL_PAIRS)
def test_all_families_together_never_collide(before_name: str, after_name: str) -> None:
    before, after, diff = fixture_pair(before_name, after_name)
    events = run_analyzers(ALL_ANALYZERS, before, after, diff)
    assert len(ids(events)) == len(set(ids(events)))
    assert events == tuple(sorted(events, key=lambda event: event.sort_key))
