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
    "control point:9 (nation:20) controller: null -> faction:15",
    "control point:12 (nation:21, controller faction:16) is absent from the after snapshot",
    "councilor:102 (faction faction:15) is present only in the after snapshot",
    "councilor:101 (faction null) is absent from the after snapshot",
    'councilor:100 (faction:15) location: region:40 -> unknown (unresolved_reference, raw={"$type": '
    '"PavonisInteractive.TerraInvicta.TIRegionState", "value": 999})',
    "faction:15 councilors list: -councilor:101",
    "federation:80 members: +nation:20",
    "nation:20 and nation:21: allies entry removed (listed by nation:20 only)",
    "nation:20 and nation:22: allies entry added (listed by both)",
}

EXPECTED_RECORDS = {
    "faction:15 records control point:9 as lost on 2031-04-10T00:00:00",
    "nation:20 records an executive change dated 2031-04-20T00:00:00: new executive faction:15 (previously null)",
}

EXPECTED_POLITICS = {
    "control point:9 (nation:20) controller: faction:16 -> faction:15; "
    "loss recorded by faction:16 on 2032-02-15T00:00:00",
    "control point:10 (nation:20) controller: faction:15 -> null",
    "faction:16 records control point:9 as lost on 2032-02-15T00:00:00",
    "control point:11 nation: nation:21 -> nation:20",
    "region:42 nation: nation:21 -> nation:20",
    "nation:20 capital: region:40 -> region:41",
    "nation:22 breakaway parent: null -> nation:20",
    "nation:20 and nation:21: rivals entry removed (listed by nation:20 only)",
    "nation:20 and nation:21: wars entry added (listed by both)",
    "nation:22 controlPoints list: +control point:10",
    "nation:20 records an executive change dated 2032-02-15T00:00:00: new executive faction:15 (previously faction:16)",
    "councilor:100 faction: faction:15 -> faction:16",
    'councilor:100 (faction:16) status: "Available" -> "FixtureStatusB"',
    "councilor:100 (faction:16) detaining faction: null -> faction:16",
    "councilor:101 (null) location: region:40 -> space object:140",
    "councilor:102 faction: faction:16 -> null",
    'faction:15 councilors list: [councilor:100] -> unknown (unresolved_reference, raw=[{"value": 999}])',
}

EXPECTED_INTERVAL_ASSETS = {
    "army:112 (faction faction:16, region region:41) is present only in the after snapshot (megafauna)",
    "army:110 (faction:15) region: region:40 -> region:42",
    "army:110 (faction:15) strength: 3.5 -> 2.0",
    "fleet:121 (faction faction:15) is present only in the after snapshot",
    "fleet:120 (faction:15) docked location: null -> space object:140",
    "fleet:120 (faction:15) orbit: space object:61 -> null",
    "fleet:120 ships list: [ship:130, ship:131] -> unknown (unresolved_reference, "
    'raw=[{"value": 130}, {"value": 999}])',
    "space object:140 (faction:15) tier: 1 -> 2",
    "nation:20 armies list: -army:110",
    "nation:21 armies list: +army:110",
    'ship:131 fleet: fleet:120 -> unknown (unresolved_reference, raw={"value": 999})',
    "technology:FixtureTechC (finished false) is present only in the after snapshot",
    "technology:FixtureTechB is listed as finished",
}

EXPECTED_ASSETS = {
    'faction:15 records a hab destruction dated 2032-05-20T00:00:00: type "Base" at space object:50 by faction:16',
    'faction:15 records a hab destruction dated 2032-06-02T00:00:00: type "Base" at unknown (unresolved_reference, '
    'raw={"value": 998}) by null',
    "army:112 (faction faction:16, region region:41) is present only in the after snapshot (megafauna)",
    "army:111 (faction:16) destroyed flag: false -> true",
    "army:113 (faction faction:15, region region:41) is absent from the after snapshot",
    "army:111 (in region:40) faction: faction:15 -> faction:16",
    "army:110 (faction:15) region: region:40 -> region:42",
    "army:110 (faction:15) strength: 3.5 -> 2.0",
    'army:111 (faction:16) type: "FixtureInfantry" -> "FixtureArmor"',
    "fleet:122 (faction faction:15) is present only in the after snapshot",
    "fleet:120 (faction:15) docked location: null -> space object:140",
    "fleet:121 faction: faction:15 -> faction:16",
    "fleet:121 (faction:16) in-combat flag: false -> true",
    "fleet:120 (faction:15) orbit: space object:60 -> space object:62",
    'fleet:120 (faction:15) parent fleet: null -> unknown (unresolved_reference, raw={"value": 999})',
    "space object:141 (faction faction:15) is absent from the after snapshot",
    "space object:140 dockedFleets list: +fleet:121",
    "space object:140 faction: faction:16 -> faction:15",
    "space object:140 (faction:15) tier: 1 -> 2",
    "space object:140 (faction:15) under-assault flag: false -> true",
    "nation:20 armies list: -army:110",
    "nation:21 armies list: +army:110",
    "ship:133 (fleet fleet:122) is present only in the after snapshot",
    "ship:132 (fleet fleet:121) is absent from the after snapshot",
    "ship:131 fleet: fleet:121 -> fleet:120",
    'ship:130 (fleet fleet:120) last refit date: null -> {"day": 1, "hour": 0, "millisecond": 0, "minute": 0, '
    '"month": 5, "second": 0, "year": 2032}',
    "technology:FixtureTechE (finished false) is present only in the after snapshot",
    "technology:FixtureTechB is listed as finished",
    "technology:FixtureTechC is listed as finished (no earlier research state)",
    "technology:FixtureTechD (finished true) is absent from the after snapshot",
}

EXPECTED_WARS = {
    "war:92 (nation:23, nation:25) is present only in the after snapshot; start date 2032-02-20T00:00:00",
    "war:91 (nation:22, nation:23) is absent from the after snapshot",
    "war:90 attacking side: +nation:22",
    'war:90 date of last fighting: "2031-12-10T00:00:00" -> "2032-03-15T00:00:00"',
    "federation:80 members: +nation:20",
    "federation:80 members: -nation:25",
    "nation:21 and nation:24: wars entry added (listed by nation:24 only)",
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
    assert describe_event(event) == "army.fixture_unknown: nation:20"
    plain = Event(**{**event.__dict__, "event_type": "nation.capital_changed", "attributes": (("after", "café"),)})
    described = describe_event(plain)
    assert described.isascii() and json.loads(described.split("-> ")[1]) == "café"
