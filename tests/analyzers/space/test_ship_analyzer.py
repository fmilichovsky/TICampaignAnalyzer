"""Ship events: the fleet reference with mirrored lists, the literal refit date, presence, fleet-list leftovers."""

from tests.analyzers.support import AFTER, BEFORE, analyze, faction_ref, fleet_ref, only, ship_ref, snapshot, state
from tinarrative.analyzers.space import ShipAnalyzer
from tinarrative.analyzers.space.ships import (
    APPEARED,
    DISAPPEARED,
    FLEET_CHANGED,
    FLEET_LIST_CHANGED,
    LAST_REFIT_DATE_CHANGED,
)
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, SourceRole
from tinarrative.model.values import FrozenMap, Unknown, UnknownReason, freeze

ANALYZER = ShipAnalyzer()
SHIP = EntityDomain.SHIP
FLEET = EntityDomain.FLEET


def test_fleet_change_cites_both_ship_lists() -> None:
    before = snapshot(
        BEFORE,
        state(SHIP, "131", BEFORE, fleet=fleet_ref("121")),
        state(FLEET, "120", BEFORE, ships=()),
        state(FLEET, "121", BEFORE, ships=(ship_ref("131"),)),
    )
    after = snapshot(
        AFTER,
        state(SHIP, "131", AFTER, fleet=fleet_ref("120")),
        state(FLEET, "120", AFTER, ships=(ship_ref("131"),)),
        state(FLEET, "121", AFTER, ships=()),
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == FLEET_CHANGED and event.confidence is Confidence.HIGH
    assert [str(r.entity_id) for r in event.entities] == ["ship:131", "fleet:121", "fleet:120"]
    assert [(s.role, str(s.change.entity_id), s.member) for s in event.sources] == [
        (SourceRole.PRIMARY, "ship:131", None),
        (SourceRole.CORROBORATING, "fleet:120", ship_ref("131")),
        (SourceRole.CORROBORATING, "fleet:121", ship_ref("131")),
    ]


def test_unresolved_fleet_is_low_confidence_and_an_unresolved_list_is_a_leftover() -> None:
    unresolved_ref = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 999}))
    unresolved_list = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze([{"value": 999}]))
    before = snapshot(
        BEFORE,
        state(SHIP, "131", BEFORE, fleet=fleet_ref("120"), propellant_tons=100.0),
        state(FLEET, "120", BEFORE, ships=(ship_ref("131"),)),
    )
    after = snapshot(
        AFTER,
        state(SHIP, "131", AFTER, fleet=unresolved_ref, propellant_tons=80.0),
        state(FLEET, "120", AFTER, ships=unresolved_list),
    )
    events = analyze(ANALYZER, before, after)
    moved = only(events, FLEET_CHANGED)
    assert moved.confidence is Confidence.LOW and moved.attribute("transition") == "unresolved"
    assert len(moved.sources) == 1  # the fleet's list cannot corroborate: it is unresolved on one side
    leftover = only(events, FLEET_LIST_CHANGED)
    assert leftover.id == "fleet.ships_changed/fleet:120/unresolved" and leftover.confidence is Confidence.LOW
    assert len(events) == 2  # propellant is not an event


def test_refit_date_is_literal_and_presence_cites_the_fleet_list() -> None:
    refit = freeze({"year": 2032, "month": 5, "day": 1})
    before = snapshot(
        BEFORE,
        state(SHIP, "130", BEFORE, fleet=fleet_ref("120"), lastRefitDate=None),
        state(SHIP, "132", BEFORE, fleet=fleet_ref("120")),
        state(FLEET, "120", BEFORE, ships=(ship_ref("130"), ship_ref("132"))),
    )
    after = snapshot(
        AFTER,
        state(SHIP, "130", AFTER, fleet=fleet_ref("120"), lastRefitDate=refit),
        state(SHIP, "133", AFTER, fleet=None),
        state(FLEET, "120", AFTER, ships=(ship_ref("130"),)),
    )
    events = analyze(ANALYZER, before, after)
    refitted = only(events, LAST_REFIT_DATE_CHANGED)
    assert dict(refitted.attributes) == {"transition": "set", "before": None, "after": refit}
    assert refitted.sources[0].change.field == "lastRefitDate"  # the only evidence that may be worded "refit"
    assert [str(r.entity_id) for r in refitted.entities] == ["ship:130", "fleet:120"]
    gone = only(events, DISAPPEARED)
    assert [(s.role, str(s.change.entity_id)) for s in gone.sources] == [
        (SourceRole.PRIMARY, "ship:132"),
        (SourceRole.CORROBORATING, "fleet:120"),
    ]
    new = only(events, APPEARED)
    assert [str(r.entity_id) for r in new.entities] == ["ship:133"] and len(new.sources) == 1
    assert len(events) == 3
    assert analyze(ANALYZER, before, before) == []


def designs(*pairs: tuple[str, str]) -> FrozenMap:
    """``shipDesigns`` as the normalizer keys it: ``dataName`` -> the whole design object."""
    return FrozenMap(
        tuple(
            (name, FrozenMap((("dataName", name), ("hullName", hull), ("_displayName", "Player text"))))
            for name, hull in pairs
        )
    )


def test_presence_carries_the_hull_of_the_ship_design_and_never_the_design_name() -> None:
    faction = EntityDomain.FACTION
    before = snapshot(
        BEFORE,
        state(SHIP, "132", BEFORE, fleet=fleet_ref("121"), templateName="Design B"),
        state(FLEET, "121", BEFORE, ships=(ship_ref("132"),), faction=faction_ref("16")),
        state(faction, "16", BEFORE, shipDesigns=designs(("Design B", "Frigate"))),
    )
    after = snapshot(
        AFTER,
        state(SHIP, "133", AFTER, fleet=fleet_ref("122"), templateName="Design A"),
        state(SHIP, "134", AFTER, fleet=fleet_ref("122"), templateName="Unknown design"),
        state(FLEET, "122", AFTER, ships=(ship_ref("133"), ship_ref("134")), faction=faction_ref("15")),
        state(faction, "15", AFTER, shipDesigns=designs(("Design A", "Escort"))),
        state(faction, "16", AFTER, shipDesigns=designs(("Design B", "Frigate"))),
    )
    events = {event.id: event for event in analyze(ANALYZER, before, after)}
    assert dict(events["ship.appeared/ship:133"].attributes) == {"side": "after", "hull": "Escort"}
    assert dict(events["ship.disappeared/ship:132"].attributes) == {"side": "before", "hull": "Frigate"}
    assert dict(events["ship.appeared/ship:134"].attributes) == {"side": "after"}  # no design of that name


def test_presence_names_the_owner_of_the_ships_fleet_as_its_third_entity() -> None:
    faction = EntityDomain.FACTION
    before = snapshot(BEFORE)
    after = snapshot(
        AFTER,
        state(SHIP, "133", AFTER, fleet=fleet_ref("122"), templateName="Design A"),
        state(FLEET, "122", AFTER, ships=(ship_ref("133"),), faction=faction_ref("15")),
        state(faction, "15", AFTER, shipDesigns=designs(("Design A", "Escort"))),
    )
    events = {event.id: event for event in analyze(ANALYZER, before, after)}
    assert [str(ref.entity_id) for ref in events["ship.appeared/ship:133"].entities] == [
        "ship:133",
        "fleet:122",
        "faction:15",
    ]
