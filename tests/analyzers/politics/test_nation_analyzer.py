"""Nation events: territory, capital, relations, breakaways, claims, names, unrest attempts, records, presence."""

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
    CLAIMS_CHANGED,
    DISAPPEARED,
    EXECUTIVE_CHANGE_RECORDED,
    HOSTILE_CLAIMS_CHANGED,
    NEW_GOVERNMENT_RECORDED,
    NUCLEAR_PROGRAM_CHANGED,
    POLICY_CHANGED,
    POLICY_FIELDS,
    REGION_NATION_CHANGED,
    RENAMED,
    UNREST_ATTEMPTS_CHANGED,
    list_event_type,
)
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, DateBasis, SourceRole
from tinarrative.model.records import ItemEntry, KeyedEntry, RecordKind
from tinarrative.model.values import FrozenMap, Unknown, UnknownReason, freeze

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


def test_claims_are_one_event_per_nation_and_list_with_the_regions_owners_as_context() -> None:
    before = snapshot(
        BEFORE,
        state(NATION, "20", BEFORE, claims=(region_ref("41"),), hostileClaims=()),
        state(NATION, "21", BEFORE, claims=(), hostileClaims=()),
        state(REGION, "40", BEFORE, nation=nation_ref("21")),
        state(REGION, "41", BEFORE, nation=nation_ref("21")),
    )
    after = snapshot(
        AFTER,
        state(NATION, "20", AFTER, claims=(region_ref("40"),), hostileClaims=(region_ref("40"),)),
        state(NATION, "21", AFTER, claims=(), hostileClaims=()),
        state(REGION, "40", AFTER, nation=nation_ref("21")),
        state(REGION, "41", AFTER, nation=nation_ref("21")),
    )
    events = analyze(ANALYZER, before, after)
    assert [event.id for event in events] == [
        "nation.claims_changed/nation:20",
        "nation.hostile_claims_changed/nation:20",
    ]
    claims = only(events, CLAIMS_CHANGED)
    assert dict(claims.attributes) == {
        "added": (named(region_ref("40")),),
        "removed": (named(region_ref("41")),),
        "added_owners": (named(nation_ref("21")),),
    }
    assert [(s.role, s.change.field, s.member) for s in claims.sources] == [
        (SourceRole.PRIMARY, "claims", region_ref("40")),
        (SourceRole.PRIMARY, "claims", region_ref("41")),
    ]
    assert [str(ref.entity_id) for ref in claims.entities] == ["nation:20", "region:40", "region:41", "nation:21"]
    hostile = only(events, HOSTILE_CLAIMS_CHANGED)
    assert hostile.attribute("added") == (named(region_ref("40")),) and hostile.attribute("removed") == ()


def test_a_claim_list_unresolved_on_one_side_is_one_low_confidence_event() -> None:
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze([{"value": 999}]))
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, claims=()))
    after = snapshot(AFTER, state(NATION, "20", AFTER, claims=unresolved))
    event = only(analyze(ANALYZER, before, after), CLAIMS_CHANGED)
    assert event.id == "nation.claims_changed/nation:20"
    assert event.confidence is Confidence.LOW and event.attribute("transition") == "unresolved"


def test_a_display_name_change_is_a_rename_with_the_literal_names() -> None:
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, displayName="Old Name"))
    after = snapshot(AFTER, state(NATION, "20", AFTER, displayName="New Name"))
    event = only(analyze(ANALYZER, before, after), RENAMED)
    assert event.id == "nation.renamed/nation:20"
    assert dict(event.attributes) == {"transition": "changed", "before": "Old Name", "after": "New Name"}
    assert [(s.role, s.change.field) for s in event.sources] == [(SourceRole.PRIMARY, "displayName")]


def test_a_nuclear_program_flag_change_is_one_event_with_the_literal_flags() -> None:
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, nuclearProgram=False, policy_noNukes=False))
    after = snapshot(AFTER, state(NATION, "20", AFTER, nuclearProgram=True, policy_noNukes=False))
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == NUCLEAR_PROGRAM_CHANGED and event.id == "nation.nuclear_program_changed/nation:20"
    assert dict(event.attributes) == {"transition": "changed", "before": False, "after": True}
    assert [(s.role, s.change.field) for s in event.sources] == [(SourceRole.PRIMARY, "nuclearProgram")]


def test_each_policy_flag_change_is_a_policy_event_naming_the_policy() -> None:
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, **dict.fromkeys(POLICY_FIELDS, False)))
    after = snapshot(AFTER, state(NATION, "20", AFTER, **dict.fromkeys(POLICY_FIELDS, True)))
    events = by_type(analyze(ANALYZER, before, after), POLICY_CHANGED)
    assert [event.attribute("policy") for event in events] == list(POLICY_FIELDS)
    assert events[2].id == "nation.policy_changed/nation:20/policy_noNukes"
    assert dict(events[2].attributes) == {
        "policy": "policy_noNukes",
        "transition": "changed",
        "before": False,
        "after": True,
    }


def test_unrest_attempts_are_one_event_per_faction_whose_count_differs() -> None:
    before = snapshot(
        BEFORE,
        state(NATION, "20", BEFORE, factionUnrestAttempts=FrozenMap((("faction:15", 1), ("faction:16", 2)))),
        state(EntityDomain.FACTION, "15", BEFORE),
        state(EntityDomain.FACTION, "16", BEFORE),
        state(EntityDomain.FACTION, "17", BEFORE),
    )
    after = snapshot(
        AFTER,
        state(NATION, "20", AFTER, factionUnrestAttempts=FrozenMap((("faction:16", 3), ("faction:17", 1)))),
        state(EntityDomain.FACTION, "15", AFTER),
        state(EntityDomain.FACTION, "16", AFTER),
        state(EntityDomain.FACTION, "17", AFTER),
    )
    events = analyze(ANALYZER, before, after)
    assert {event.id: (event.attribute("before"), event.attribute("after")) for event in events} == {
        "nation.unrest_attempts_changed/nation:20/faction:15": (1, None),
        "nation.unrest_attempts_changed/nation:20/faction:16": (2, 3),
        "nation.unrest_attempts_changed/nation:20/faction:17": (None, 1),
    }
    changed = next(event for event in events if event.id.endswith("faction:16"))
    assert changed.attribute("faction") == named(faction_ref("16"))
    assert [str(ref.entity_id) for ref in changed.entities] == ["nation:20", "faction:16"]
    assert [(s.role, s.change.field, s.member) for s in changed.sources] == [
        (SourceRole.PRIMARY, "factionUnrestAttempts", "faction:16")
    ]


def test_an_unresolved_unrest_map_is_one_low_confidence_event() -> None:
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze([{"Key": {"value": 999}, "Value": 1}]))
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, factionUnrestAttempts=FrozenMap()))
    after = snapshot(AFTER, state(NATION, "20", AFTER, factionUnrestAttempts=unresolved))
    event = only(analyze(ANALYZER, before, after), UNREST_ATTEMPTS_CHANGED)
    assert event.id == "nation.unrest_attempts_changed/nation:20/unresolved"
    assert event.confidence is Confidence.LOW


def new_government(save: str, date: object) -> object:
    return record_set(save, nation_ref("20"), "dateOfNewGovernment", RecordKind.DATE, (ItemEntry(0, date),))  # type: ignore[arg-type]


def test_a_new_government_date_is_record_dated() -> None:
    before = snapshot(BEFORE, state(NATION, "20", BEFORE), records=(new_government(BEFORE, "2030-02-01T00:00:00"),))  # type: ignore[arg-type]
    after = snapshot(AFTER, state(NATION, "20", AFTER), records=(new_government(AFTER, "2031-04-20T00:00:00"),))  # type: ignore[arg-type]
    event = only(analyze(ANALYZER, before, after), NEW_GOVERNMENT_RECORDED)
    assert event.id == "nation.new_government_recorded/nation:20"
    assert (event.date, event.date_basis) == ("2031-04-20T00:00:00", DateBasis.RECORD)
    assert (event.attribute("before"), event.attribute("after")) == ("2030-02-01T00:00:00", "2031-04-20T00:00:00")


def test_presence_carries_the_population_of_the_nations_regions_on_its_side() -> None:
    before = snapshot(
        BEFORE,
        state(NATION, "21", BEFORE, regions=(region_ref("40"), region_ref("41"))),
        state(REGION, "40", BEFORE, populationInMillions=12.5),
        state(REGION, "41", BEFORE, populationInMillions=7),
    )
    after = snapshot(
        AFTER,
        state(NATION, "23", AFTER, regions=(region_ref("40"),)),
        state(NATION, "24", AFTER, regions=(region_ref("41"),)),
        state(REGION, "40", AFTER, populationInMillions=13.0),
        state(REGION, "41", AFTER),
    )
    events = analyze(ANALYZER, before, after)
    population = {event.id: event.attribute("population") for event in events}
    assert population["nation.disappeared/nation:21"] == 19.5
    assert population["nation.appeared/nation:23"] == 13.0
    assert isinstance(population["nation.appeared/nation:24"], Unknown)  # the region carries no population
