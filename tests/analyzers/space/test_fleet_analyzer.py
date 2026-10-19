"""Fleet events: faction and docking with mirrored lists, orbit, parent fleet, combat flag, presence, leftovers."""

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    analyze,
    faction_ref,
    fleet_ref,
    hab_ref,
    named,
    only,
    ref,
    snapshot,
    state,
)
from tinarrative.analyzers.space import FleetAnalyzer
from tinarrative.analyzers.space.fleets import (
    APPEARED,
    DISAPPEARED,
    DOCKED_LIST_CHANGED,
    DOCKED_LOCATION_CHANGED,
    FACTION_CHANGED,
    IN_COMBAT_CHANGED,
    ORBIT_CHANGED,
    PARENT_FLEET_CHANGED,
)
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, SourceRole
from tinarrative.model.values import Unknown, UnknownReason, freeze

ANALYZER = FleetAnalyzer()
FLEET = EntityDomain.FLEET
FACTION = EntityDomain.FACTION
HAB = EntityDomain.SPACE_OBJECT


def test_faction_and_docking_changes_cite_the_mirroring_lists() -> None:
    before = snapshot(
        BEFORE,
        state(FLEET, "120", BEFORE, faction=faction_ref("15"), dockedLocation=None),
        state(FACTION, "15", BEFORE, fleets=(fleet_ref("120"),)),
        state(FACTION, "16", BEFORE, fleets=()),
        state(HAB, "140", BEFORE, dockedFleets=()),
    )
    after = snapshot(
        AFTER,
        state(FLEET, "120", AFTER, faction=faction_ref("16"), dockedLocation=hab_ref("140")),
        state(FACTION, "15", AFTER, fleets=()),
        state(FACTION, "16", AFTER, fleets=(fleet_ref("120"),)),
        state(HAB, "140", AFTER, dockedFleets=(fleet_ref("120"),)),
    )
    events = analyze(ANALYZER, before, after)
    assert [event.event_type for event in events] == [FACTION_CHANGED, DOCKED_LOCATION_CHANGED]
    faction, docked = events
    assert [(s.role, str(s.change.entity_id), s.change.field) for s in faction.sources] == [
        (SourceRole.PRIMARY, "fleet:120", "faction"),
        (SourceRole.CORROBORATING, "faction:15", "fleets"),
        (SourceRole.CORROBORATING, "faction:16", "fleets"),
    ]
    assert [str(r.entity_id) for r in faction.entities] == ["fleet:120", "faction:15", "faction:16"]
    assert dict(docked.attributes) == {"transition": "set", "before": None, "after": named(hab_ref("140"))}
    assert [(s.role, str(s.change.entity_id), s.change.field) for s in docked.sources] == [
        (SourceRole.PRIMARY, "fleet:120", "dockedLocation"),
        (SourceRole.CORROBORATING, "space object:140", "dockedFleets"),
    ]
    assert [str(r.entity_id) for r in docked.entities] == ["fleet:120", "faction:16", "space object:140"]


def test_orbit_parent_and_combat_are_literal_with_the_faction_as_context() -> None:
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 999}))
    before = snapshot(
        BEFORE,
        state(
            FLEET, "120", BEFORE, faction=faction_ref("15"), orbitState=ref(HAB, "60"), parentFleet=None, inCombat=False
        ),
        state(HAB, "60", BEFORE),
    )
    after = snapshot(
        AFTER,
        state(FLEET, "120", AFTER, faction=faction_ref("15"), orbitState=None, parentFleet=unresolved, inCombat=True),
        state(HAB, "60", AFTER),
    )
    events = analyze(ANALYZER, before, after)
    assert [event.event_type for event in events] == [ORBIT_CHANGED, PARENT_FLEET_CHANGED, IN_COMBAT_CHANGED]
    orbit, parent, combat = events
    assert dict(orbit.attributes) == {"transition": "cleared", "before": named(ref(HAB, "60")), "after": None}
    assert [str(r.entity_id) for r in orbit.entities] == ["fleet:120", "faction:15", "space object:60"]
    assert parent.confidence is Confidence.LOW and parent.attribute("transition") == "unresolved"
    assert "merge" not in parent.event_type
    assert dict(combat.attributes) == {"transition": "changed", "before": False, "after": True}
    assert all(len(event.sources) == 1 for event in events)


def test_presence_cites_the_faction_and_hab_lists_and_unexplained_members_are_leftovers() -> None:
    before = snapshot(
        BEFORE,
        state(FLEET, "121", BEFORE, faction=faction_ref("15"), dockedLocation=None),
        state(FACTION, "15", BEFORE, fleets=(fleet_ref("121"),)),
        state(HAB, "140", BEFORE, dockedFleets=()),
    )
    after = snapshot(
        AFTER,
        state(FLEET, "122", AFTER, faction=faction_ref("15"), dockedLocation=hab_ref("140")),
        state(FACTION, "15", AFTER, fleets=(fleet_ref("122"),)),
        state(HAB, "140", AFTER, dockedFleets=(fleet_ref("122"), fleet_ref("121"))),
    )
    events = analyze(ANALYZER, before, after)
    gone = only(events, DISAPPEARED)
    assert gone.attribute("side") == "before" and "destroy" not in gone.event_type
    assert [(s.role, str(s.change.entity_id)) for s in gone.sources] == [
        (SourceRole.PRIMARY, "fleet:121"),
        (SourceRole.CORROBORATING, "faction:15"),
    ]
    new = only(events, APPEARED)
    assert [str(r.entity_id) for r in new.entities] == ["fleet:122", "faction:15", "space object:140"]
    assert [(s.role, s.change.field) for s in new.sources] == [
        (SourceRole.PRIMARY, None),
        (SourceRole.CORROBORATING, "fleets"),
        (SourceRole.CORROBORATING, "dockedFleets"),
    ]
    leftover = only(events, DOCKED_LIST_CHANGED)
    assert leftover.id == "hab.docked_fleets_changed/space object:140/fleet:121/added"
    assert len(events) == 3


def test_identical_snapshots_and_churn_fields_produce_nothing() -> None:
    before = snapshot(BEFORE, state(FLEET, "120", BEFORE, faction=faction_ref("15"), trajectory=freeze({"d": 1})))
    after = snapshot(AFTER, state(FLEET, "120", AFTER, faction=faction_ref("15"), trajectory=freeze({"d": 2})))
    assert analyze(ANALYZER, before, after) == []
    assert analyze(ANALYZER, before, before) == []
