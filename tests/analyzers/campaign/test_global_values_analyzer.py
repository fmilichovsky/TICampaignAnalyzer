"""The global-values analyzer on synthetic snapshots: edge cases the fixture pair does not cover."""

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    analyze,
    by_type,
    faction_ref,
    only,
    record_set,
    snapshot,
    state,
    war_ref,
)
from tinarrative.analyzers.campaign import GlobalValuesAnalyzer
from tinarrative.analyzers.politics import WarAnalyzer
from tinarrative.model.entities import EntityDomain, EntityRef
from tinarrative.model.events import Confidence, Event
from tinarrative.model.records import ItemEntry, KeyedEntry, RecordEntry, RecordKind, RecordSet
from tinarrative.model.snapshot import EntityState, SaveSnapshot
from tinarrative.model.values import Observed, Unknown, UnknownReason

KEY = "70"


def singleton(save: str, **fields: Observed) -> EntityState:
    return state(EntityDomain.GLOBAL_VALUES, KEY, save, **fields)


def owner(save: str) -> EntityRef:
    return singleton(save).ref


def records(save: str, field: str, kind: RecordKind, *entries: RecordEntry) -> RecordSet:
    return record_set(save, owner(save), field, kind, entries)


def run_records(
    field: str, kind: RecordKind, before: tuple[RecordEntry, ...], after: tuple[RecordEntry, ...]
) -> list[Event]:
    return analyze(
        GlobalValuesAnalyzer(),
        snapshot(BEFORE, singleton(BEFORE), records=(records(BEFORE, field, kind, *before),)),
        snapshot(AFTER, singleton(AFTER), records=(records(AFTER, field, kind, *after),)),
    )


MILESTONES = ("globalMilestones", RecordKind.LABELLED_REFERENCES)
UNRESOLVED = Unknown(UnknownReason.UNRESOLVED_REFERENCE, None)


def test_a_milestone_recorded_for_another_faction_is_a_literal_change() -> None:
    events = run_records(
        *MILESTONES,
        (KeyedEntry(0, "FirstWarship", faction_ref("15")),),
        (KeyedEntry(0, "FirstWarship", faction_ref("16")),),
    )
    event = only(events, "campaign.global_milestone_changed")
    assert event.attribute("transition") == "changed"
    assert (event.attribute("before"), event.attribute("after")) == (faction_ref("15"), faction_ref("16"))
    assert not by_type(events, "campaign.global_value_changed")


def test_a_removed_milestone_is_reported_literally_not_explained() -> None:
    events = run_records(*MILESTONES, (KeyedEntry(0, "FirstWarship", faction_ref("15")),), ())
    event = only(events, "campaign.global_value_changed")
    assert (event.attribute("field"), event.attribute("removed")) == ("globalMilestones", 1)
    assert not by_type(events, "campaign.global_milestone_recorded")


def test_an_unresolved_milestone_faction_has_low_confidence() -> None:
    events = run_records(*MILESTONES, (), (KeyedEntry(0, "FirstWarship", UNRESOLVED),))
    event = only(events, "campaign.global_milestone_recorded")
    assert event.confidence is Confidence.LOW
    assert [str(ref.entity_id) for ref in event.entities] == [f"global values:{KEY}"]


def test_a_repeated_once_per_campaign_name_gets_distinct_events() -> None:
    field = ("triggeredOncePerCampaignEvents", RecordKind.NAME_LOG)
    events = run_records(*field, (), (ItemEntry(0, "event_A"), ItemEntry(1, "event_A")))
    assert len(by_type(events, "campaign.narrative_event_triggered")) == 2


def test_a_target_list_that_only_shrank_is_a_literal_change() -> None:
    field = ("triggeredOncePerTargetEvents", RecordKind.LABELLED_REFERENCES)
    events = run_records(
        *field,
        (KeyedEntry(0, "event_T", (faction_ref("15"), faction_ref("16"))),),
        (KeyedEntry(0, "event_T", (faction_ref("15"),)),),
    )
    assert not by_type(events, "campaign.narrative_event_triggered")
    assert only(events, "campaign.global_value_changed").attribute("changed") == 1


def test_a_target_list_that_grew_names_only_the_new_targets() -> None:
    field = ("triggeredOncePerTargetEvents", RecordKind.LABELLED_REFERENCES)
    events = run_records(
        *field,
        (KeyedEntry(0, "event_T", (faction_ref("15"),)),),
        (KeyedEntry(0, "event_T", (faction_ref("15"), faction_ref("16"))),),
    )
    event = only(events, "campaign.narrative_event_triggered")
    assert event.attribute("targets") == (faction_ref("16"),)


def test_a_sea_level_flag_cleared_is_not_a_rise() -> None:
    events = analyze(
        GlobalValuesAnalyzer(),
        snapshot(BEFORE, singleton(BEFORE, globalSeaLevelRise2Triggered=True)),
        snapshot(AFTER, singleton(AFTER, globalSeaLevelRise2Triggered=False)),
    )
    assert not by_type(events, "campaign.sea_level_rise_triggered")
    assert only(events, "campaign.global_value_changed").attribute("field") == "globalSeaLevelRise2Triggered"


def test_a_field_missing_on_one_side_is_a_schema_gap_not_a_change() -> None:
    events = analyze(
        GlobalValuesAnalyzer(),
        snapshot(BEFORE, singleton(BEFORE)),
        snapshot(AFTER, singleton(AFTER, bestGlobalHumanEducation=2.5)),
    )
    assert events == []


def test_the_singleton_appearing_is_reported() -> None:
    events = analyze(GlobalValuesAnalyzer(), snapshot(BEFORE), snapshot(AFTER, singleton(AFTER)))
    assert only(events, "campaign.global_values_appeared").attribute("side") == "after"


def test_an_interstate_wars_member_no_war_explains_is_a_leftover_of_the_war_analyzer() -> None:
    war_before = state(EntityDomain.WAR, "90", BEFORE)
    war_after = state(EntityDomain.WAR, "90", AFTER)
    events = analyze(
        WarAnalyzer(),
        snapshot(BEFORE, war_before, singleton(BEFORE, interstateWars=())),
        snapshot(AFTER, war_after, singleton(AFTER, interstateWars=(war_ref("90"),))),
    )
    event = only(events, "campaign.interstate_wars_changed")
    assert event.attribute("transition") == "added" and event.attribute("member") == war_ref("90")
    assert analyze(GlobalValuesAnalyzer(), *_war_pair()) == []


def _war_pair() -> tuple[SaveSnapshot, SaveSnapshot]:
    return (
        snapshot(BEFORE, singleton(BEFORE, interstateWars=())),
        snapshot(AFTER, singleton(AFTER, interstateWars=(war_ref("90"),))),
    )
