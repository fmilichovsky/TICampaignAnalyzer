"""Acceptance for the army, space and technology families over the checked-in fixture pairs."""

from collections import Counter

from tests.analyzers.support import fixture_pair
from tinarrative.analyzers import (
    MILITARY_ANALYZERS,
    SPACE_ANALYZERS,
    TECHNOLOGY_ANALYZERS,
    run_analyzers,
)
from tinarrative.model.changes import StateDiff
from tinarrative.model.events import Confidence, DateBasis, Event, SourceRole
from tinarrative.model.snapshot import SaveSnapshot

ASSET_ANALYZERS = MILITARY_ANALYZERS + SPACE_ANALYZERS + TECHNOLOGY_ANALYZERS


def run(before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> tuple[Event, ...]:
    return run_analyzers(ASSET_ANALYZERS, before, after, diff)


def ids(events: tuple[Event, ...]) -> list[str]:
    return [event.id for event in events]


def test_interval_pair_yields_the_expected_events() -> None:
    before, after, diff = fixture_pair("interval_before.json", "interval_after.json")
    events = run(before, after, diff)
    assert ids(events) == [
        "army.appeared/army:112",
        "army.region_changed/army:110",
        "army.strength_changed/army:110",
        "faction.project_completed/faction:15/Project_Fixture",
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


def test_assets_pair_covers_every_transition_once() -> None:
    before, after, diff = fixture_pair("assets_before.json", "assets_after.json")
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
    # The army's home nation (of home region 41) is context: an entity and an attribute.
    assert str(gone.attribute("home_nation").entity_id) == "nation:20"  # type: ignore[union-attr]
    assert "nation:20" in [str(ref.entity_id) for ref in gone.entities]
    # The hull is looked up in the fleet faction's designs on the side where the ship exists.
    assert by_id["ship.appeared/ship:133"].attribute("hull") == "Frigate"
    assert by_id["ship.disappeared/ship:132"].attribute("hull") == "Frigate"
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
