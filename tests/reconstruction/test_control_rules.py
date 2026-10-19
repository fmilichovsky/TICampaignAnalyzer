"""Nation-control reconstruction: synthetic control points changing hands, with executive and loss records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    by_type,
    faction_ref,
    nation_ref,
    pair,
    point_ref,
    record_set,
    region_ref,
    snapshot,
    state,
)
from tests.reconstruction.support import Scenario, assert_traceable, lines_of, run
from tinarrative.analyzers.render import describe_event
from tinarrative.model.entities import EntityDomain, EntityRef
from tinarrative.model.events import Confidence, DateBasis, Event, EventStatus, Significance, SourceRole
from tinarrative.model.records import KeyedEntry, RecordKind, RecordSet
from tinarrative.model.snapshot import EntityState, SaveSnapshot
from tinarrative.model.values import FrozenMap, Observed, Unknown, UnknownReason
from tinarrative.reconstruction import NATION_CONTROL_CHANGED, RULE_TYPES

POINT = EntityDomain.CONTROL_POINT
NATION = "20"
OTHER_NATION = "21"
UNRESOLVED = Unknown(UnknownReason.UNRESOLVED_REFERENCE)

Holders = Sequence[str | None | Unknown]
"""The controller of each control point of nation 20 by position: a faction key, ``None`` or an unresolved value."""


def _controller(holder: str | None | Unknown) -> Observed:
    return faction_ref(holder) if isinstance(holder, str) else holder


def control_pair(
    before: Holders,
    after: Holders,
    *,
    records_before: tuple[RecordSet, ...] = (),
    records_after: tuple[RecordSet, ...] = (),
    moved_point: str | None = None,
) -> Scenario:
    """Nation 20 with one control point per position (keys ``9``, ``10``, ...), position 0 its executive seat typed
    after the regime; factions 15 to 17 exist. ``moved_point`` belongs to nation 21 before and to nation 20 after."""

    def side(save: str, holders: Holders, records: tuple[RecordSet, ...], moved_to: str) -> SaveSnapshot:
        keys = [str(9 + position) for position in range(len(holders))]
        points = [
            state(
                POINT,
                key,
                save,
                nation=nation_ref(moved_to if key == moved_point else NATION),
                faction=_controller(holder),
                positionInNation=position,
                controlPointType="TheParty" if position == 0 else "Legislative",
            )
            for position, (key, holder) in enumerate(zip(keys, holders, strict=True))
        ]
        own = tuple(point_ref(key) for key in keys if key != moved_point or moved_to == NATION)
        nations = [
            state(EntityDomain.NATION, NATION, save, controlPoints=own, regions=(region_ref("40"),)),
            state(
                EntityDomain.NATION,
                OTHER_NATION,
                save,
                controlPoints=tuple(point_ref(key) for key in keys if key == moved_point and moved_to != NATION),
                regions=(region_ref("41"),),
            ),
        ]
        regions = [
            state(EntityDomain.REGION, "40", save, nation=nation_ref(NATION), populationInMillions=12.5),
            state(EntityDomain.REGION, "41", save, nation=nation_ref(OTHER_NATION), populationInMillions=3.0),
        ]
        factions = [state(EntityDomain.FACTION, key, save, templateName="ResistCouncil") for key in ("15", "16", "17")]
        return snapshot(save, *points, *nations, *regions, *factions, records=records)

    return pair(
        side(BEFORE, before, records_before, OTHER_NATION),
        side(AFTER, after, records_after, NATION),
    )


def executive_record(save: str, new_executive: str, cause: str, date: str) -> RecordSet:
    entries = (
        KeyedEntry(0, "cause", cause),
        KeyedEntry(1, "date", date),
        KeyedEntry(2, "newExecutive", faction_ref(new_executive)),
    )
    return record_set(save, nation_ref(NATION), "lastExecutiveChange", RecordKind.EXECUTIVE_CHANGE, entries)


def loss_record(save: str, point: str, date: str | None) -> tuple[RecordSet, ...]:
    entries = () if date is None else (KeyedEntry(0, point_ref(point), date),)
    return (record_set(save, faction_ref("15"), "lostControlPoints", RecordKind.DATED_REFERENCES, entries),)


def control(events: list[Event], scope: str) -> Event:
    matches = [event for event in by_type(events, NATION_CONTROL_CHANGED) if event.attribute("scope") == scope]
    assert len(matches) == 1, [event.id for event in events]
    return matches[0]


def scopes(events: list[Event]) -> list[str]:
    return sorted(str(event.attribute("scope")) for event in by_type(events, NATION_CONTROL_CHANGED))


def faction_key(value: Observed) -> str | None:
    if value is None:
        return None
    assert isinstance(value, EntityRef)
    return value.entity_id.key


# --- Scenarios --------------------------------------------------------------------------------------------


def executive_flip() -> Scenario:
    """Faction 16 takes the executive seat from 15; 15 keeps the plurality, and one point stays uncontrolled."""
    return control_pair(["15", "15", "15", None], ["16", "15", "15", None])


def plurality_flip() -> Scenario:
    """Faction 16 takes two legislative points; the seat stays with 15."""
    return control_pair(["15", "15", None], ["15", "16", "16"])


def plurality_tie() -> Scenario:
    """Faction 16 takes one of 15's two points: one each, no plurality."""
    return control_pair(["15", "15"], ["15", "16"])


def sole_handover() -> Scenario:
    """One-point nation: faction 16 takes 15's only point (every scope changes)."""
    return control_pair(["15"], ["16"])


def sole_gained() -> Scenario:
    """Faction 15 takes the last uncontrolled point of the nation."""
    return control_pair(["15", None], ["15", "15"])


def recorded_takeover() -> Scenario:
    """Faction 16 takes the seat and a ``lastExecutiveChange`` names it, dated in the interval; 15 records a loss."""
    return control_pair(
        ["15", "15", "16"],
        ["16", "15", "16"],
        records_before=(
            executive_record(BEFORE, "15", "Politics", "2029-05-01T00:00:00"),
            *loss_record(BEFORE, "9", None),
        ),
        records_after=(
            executive_record(AFTER, "16", "Coup", "2031-04-12T00:00:00"),
            *loss_record(AFTER, "9", "2031-04-12T00:00:00"),
        ),
    )


def disagreeing_record() -> Scenario:
    """The seat goes to 16 while the executive record names 17."""
    return control_pair(
        ["15", "15", "15"],
        ["16", "15", "15"],
        records_before=(executive_record(BEFORE, "15", "Politics", "2029-05-01T00:00:00"),),
        records_after=(executive_record(AFTER, "17", "Election", "2031-04-12T00:00:00"),),
    )


def unresolved_point() -> Scenario:
    """The seat goes to 16 while a legislative point's controller is unresolved after the interval."""
    return control_pair(["15", "15", "15"], ["16", UNRESOLVED, "15"])


def moved_point() -> Scenario:
    """Point 11 moves from nation 21 to nation 20 under faction 16, and faction 16 takes the seat as well."""
    return control_pair(["15", "15", "16"], ["16", "15", "16"], moved_point="11")


SCENARIOS = (
    executive_flip,
    plurality_flip,
    plurality_tie,
    sole_handover,
    sole_gained,
    recorded_takeover,
    disagreeing_record,
    unresolved_point,
)


# --- Tests ------------------------------------------------------------------------------------------------


def test_the_rule_is_listed() -> None:
    assert NATION_CONTROL_CHANGED in RULE_TYPES


def test_every_scenario_is_traceable() -> None:
    for scenario in SCENARIOS:
        assert_traceable(scenario())


def test_an_executive_seat_changing_hands_is_the_executive_scope_only() -> None:
    _, inferred = run(executive_flip())
    assert scopes(inferred) == ["executive"]
    event = control(inferred, "executive")
    assert event.status is EventStatus.INFERRED and event.confidence is Confidence.MEDIUM
    assert event.id == f"{NATION_CONTROL_CHANGED}/nation:20/executive"
    assert faction_key(event.attribute("before")) == "15" and faction_key(event.attribute("after")) == "16"
    assert event.attribute("shares_before") == FrozenMap((("faction:15", 3),))
    assert event.attribute("shares_after") == FrozenMap((("faction:15", 2), ("faction:16", 1)))
    assert event.attribute("point_count_before") == 4 and event.attribute("point_count_after") == 4
    assert event.attribute("cause") is None and event.attribute("population") == 12.5
    assert event.date_basis is DateBasis.INTERVAL
    assert event.constituents == ("control_point.controller_changed/control point:9",)
    assert [str(ref.entity_id) for ref in event.entities] == ["nation:20", "faction:15", "faction:16"]
    assert describe_event(event) == (
        "Fixture nation 20 (nation:20) executive control changed: "
        "Fixture faction 15 (faction:15) -> Fixture faction 16 (faction:16)"
    )


def test_the_position_zero_point_is_the_seat_whatever_its_type() -> None:
    _, inferred = run(control_pair(["15", "15", "15", None], ["15", "15", "16", None]))
    assert scopes(inferred) == []  # point 11 is not the seat and 15 keeps the plurality and the seat


def test_a_plurality_change_names_the_new_largest_holder() -> None:
    _, inferred = run(plurality_flip())
    assert scopes(inferred) == ["plurality"]
    event = control(inferred, "plurality")
    assert faction_key(event.attribute("before")) == "15" and faction_key(event.attribute("after")) == "16"
    assert len(event.constituents) == 2


def test_a_plurality_tie_has_no_holder_and_stays_major() -> None:
    _, inferred = run(plurality_tie())
    assert scopes(inferred) == ["plurality", "sole"]
    event = control(inferred, "plurality")
    assert faction_key(event.attribute("before")) == "15" and event.attribute("after") is None
    assert [str(ref.entity_id) for ref in event.entities] == ["nation:20", "faction:15"]
    lines = lines_of(plurality_tie())
    assert lines[event.id] == (
        "Fixture nation 20 (nation:20) plurality control changed: Fixture faction 15 (faction:15) -> null",
        Significance.MAJOR,
    )


def test_a_one_point_nation_changes_every_scope() -> None:
    _, inferred = run(sole_handover())
    assert scopes(inferred) == ["executive", "plurality", "sole"]
    for scope in ("executive", "plurality", "sole"):
        event = control(inferred, scope)
        assert faction_key(event.attribute("before")) == "15" and faction_key(event.attribute("after")) == "16"


def test_gaining_every_point_is_a_sole_change() -> None:
    _, inferred = run(sole_gained())
    assert scopes(inferred) == ["sole"]
    event = control(inferred, "sole")
    assert event.attribute("before") is None and faction_key(event.attribute("after")) == "15"


def test_an_agreeing_executive_record_dates_the_change_and_raises_it() -> None:
    _, inferred = run(recorded_takeover())
    assert scopes(inferred) == ["executive", "plurality"]
    assert faction_key(control(inferred, "plurality").attribute("after")) == "16"
    assert control(inferred, "plurality").confidence is Confidence.HIGH  # the record names the new plurality too
    event = control(inferred, "executive")
    assert event.confidence is Confidence.HIGH
    assert event.date_basis is DateBasis.RECORD and event.date == "2031-04-12T00:00:00"
    assert event.attribute("cause") == "Coup" and event.attribute("recorded_on") == "2031-04-12T00:00:00"
    assert set(event.constituents) == {
        "control_point.controller_changed/control point:9",
        "nation.executive_change_recorded/nation:20",
        "control_point.loss_recorded/faction:15/control point:9",
    }
    roles = {source.change.field: source.role for source in event.sources}
    assert roles["faction"] is SourceRole.PRIMARY
    assert roles["lastExecutiveChange"] is SourceRole.CORROBORATING
    assert "Coup" not in describe_event(event)


def test_a_disagreeing_executive_record_is_quoted_but_neither_dates_nor_raises() -> None:
    _, inferred = run(disagreeing_record())
    event = control(inferred, "executive")
    assert event.confidence is Confidence.MEDIUM and event.date_basis is DateBasis.INTERVAL
    assert event.attribute("cause") == "Election" and faction_key(event.attribute("new_executive")) == "17"
    assert "nation.executive_change_recorded/nation:20" in event.constituents


def test_an_unresolved_point_makes_every_scope_low() -> None:
    _, inferred = run(unresolved_point())
    assert scopes(inferred) == ["executive", "plurality", "sole"]
    assert {event.confidence for event in by_type(inferred, NATION_CONTROL_CHANGED)} == {Confidence.LOW}
    assert faction_key(control(inferred, "executive").attribute("after")) == "16"
    assert isinstance(control(inferred, "plurality").attribute("after"), Unknown)


def test_a_nation_whose_points_moved_between_nations_is_skipped() -> None:
    objective, inferred = run(moved_point())
    assert by_type(list(objective), "control_point.nation_changed")
    assert by_type(list(objective), "control_point.controller_changed")
    assert not by_type(inferred, NATION_CONTROL_CHANGED)


def test_no_controller_change_means_no_control_event() -> None:
    _, inferred = run(control_pair(["15", None], ["15", None]))
    assert not inferred


def _states(scenario: Scenario) -> Mapping[str, EntityState]:
    return {str(item.ref.entity_id): item for item in scenario[1].control_points}


def test_the_scenario_builder_types_the_seat_after_the_regime() -> None:
    seat = _states(executive_flip())["control point:9"]
    assert seat.get("positionInNation") == 0 and seat.get("controlPointType") == "TheParty"
