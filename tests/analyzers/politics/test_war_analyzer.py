"""War events: presence, alliance members, leading nations and the last-fighting record, with nation wars mirrors."""

from tests.analyzers.support import (
    AFTER,
    AFTER_DATE,
    BEFORE,
    analyze,
    named,
    nation_ref,
    only,
    record_set,
    snapshot,
    state,
    war_ref,
)
from tinarrative.analyzers.politics import WarAnalyzer
from tinarrative.analyzers.politics.wars import (
    ALLIANCE_CHANGED,
    APPEARED,
    ATTACKER_CHANGED,
    DISAPPEARED,
    LAST_FIGHTING_CHANGED,
)
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, DateBasis, SourceRole
from tinarrative.model.records import ItemEntry, RecordKind
from tinarrative.model.values import Unknown, UnknownReason, freeze

ANALYZER = WarAnalyzer()
NATION = EntityDomain.NATION
WAR = EntityDomain.WAR


def war(save: str, attacking: tuple[str, ...], defending: tuple[str, ...], key: str = "90") -> object:
    return state(
        WAR,
        key,
        save,
        attacker=nation_ref(attacking[0]),
        defender=nation_ref(defending[0]),
        _attackingAlliance=tuple(nation_ref(n) for n in attacking),
        _defendingAlliance=tuple(nation_ref(n) for n in defending),
    )


def nation(save: str, key: str, *wars: str) -> object:
    return state(NATION, key, save, wars=tuple(nation_ref(n) for n in wars))


def date_record(save: str, field: str, value: str, key: str = "90") -> object:
    return record_set(save, war_ref(key), field, RecordKind.DATE, (ItemEntry(0, value),))


def sources(event: object) -> list[tuple[SourceRole, str, str | None]]:
    return [(s.role, str(s.change.entity_id), s.change.field) for s in event.sources]  # type: ignore[attr-defined]


def test_an_appeared_war_is_dated_by_its_start_record_and_cites_every_cross_side_wars_entry() -> None:
    before = snapshot(BEFORE, nation(BEFORE, "20"), nation(BEFORE, "21"), nation(BEFORE, "22"))
    after = snapshot(
        AFTER,
        war(AFTER, ("20", "22"), ("21",)),
        nation(AFTER, "20", "21"),
        nation(AFTER, "21", "20", "22"),
        nation(AFTER, "22", "21"),
        records=(date_record(AFTER, "startDate", "2031-04-02T00:00:00"),),
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == APPEARED and event.confidence is Confidence.HIGH
    assert (event.date, event.date_basis) == ("2031-04-02T00:00:00", DateBasis.RECORD)
    assert [str(ref.entity_id) for ref in event.entities] == ["war:90", "nation:20", "nation:22", "nation:21"]
    assert sorted(sources(event)[2:]) == sorted(
        [
            (SourceRole.CORROBORATING, "nation:20", "wars"),
            (SourceRole.CORROBORATING, "nation:21", "wars"),
            (SourceRole.CORROBORATING, "nation:22", "wars"),
            (SourceRole.CORROBORATING, "nation:21", "wars"),
        ]
    )


def test_an_appeared_war_without_a_start_record_is_interval_dated_and_unmirrored_lists_are_not_required() -> None:
    before = snapshot(BEFORE)
    after = snapshot(AFTER, war(AFTER, ("20",), ("21",)))
    (event,) = analyze(ANALYZER, before, after)
    assert (event.date, event.date_basis) == (AFTER_DATE, DateBasis.INTERVAL)
    assert sources(event) == [(SourceRole.PRIMARY, "war:90", None)]
    assert isinstance(event.attribute("started_on"), Unknown)


def test_a_disappeared_war_cites_the_removed_wars_entries_from_the_earlier_sides() -> None:
    before = snapshot(BEFORE, war(BEFORE, ("20",), ("21",)), nation(BEFORE, "20", "21"), nation(BEFORE, "21", "20"))
    after = snapshot(AFTER, nation(AFTER, "20"), nation(AFTER, "21"))
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == DISAPPEARED and event.attribute("side") == "before"
    assert sources(event) == [
        (SourceRole.PRIMARY, "war:90", None),
        (SourceRole.CORROBORATING, "nation:20", "wars"),
        (SourceRole.CORROBORATING, "nation:21", "wars"),
    ]


def test_an_alliance_member_leaving_cites_its_wars_entries_against_the_earlier_opposing_side() -> None:
    before = snapshot(
        BEFORE,
        war(BEFORE, ("20",), ("21", "23")),
        nation(BEFORE, "20", "21", "23"),
        nation(BEFORE, "21", "20"),
        nation(BEFORE, "23", "20"),
    )
    after = snapshot(
        AFTER, war(AFTER, ("20",), ("21",)), nation(AFTER, "20", "21"), nation(AFTER, "21", "20"), nation(AFTER, "23")
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.id == "war.alliance_changed/war:90/defending/nation:23/removed"
    assert event.event_type == ALLIANCE_CHANGED
    assert dict(event.attributes) == {"side": "defending", "member": named(nation_ref("23")), "transition": "removed"}
    assert sources(event) == [
        (SourceRole.PRIMARY, "war:90", "_defendingAlliance"),
        (SourceRole.CORROBORATING, "nation:20", "wars"),
        (SourceRole.CORROBORATING, "nation:23", "wars"),
    ]


def test_a_new_leading_nation_and_a_later_last_fighting_date_are_literal_transitions() -> None:
    before = snapshot(
        BEFORE,
        war(BEFORE, ("20", "22"), ("21",)),
        records=(date_record(BEFORE, "dateOfLastFighting", "2031-02-01T00:00:00"),),
    )
    after = snapshot(
        AFTER,
        state(
            WAR,
            "90",
            AFTER,
            attacker=nation_ref("22"),
            defender=nation_ref("21"),
            _attackingAlliance=(nation_ref("20"), nation_ref("22")),
            _defendingAlliance=(nation_ref("21"),),
        ),
        records=(date_record(AFTER, "dateOfLastFighting", "2031-05-20T00:00:00"),),
    )
    events = analyze(ANALYZER, before, after)
    assert len(events) == 2
    attacker = only(events, ATTACKER_CHANGED)
    assert dict(attacker.attributes) == {"transition": "changed", "before": nation_ref("20"), "after": nation_ref("22")}
    fighting = only(events, LAST_FIGHTING_CHANGED)
    assert (fighting.date, fighting.date_basis) == ("2031-05-20T00:00:00", DateBasis.RECORD)


def test_wars_entries_no_war_explains_are_relation_events_and_unresolved_alliances_are_leftovers() -> None:
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze([{"value": 999}]))
    before = snapshot(BEFORE, war(BEFORE, ("20",), ("21",)), nation(BEFORE, "22"), nation(BEFORE, "23"))
    after = snapshot(
        AFTER,
        state(
            WAR,
            "90",
            AFTER,
            attacker=nation_ref("20"),
            defender=nation_ref("21"),
            _attackingAlliance=(nation_ref("20"),),
            _defendingAlliance=unresolved,
        ),
        nation(AFTER, "22", "23"),
        nation(AFTER, "23", "22"),
    )
    events = analyze(ANALYZER, before, after)
    assert sorted(event.id for event in events) == [
        "nation.relation_changed/wars/nation:22/nation:23/added",
        "war.defending_alliance_changed/war:90/unresolved",
    ]
    leftover = only(events, "war.defending_alliance_changed")
    assert leftover.confidence is Confidence.LOW
