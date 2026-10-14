"""The message catalog: one conservative ASCII line per event type, nothing about causes."""

import json

from tests.analyzers.support import AFTER, BEFORE, fixture_pair, pair, snapshot, state
from tinarrative.analyzers import POLITICS_ANALYZERS, run_analyzers
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
    'nation:20 federation: null -> {"value": 80} (unmodelled state type)',
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


def lines(before_name: str, after_name: str) -> set[str]:
    before, after, diff = fixture_pair(before_name, after_name)
    return {describe_event(event) for event in run_analyzers(POLITICS_ANALYZERS, before, after, diff)}


def test_every_politics_event_type_has_a_template() -> None:
    assert lines("interval_before.json", "interval_after.json") == EXPECTED_INTERVAL
    assert lines("records_before.json", "records_after.json") == EXPECTED_RECORDS
    assert lines("politics_before.json", "politics_after.json") == EXPECTED_POLITICS
    assert all(line.isascii() for line in EXPECTED_INTERVAL | EXPECTED_RECORDS | EXPECTED_POLITICS)


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
        event_type="army.destroyed_flag_changed",
        status=EventStatus.OBJECTIVE,
        confidence=Confidence.HIGH,
        date=Unknown(),
        date_basis=DateBasis.INTERVAL,
        not_before=Unknown(),
        sources=(),
        entities=(after.nations[0].ref,),
        attributes=(("after", "café"),),
    )
    assert describe_event(event) == "army.destroyed_flag_changed: nation:20"
    plain = Event(**{**event.__dict__, "event_type": "nation.capital_changed", "attributes": (("after", "café"),)})
    described = describe_event(plain)
    assert described.isascii() and json.loads(described.split("-> ")[1]) == "café"
