"""Nation events: territory, capital, relations, breakaways, the executive record and presence."""

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    BEFORE_DATE,
    analyze,
    by_type,
    faction_ref,
    federation_ref,
    named,
    nation_ref,
    only,
    record_set,
    region_ref,
    snapshot,
    state,
)
from tinarrative.analyzers.politics import NationAnalyzer
from tinarrative.analyzers.politics.nations import (
    APPEARED,
    BREAKAWAY_PARENT_CHANGED,
    CAPITAL_CHANGED,
    DISAPPEARED,
    EXECUTIVE_CHANGE_RECORDED,
    REGION_NATION_CHANGED,
    list_event_type,
)
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, DateBasis, SourceRole
from tinarrative.model.records import KeyedEntry, RecordKind
from tinarrative.model.values import Unknown, UnknownReason, freeze

ANALYZER = NationAnalyzer()
NATION = EntityDomain.NATION
REGION = EntityDomain.REGION


def test_region_ownership_change_cites_both_nations_region_lists() -> None:
    before = snapshot(
        BEFORE,
        state(REGION, "42", BEFORE, nation=nation_ref("21")),
        state(NATION, "20", BEFORE, regions=(region_ref("40"),)),
        state(NATION, "21", BEFORE, regions=(region_ref("42"),)),
    )
    after = snapshot(
        AFTER,
        state(REGION, "42", AFTER, nation=nation_ref("20")),
        state(NATION, "20", AFTER, regions=(region_ref("42"), region_ref("40"))),
        state(NATION, "21", AFTER, regions=()),
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == REGION_NATION_CHANGED and event.confidence is Confidence.HIGH
    assert [str(ref.entity_id) for ref in event.entities] == ["region:42", "nation:21", "nation:20"]
    assert dict(event.attributes) == {
        "transition": "changed",
        "before": named(nation_ref("21")),
        "after": named(nation_ref("20")),
    }
    assert [(s.role, str(s.change.entity_id), s.member) for s in event.sources] == [
        (SourceRole.PRIMARY, "region:42", None),
        (SourceRole.CORROBORATING, "nation:20", region_ref("42")),
        (SourceRole.CORROBORATING, "nation:21", region_ref("42")),
    ]


def test_capital_is_a_single_field_transition_and_federation_and_wars_are_left_to_their_analyzers() -> None:
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, capital=region_ref("40"), federation=None, wars=()))
    after = snapshot(
        AFTER,
        state(NATION, "20", AFTER, capital=region_ref("41"), federation=federation_ref("80"), wars=(nation_ref("21"),)),
    )
    events = analyze(ANALYZER, before, after)
    capital = only(events, CAPITAL_CHANGED)
    assert [str(ref.entity_id) for ref in capital.entities] == ["nation:20", "region:40", "region:41"]
    assert len(events) == 1


def test_reciprocal_relation_entries_merge_and_one_sided_entries_name_the_lister() -> None:
    before = snapshot(
        BEFORE,
        state(NATION, "20", BEFORE, allies=(nation_ref("21"),), rivals=()),
        state(NATION, "21", BEFORE, allies=(nation_ref("20"),), rivals=()),
        state(NATION, "22", BEFORE, allies=(), rivals=()),
    )
    after = snapshot(
        AFTER,
        state(NATION, "20", AFTER, allies=(nation_ref("22"),), rivals=(nation_ref("21"),)),
        state(NATION, "21", AFTER, allies=(nation_ref("20"),), rivals=(nation_ref("20"),)),
        state(NATION, "22", AFTER, allies=(nation_ref("20"),), rivals=()),
    )
    events = analyze(ANALYZER, before, after)
    assert [event.id for event in events] == [
        "nation.relation_changed/allies/nation:20/nation:22/added",
        "nation.relation_changed/allies/nation:20/nation:21/removed",
        "nation.relation_changed/rivals/nation:20/nation:21/added",
    ]
    added, removed, rivals = events
    assert dict(added.attributes) == {"relation": "allies", "transition": "added", "reciprocal": True}
    assert [(s.role, str(s.change.entity_id), s.member) for s in added.sources] == [
        (SourceRole.PRIMARY, "nation:20", nation_ref("22")),
        (SourceRole.PRIMARY, "nation:22", nation_ref("20")),
    ]
    assert dict(removed.attributes) == {
        "relation": "allies",
        "transition": "removed",
        "reciprocal": False,
        "listed_by": removed.entities[0],
    }
    assert str(removed.entities[0].entity_id) == "nation:20" and len(removed.sources) == 1
    assert dict(rivals.attributes)["reciprocal"] is True and len(rivals.sources) == 2
    assert all(event.confidence is Confidence.HIGH for event in events)


def test_breakaway_parent_cites_the_parents_breakaway_list_and_leftovers_are_reported() -> None:
    before = snapshot(
        BEFORE,
        state(NATION, "20", BEFORE, breakaways=(), regions=(region_ref("40"),)),
        state(NATION, "22", BEFORE, breakawayParent=None),
    )
    after = snapshot(
        AFTER,
        state(NATION, "20", AFTER, breakaways=(nation_ref("22"),), regions=()),
        state(NATION, "22", AFTER, breakawayParent=nation_ref("20")),
    )
    events = analyze(ANALYZER, before, after)
    parent = only(events, BREAKAWAY_PARENT_CHANGED)
    assert [str(ref.entity_id) for ref in parent.entities] == ["nation:22", "nation:20"]
    assert [(s.role, str(s.change.entity_id)) for s in parent.sources] == [
        (SourceRole.PRIMARY, "nation:22"),
        (SourceRole.CORROBORATING, "nation:20"),
    ]
    regions = only(events, list_event_type("regions"))
    assert regions.id == "nation.regions_changed/nation:20/region:40/removed"
    assert dict(regions.attributes) == {"member": region_ref("40"), "transition": "removed"}
    assert len(events) == 2


def executive(save: str, nation: str, new: object, date: object, cause: object) -> object:
    entries = (KeyedEntry(0, "cause", cause), KeyedEntry(1, "date", date), KeyedEntry(2, "newExecutive", new))  # type: ignore[arg-type]
    return record_set(save, nation_ref(nation), "lastExecutiveChange", RecordKind.EXECUTIVE_CHANGE, entries)


def test_executive_change_record_is_dated_by_the_record_and_copies_its_values_literally() -> None:
    before = snapshot(
        BEFORE,
        state(NATION, "20", BEFORE),
        records=(executive(BEFORE, "20", faction_ref("16"), "2031-01-05T00:00:00", "Politics"),),  # type: ignore[arg-type]
    )
    after = snapshot(
        AFTER,
        state(NATION, "20", AFTER),
        records=(executive(AFTER, "20", faction_ref("15"), "2031-04-20T00:00:00", "Coup"),),  # type: ignore[arg-type]
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == EXECUTIVE_CHANGE_RECORDED
    assert (event.date, event.date_basis, event.not_before) == ("2031-04-20T00:00:00", DateBasis.RECORD, BEFORE_DATE)
    assert [str(ref.entity_id) for ref in event.entities] == ["nation:20", "faction:15", "faction:16"]
    assert dict(event.attributes) == {
        "new_executive": faction_ref("15"),
        "recorded_on": "2031-04-20T00:00:00",
        "cause": "Coup",
        "previous_executive": faction_ref("16"),
        "previous_recorded_on": "2031-01-05T00:00:00",
        "previous_cause": "Politics",
    }
    assert [(s.role, s.member, s.entry.path.rsplit("/", 1)[1]) for s in event.sources] == [  # type: ignore[union-attr]
        (SourceRole.PRIMARY, "cause", "cause"),
        (SourceRole.PRIMARY, "date", "date"),
        (SourceRole.PRIMARY, "newExecutive", "newExecutive"),
    ]
    assert "coup" not in event.event_type.lower()


def test_executive_record_with_an_unresolved_executive_is_low_confidence() -> None:
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 999}))
    before = snapshot(BEFORE, state(NATION, "20", BEFORE), records=(executive(BEFORE, "20", None, None, "None"),))  # type: ignore[arg-type]
    after = snapshot(
        AFTER,
        state(NATION, "20", AFTER),
        records=(executive(AFTER, "20", unresolved, "2031-04-20T00:00:00", "Politics"),),
    )  # type: ignore[arg-type]
    (event,) = analyze(ANALYZER, before, after)
    assert event.confidence is Confidence.LOW and event.date_basis is DateBasis.RECORD
    assert [str(ref.entity_id) for ref in event.entities] == ["nation:20"]


def test_presence_and_statistics() -> None:
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, GDP=1.0), state(NATION, "21", BEFORE))
    after = snapshot(AFTER, state(NATION, "20", AFTER, GDP=2.0), state(NATION, "23", AFTER))
    events = analyze(ANALYZER, before, after)
    assert only(events, DISAPPEARED).attribute("side") == "before"
    assert only(events, APPEARED).attribute("side") == "after"
    assert not by_type(events, CAPITAL_CHANGED) and len(events) == 2  # GDP stays in the diff
