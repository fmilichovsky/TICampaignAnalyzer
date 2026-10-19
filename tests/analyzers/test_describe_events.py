"""The message catalog: one conservative ASCII line per event type, nothing about causes."""

import json

from tests.analyzers.support import AFTER, BEFORE, fixture_pair, pair, snapshot, state
from tinarrative.analyzers import ALL_ANALYZERS, POLITICS_ANALYZERS, run_analyzers
from tinarrative.analyzers.base import Analyzer
from tinarrative.analyzers.render import describe_event
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, DateBasis, Event, EventStatus
from tinarrative.model.values import Unknown

EXPECTED_INTERVAL = {
    "Fixture CP 9 (control point:9) (Fixture Northland Union (nation:20)) controller: null "
    "-> Fixture Resistance (faction:15)",
    "Fixture CP 12 (control point:12) (Fixture Southland (nation:21), controller Fixture "
    "Servants (faction:16)) is absent from the after snapshot",
    "Fixture Councilor 102 (councilor:102) (faction Fixture Resistance (faction:15)) is "
    "present only in the after snapshot",
    "Fixture Councilor 101 (councilor:101) (faction null) is absent from the after snapshot",
    "Fixture Councilor 100 (councilor:100) (Fixture Resistance (faction:15)) location: "
    'Fixture North (region:40) -> unknown (unresolved_reference, raw={"$type": '
    '"PavonisInteractive.TerraInvicta.TIRegionState", "value": 999})',
    "Fixture Resistance (faction:15) councilors list: -Fixture Councilor 101 (councilor:101)",
    "Fixture Federation (federation:80) members: +Fixture Northland Union (nation:20)",
    "Fixture Northland Union (nation:20) and Fixture Southland (nation:21): allies entry "
    "removed (listed by Fixture Northland Union (nation:20) only)",
    "Fixture Northland Union (nation:20) and Fixture Eastland (nation:22): allies entry added (listed by both)",
    "Fixture Northland Union (nation:20) GDP: 1000.0 -> 1200.0",
    "Fixture Org (organization:70) assigned councilor: Fixture Councilor 100 (councilor:100) -> null",
}

EXPECTED_RECORDS = {
    "Fixture Resistance (faction:15) records Fixture CP 9 (control point:9) as lost on 2031-04-10T00:00:00",
    "Fixture Northland (nation:20) records an executive change dated 2031-04-20T00:00:00: "
    "new executive Fixture Resistance (faction:15) (previously null)",
}

EXPECTED_POLITICS = {
    "Fixture Servants (faction:16) records Fixture CP 9 (control point:9) as lost on 2032-02-15T00:00:00",
    "Fixture Northland (nation:20) records an executive change dated 2032-02-15T00:00:00: "
    "new executive Fixture Resistance (faction:15) (previously Fixture Servants "
    "(faction:16))",
    "Fixture CP 10 (control point:10) (Fixture Northland (nation:20)) controller: Fixture "
    "Resistance (faction:15) -> null",
    "Fixture CP 9 (control point:9) (Fixture Northland (nation:20)) controller: Fixture "
    "Servants (faction:16) -> Fixture Resistance (faction:15); loss recorded by Fixture "
    "Servants (faction:16) on 2032-02-15T00:00:00",
    "Fixture CP 11 (control point:11) nation: Fixture Southland (nation:21) -> Fixture Northland (nation:20)",
    "Fixture Councilor 100 (councilor:100) (Fixture Servants (faction:16)) detaining "
    "faction: null -> Fixture Servants (faction:16)",
    "Fixture Councilor 100 (councilor:100) faction: Fixture Resistance (faction:15) -> Fixture Servants (faction:16)",
    "Fixture Councilor 102 (councilor:102) faction: Fixture Servants (faction:16) -> null",
    "Fixture Councilor 101 (councilor:101) (null) location: Fixture North (region:40) -> "
    "Fixture Hab 140 (space object:140)",
    'Fixture Councilor 100 (councilor:100) (Fixture Servants (faction:16)) status: "Available" -> "FixtureStatusB"',
    "Fixture Resistance (faction:15) councilors list: [Fixture Councilor 100 "
    '(councilor:100)] -> unknown (unresolved_reference, raw=[{"value": 999}])',
    "Fixture Eastland (nation:22) breakaway parent: null -> Fixture Northland (nation:20)",
    "Fixture Northland (nation:20) capital: Fixture North (region:40) -> Fixture East (region:41)",
    "Fixture Eastland (nation:22) controlPoints list: +Fixture CP 10 (control point:10)",
    "Fixture Northland (nation:20) and Fixture Southland (nation:21): rivals entry removed "
    "(listed by Fixture Northland (nation:20) only)",
    "Fixture Northland (nation:20) and Fixture Southland (nation:21): wars entry added (listed by both)",
    "Fixture South (region:42) nation: Fixture Southland (nation:21) -> Fixture Northland (nation:20)",
}

EXPECTED_INTERVAL_ASSETS = {
    "Fixture Megafauna (army:112) (faction Fixture Servants (faction:16), region Fixture "
    "East (region:41)) is present only in the after snapshot (megafauna)",
    "Fixture Army (army:110) (Fixture Resistance (faction:15)) region: Fixture North "
    "(region:40) -> Fixture South (region:42)",
    "Fixture Army (army:110) (Fixture Resistance (faction:15)) strength: 3.5 -> 2.0",
    "Fixture Fleet 121 (fleet:121) (faction Fixture Resistance (faction:15)) is present only in the after snapshot",
    "Fixture Fleet 120 (fleet:120) (Fixture Resistance (faction:15)) docked location: null "
    "-> Fixture Hab 140 (space object:140)",
    "Fixture Fleet 120 (fleet:120) (Fixture Resistance (faction:15)) orbit: space object:61 -> null",
    "Fixture Fleet 120 (fleet:120) ships list: [Fixture Ship 130 (ship:130), Fixture Ship "
    '131 (ship:131)] -> unknown (unresolved_reference, raw=[{"value": 130}, {"value": 999}])',
    "Fixture Hab 140 (space object:140) (Fixture Resistance (faction:15)) tier: 1 -> 2",
    "Fixture Northland Union (nation:20) armies list: -Fixture Army (army:110)",
    "Fixture Southland (nation:21) armies list: +Fixture Army (army:110)",
    "Fixture Ship 131 (ship:131) fleet: Fixture Fleet 120 (fleet:120) -> unknown "
    '(unresolved_reference, raw={"value": 999})',
    "technology:FixtureTechC (finished false) is present only in the after snapshot",
    "technology:FixtureTechB is listed as finished",
}

EXPECTED_ASSETS = {
    "Fixture Resistance (faction:15) records a hab destruction dated 2032-05-20T00:00:00: "
    'type "Base" at Fixture Body (space body:50) by Fixture Servants (faction:16)',
    "Fixture Resistance (faction:15) records a hab destruction dated 2032-06-02T00:00:00: "
    'type "Base" at unknown (unresolved_reference, raw={"value": 998}) by null',
    "Fixture Megafauna (army:112) (faction Fixture Servants (faction:16), region Fixture "
    "East (region:41)) is present only in the after snapshot (megafauna)",
    "Fixture ArmyState 111 (army:111) (Fixture Servants (faction:16)) destroyed flag: false -> true",
    "Fixture ArmyState 113 (army:113) (faction Fixture Resistance (faction:15), region "
    "Fixture East (region:41)) is absent from the after snapshot",
    "Fixture ArmyState 111 (army:111) (in Fixture North (region:40)) faction: Fixture "
    "Resistance (faction:15) -> Fixture Servants (faction:16)",
    "Fixture ArmyState 110 (army:110) (Fixture Resistance (faction:15)) region: Fixture "
    "North (region:40) -> Fixture South (region:42)",
    "Fixture ArmyState 110 (army:110) (Fixture Resistance (faction:15)) strength: 3.5 -> 2.0",
    'Fixture ArmyState 111 (army:111) (Fixture Servants (faction:16)) type: "FixtureInfantry" -> "FixtureArmor"',
    "Fixture SpaceFleetState 122 (fleet:122) (faction Fixture Resistance (faction:15)) is "
    "present only in the after snapshot",
    "Fixture SpaceFleetState 120 (fleet:120) (Fixture Resistance (faction:15)) docked "
    "location: null -> Fixture HabState 140 (space object:140)",
    "Fixture SpaceFleetState 121 (fleet:121) faction: Fixture Resistance (faction:15) -> Fixture Servants (faction:16)",
    "Fixture SpaceFleetState 121 (fleet:121) (Fixture Servants (faction:16)) in-combat flag: false -> true",
    "Fixture SpaceFleetState 120 (fleet:120) (Fixture Resistance (faction:15)) orbit: "
    "space object:60 -> space object:62",
    "Fixture SpaceFleetState 120 (fleet:120) (Fixture Resistance (faction:15)) parent "
    'fleet: null -> unknown (unresolved_reference, raw={"value": 999})',
    "Fixture HabState 141 (space object:141) (faction Fixture Resistance (faction:15)) is "
    "absent from the after snapshot",
    "Fixture HabState 140 (space object:140) dockedFleets list: +Fixture SpaceFleetState 121 (fleet:121)",
    "Fixture HabState 140 (space object:140) faction: Fixture Servants (faction:16) -> Fixture Resistance (faction:15)",
    "Fixture HabState 140 (space object:140) (Fixture Resistance (faction:15)) tier: 1 -> 2",
    "Fixture HabState 140 (space object:140) (Fixture Resistance (faction:15)) under-assault flag: false -> true",
    "Fixture Northland (nation:20) armies list: -Fixture ArmyState 110 (army:110)",
    "Fixture Southland (nation:21) armies list: +Fixture ArmyState 110 (army:110)",
    "Fixture SpaceShipState 133 (ship:133) (fleet Fixture SpaceFleetState 122 (fleet:122)) "
    "is present only in the after snapshot",
    "Fixture SpaceShipState 132 (ship:132) (fleet Fixture SpaceFleetState 121 (fleet:121)) "
    "is absent from the after snapshot",
    "Fixture SpaceShipState 131 (ship:131) fleet: Fixture SpaceFleetState 121 (fleet:121) "
    "-> Fixture SpaceFleetState 120 (fleet:120)",
    "Fixture SpaceShipState 130 (ship:130) (fleet Fixture SpaceFleetState 120 (fleet:120)) "
    'last refit date: null -> {"day": 1, "hour": 0, "millisecond": 0, "minute": 0, "month": 5, '
    '"second": 0, "year": 2032}',
    "technology:FixtureTechE (finished false) is present only in the after snapshot",
    "technology:FixtureTechB is listed as finished",
    "technology:FixtureTechC is listed as finished (no earlier research state)",
    "technology:FixtureTechD (finished true) is absent from the after snapshot",
}

EXPECTED_WARS = {
    "Fixture War 92 (war:92) (Fixture Nation 23 (nation:23), Fixture Nation 25 "
    "(nation:25)) is present only in the after snapshot; start date 2032-02-20T00:00:00",
    'Fixture War 90 (war:90) date of last fighting: "2031-12-10T00:00:00" -> "2032-03-15T00:00:00"',
    "Fixture Federation (federation:80) members: +Fixture Nation 20 (nation:20)",
    "Fixture Federation (federation:80) members: -Fixture Nation 25 (nation:25)",
    "Fixture Nation 21 (nation:21) and Fixture Nation 24 (nation:24): wars entry added "
    "(listed by Fixture Nation 24 (nation:24) only)",
    "Fixture War 90 (war:90) attacking side: +Fixture Nation 22 (nation:22)",
    "Fixture War 91 (war:91) (Fixture Nation 22 (nation:22), Fixture Nation 23 "
    "(nation:23)) is absent from the after snapshot",
}


def lines(before_name: str, after_name: str, analyzers: tuple[Analyzer, ...] = POLITICS_ANALYZERS) -> set[str]:
    before, after, diff = fixture_pair(before_name, after_name)
    return {describe_event(event) for event in run_analyzers(analyzers, before, after, diff)}


def test_every_politics_event_type_has_a_template() -> None:
    assert lines("interval_before.json", "interval_after.json") == EXPECTED_INTERVAL
    assert lines("records_before.json", "records_after.json") == EXPECTED_RECORDS
    assert lines("politics_before.json", "politics_after.json") == EXPECTED_POLITICS
    assert lines("wars_before.json", "wars_after.json") == EXPECTED_WARS
    assert all(line.isascii() for line in EXPECTED_INTERVAL | EXPECTED_RECORDS | EXPECTED_POLITICS | EXPECTED_WARS)


def test_every_asset_event_type_has_a_template() -> None:
    assert (
        lines("interval_before.json", "interval_after.json", ALL_ANALYZERS)
        == EXPECTED_INTERVAL | EXPECTED_INTERVAL_ASSETS
    )
    assert lines("assets_before.json", "assets_after.json", ALL_ANALYZERS) == EXPECTED_ASSETS
    assert all(line.isascii() for line in EXPECTED_INTERVAL_ASSETS | EXPECTED_ASSETS)
    assert "destroyed" not in " ".join(line for line in EXPECTED_ASSETS if "absent" in line)


def test_the_recorded_cause_is_carried_as_an_attribute_but_never_said() -> None:
    before, after, diff = fixture_pair("records_before.json", "records_after.json")
    (event,) = [e for e in run_analyzers(POLITICS_ANALYZERS, before, after, diff) if "executive" in e.event_type]
    assert event.attribute("cause") == "Coup"
    assert "Coup" not in describe_event(event) and "coup" not in event.event_type


def test_unknown_event_types_fall_back_to_type_and_entities_and_escape_non_ascii() -> None:
    before, after, diff = pair(
        snapshot(BEFORE, state(EntityDomain.NATION, "20", BEFORE, GDP=1.0)),
        snapshot(AFTER, state(EntityDomain.NATION, "20", AFTER, GDP=2.0)),
    )
    event = Event(
        id="x",
        event_type="army.fixture_unknown",
        status=EventStatus.OBJECTIVE,
        confidence=Confidence.HIGH,
        date=Unknown(),
        date_basis=DateBasis.INTERVAL,
        not_before=Unknown(),
        sources=(),
        entities=(after.nations[0].ref,),
        attributes=(("after", "café"),),
    )
    assert describe_event(event) == "army.fixture_unknown: Fixture nation 20 (nation:20)"
    plain = Event(**{**event.__dict__, "event_type": "nation.capital_changed", "attributes": (("after", "café"),)})
    described = describe_event(plain)
    assert described.isascii() and json.loads(described.split("-> ")[1]) == "café"
