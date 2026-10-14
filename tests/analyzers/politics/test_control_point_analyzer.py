"""Control-point control events: controller transitions, nation moves, presence, loss records and leftovers."""

from tests.analyzers.support import (
    AFTER,
    AFTER_DATE,
    BEFORE,
    BEFORE_DATE,
    analyze,
    by_type,
    faction_ref,
    nation_ref,
    only,
    point_ref,
    record_set,
    snapshot,
    state,
)
from tinarrative.analyzers.politics import ControlPointAnalyzer
from tinarrative.analyzers.politics.control_points import (
    APPEARED,
    CONTROLLER_CHANGED,
    DISAPPEARED,
    FACTION_LIST_CHANGED,
    LOSS_RECORDED,
    NATION_CHANGED,
    NATION_LIST_CHANGED,
)
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, DateBasis, EventStatus, SourceRole
from tinarrative.model.records import KeyedEntry, RecordKind
from tinarrative.model.values import Unknown, UnknownReason, freeze

ANALYZER = ControlPointAnalyzer()
CP = EntityDomain.CONTROL_POINT
LOST_ON = "2031-04-10T00:00:00"


def point(save: str, key: str, faction: object, nation: str = "20") -> object:
    return state(CP, key, save, faction=faction, nation=nation_ref(nation))


def test_controller_transfer_cites_both_rosters_and_the_loss_record() -> None:
    losing = faction_ref("16")
    before = snapshot(
        BEFORE,
        point(BEFORE, "9", losing),  # type: ignore[arg-type]
        state(EntityDomain.FACTION, "15", BEFORE, controlPoints=()),
        state(EntityDomain.FACTION, "16", BEFORE, controlPoints=(point_ref("9"),)),
        state(EntityDomain.NATION, "20", BEFORE),
        records=(record_set(BEFORE, losing, "lostControlPoints", RecordKind.DATED_REFERENCES, ()),),
    )
    after = snapshot(
        AFTER,
        point(AFTER, "9", faction_ref("15")),  # type: ignore[arg-type]
        state(EntityDomain.FACTION, "15", AFTER, controlPoints=(point_ref("9"),)),
        state(EntityDomain.FACTION, "16", AFTER, controlPoints=()),
        state(EntityDomain.NATION, "20", AFTER),
        records=(
            record_set(
                AFTER,
                losing,
                "lostControlPoints",
                RecordKind.DATED_REFERENCES,
                (KeyedEntry(0, point_ref("9"), LOST_ON),),
            ),
        ),
    )
    events = analyze(ANALYZER, before, after)
    event = only(events, CONTROLLER_CHANGED)
    assert event.id == "control_point.controller_changed/control point:9"
    assert (event.status, event.confidence) == (EventStatus.OBJECTIVE, Confidence.HIGH)
    assert (event.date, event.date_basis, event.not_before) == (AFTER_DATE, DateBasis.INTERVAL, BEFORE_DATE)
    assert [str(ref.entity_id) for ref in event.entities] == [
        "control point:9",
        "nation:20",
        "faction:16",
        "faction:15",
    ]
    assert event.entities[0].name == "Fixture control point 9"
    assert dict(event.attributes) == {
        "transition": "changed",
        "before": losing,
        "after": faction_ref("15"),
        "loss_recorded_on": LOST_ON,
    }
    cited = [(s.role, str(s.change.entity_id), s.change.field, s.member) for s in event.sources]
    assert cited == [
        (SourceRole.PRIMARY, "control point:9", "faction", None),
        (SourceRole.CORROBORATING, "faction:15", "controlPoints", point_ref("9")),
        (SourceRole.CORROBORATING, "faction:16", "controlPoints", point_ref("9")),
        (SourceRole.CORROBORATING, "faction:16", "lostControlPoints", point_ref("9")),
    ]
    record_source = event.sources[3]
    assert record_source.entry is not None and record_source.entry.path.endswith("/lostControlPoints/0")  # type: ignore[union-attr]
    # the record is also an event of its own, dated by the entry
    loss = only(events, LOSS_RECORDED)
    assert (loss.date, loss.date_basis, loss.not_before) == (LOST_ON, DateBasis.RECORD, BEFORE_DATE)
    assert [str(ref.entity_id) for ref in loss.entities] == ["control point:9", "faction:16", "nation:20"]
    assert dict(loss.attributes) == {"recorded_on": LOST_ON}
    assert loss.sources[0].role is SourceRole.PRIMARY and loss.sources[0].entry == record_source.entry
    assert not by_type(events, FACTION_LIST_CHANGED)  # both roster entries were consumed as corroboration
    assert len(events) == 2


def test_set_and_cleared_controllers_are_transitions_without_a_loser_or_gainer() -> None:
    before = snapshot(BEFORE, point(BEFORE, "9", None), point(BEFORE, "10", faction_ref("15")))  # type: ignore[arg-type]
    after = snapshot(AFTER, point(AFTER, "9", faction_ref("15")), point(AFTER, "10", None))  # type: ignore[arg-type]
    taken, released = by_type(analyze(ANALYZER, before, after), CONTROLLER_CHANGED)
    assert taken.attribute("transition") == "set" and taken.attribute("before") is None
    assert released.attribute("transition") == "cleared" and released.attribute("after") is None
    assert [str(ref.entity_id) for ref in taken.entities] == ["control point:9", "nation:20", "faction:15"]
    assert all(len(event.sources) == 1 for event in (taken, released))


def test_unresolved_controller_is_a_low_confidence_transition_and_missing_is_nothing() -> None:
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 999}))
    before = snapshot(BEFORE, point(BEFORE, "9", faction_ref("15")), point(BEFORE, "10", faction_ref("15")))  # type: ignore[arg-type]
    after = snapshot(AFTER, point(AFTER, "9", unresolved), point(AFTER, "10", Unknown()))  # type: ignore[arg-type]
    (event,) = analyze(ANALYZER, before, after)
    assert event.id.endswith("control point:9") and event.confidence is Confidence.LOW
    assert event.attribute("transition") == "unresolved" and event.attribute("after") == unresolved


def test_nation_move_is_distinct_from_control_and_cites_both_nation_lists() -> None:
    before = snapshot(
        BEFORE,
        point(BEFORE, "11", None, "21"),  # type: ignore[arg-type]
        state(EntityDomain.NATION, "20", BEFORE, controlPoints=()),
        state(EntityDomain.NATION, "21", BEFORE, controlPoints=(point_ref("11"),)),
    )
    after = snapshot(
        AFTER,
        point(AFTER, "11", None, "20"),  # type: ignore[arg-type]
        state(EntityDomain.NATION, "20", AFTER, controlPoints=(point_ref("11"),)),
        state(EntityDomain.NATION, "21", AFTER, controlPoints=()),
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == NATION_CHANGED
    assert [str(ref.entity_id) for ref in event.entities] == ["control point:11", "nation:21", "nation:20"]
    assert [(s.role, str(s.change.entity_id)) for s in event.sources] == [
        (SourceRole.PRIMARY, "control point:11"),
        (SourceRole.CORROBORATING, "nation:20"),
        (SourceRole.CORROBORATING, "nation:21"),
    ]


def test_presence_changes_say_absent_or_present_and_cite_the_owner_lists() -> None:
    before = snapshot(
        BEFORE,
        point(BEFORE, "12", faction_ref("16"), "21"),  # type: ignore[arg-type]
        state(EntityDomain.FACTION, "16", BEFORE, controlPoints=(point_ref("12"),)),
        state(EntityDomain.NATION, "21", BEFORE, controlPoints=(point_ref("12"),)),
    )
    after = snapshot(
        AFTER,
        point(AFTER, "13", None, "21"),  # type: ignore[arg-type]
        state(EntityDomain.FACTION, "16", AFTER, controlPoints=()),
        state(EntityDomain.NATION, "21", AFTER, controlPoints=(point_ref("13"),)),
    )
    events = analyze(ANALYZER, before, after)
    gone = only(events, DISAPPEARED)
    assert gone.attribute("side") == "before" and gone.confidence is Confidence.HIGH
    assert [str(ref.entity_id) for ref in gone.entities] == ["control point:12", "nation:21", "faction:16"]
    assert [(s.role, str(s.change.entity_id)) for s in gone.sources] == [
        (SourceRole.PRIMARY, "control point:12"),
        (SourceRole.CORROBORATING, "faction:16"),
        (SourceRole.CORROBORATING, "nation:21"),
    ]
    assert gone.sources[0].change.evidence.description == "absent from the after snapshot"
    new = only(events, APPEARED)
    assert new.attribute("side") == "after"
    assert [str(ref.entity_id) for ref in new.entities] == ["control point:13", "nation:21"]
    assert len(new.sources) == 2
    assert len(events) == 2


def test_loss_record_alone_is_an_event_and_a_redated_entry_keeps_the_previous_date() -> None:
    owner = faction_ref("16")
    earlier = "2031-02-01T00:00:00"
    before = snapshot(
        BEFORE,
        point(BEFORE, "9", owner),  # type: ignore[arg-type]
        records=(
            record_set(
                BEFORE,
                owner,
                "lostControlPoints",
                RecordKind.DATED_REFERENCES,
                (KeyedEntry(0, point_ref("9"), earlier),),
            ),
        ),
    )
    after = snapshot(
        AFTER,
        point(AFTER, "9", owner),  # type: ignore[arg-type]
        records=(
            record_set(
                AFTER,
                owner,
                "lostControlPoints",
                RecordKind.DATED_REFERENCES,
                (KeyedEntry(0, point_ref("9"), LOST_ON),),
            ),
        ),
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == LOSS_RECORDED and event.date == LOST_ON
    assert dict(event.attributes) == {"recorded_on": LOST_ON, "previous_recorded_on": earlier}
    assert [str(ref.entity_id) for ref in event.entities] == ["control point:9", "faction:16", "nation:20"]


def test_unexplained_list_members_and_unresolved_lists_become_their_own_events() -> None:
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze([{"value": 999}]))
    before = snapshot(
        BEFORE,
        state(EntityDomain.FACTION, "15", BEFORE, controlPoints=(point_ref("9"),)),
        state(EntityDomain.NATION, "22", BEFORE, controlPoints=()),
    )
    after = snapshot(
        AFTER,
        state(EntityDomain.FACTION, "15", AFTER, controlPoints=unresolved),
        state(EntityDomain.NATION, "22", AFTER, controlPoints=(point_ref("10"),)),
    )
    events = analyze(ANALYZER, before, after)
    stale = only(events, FACTION_LIST_CHANGED)
    assert stale.id == "faction.control_points_changed/faction:15/unresolved"
    assert stale.confidence is Confidence.LOW and stale.attribute("after") == unresolved
    assert [str(ref.entity_id) for ref in stale.entities] == ["faction:15"]
    extra = only(events, NATION_LIST_CHANGED)
    assert extra.id == "nation.control_points_changed/nation:22/control point:10/added"
    assert dict(extra.attributes) == {"member": point_ref("10"), "transition": "added"}
    assert extra.sources[0].member == point_ref("10")
    assert len(events) == 2


def test_timers_and_identical_snapshots_produce_nothing() -> None:
    before = snapshot(BEFORE, state(CP, "9", BEFORE, faction=faction_ref("15"), defended=False, defendExpiration=None))
    after = snapshot(AFTER, state(CP, "9", AFTER, faction=faction_ref("15"), defended=True, defendExpiration="x"))
    assert analyze(ANALYZER, before, after) == []
    assert analyze(ANALYZER, before, before) == []
