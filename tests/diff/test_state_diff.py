"""Behavioral coverage of ``diff_states``: kinds, strict equality, membership, ordering, evidence, determinism."""

import json

import pytest

from tinarrative.diff.render import render_change
from tinarrative.diff.state_diff import (
    ChangeKind,
    MapDetail,
    MembershipDetail,
    RecordsDetail,
    StateChange,
    diff_states,
    strict_equal,
)
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.evidence import SourceLocation
from tinarrative.model.records import (
    CombatEntry,
    DestructionEntry,
    ItemEntry,
    KeyedEntry,
    LedgerEntry,
    NotificationEntry,
    RecordEntry,
    RecordKind,
    RecordSet,
)
from tinarrative.model.snapshot import CampaignMetadata, EntityState, ResearchState, SaveSnapshot
from tinarrative.model.values import FrozenMap, Observed, Unknown, UnknownReason, freeze

BEFORE = "before.json"
AFTER = "after.json"


def ref(key: str, domain: EntityDomain = EntityDomain.NATION, state_type: str = "TINationState") -> EntityRef:
    return EntityRef(EntityId(domain, key), IdentityConfidence.IN_SAVE_ID, state_type=state_type)


def nation(key: str, save: str, name: str | None = None, **values: Observed) -> EntityState:
    entity = EntityRef(EntityId(EntityDomain.NATION, key), IdentityConfidence.IN_SAVE_ID, "TINationState", name)
    location = SourceLocation(save, "TINationState", int(key), f"/gamestates/TINationState/{key}/Value")
    return EntityState(entity, tuple(values.items()), location)


def snapshot(save: str, *nations: EntityState, **extra: object) -> SaveSnapshot:
    return SaveSnapshot(source=save, date="2031-01-01T00:00:00", nations=nations, **extra)  # type: ignore[arg-type]


def changes_of(before: SaveSnapshot, after: SaveSnapshot) -> tuple[StateChange, ...]:
    return diff_states(before, after).changes


def single(before: Observed, after: Observed) -> StateChange | None:
    changes = changes_of(snapshot(BEFORE, nation("1", BEFORE, f=before)), snapshot(AFTER, nation("1", AFTER, f=after)))
    assert len(changes) <= 1
    return changes[0] if changes else None


def test_identical_snapshots_produce_no_changes() -> None:
    before = snapshot(BEFORE, nation("1", BEFORE, GDP=1.0, allies=(ref("2"),)))
    after = snapshot(AFTER, nation("1", AFTER, GDP=1.0, allies=(ref("2"),)))
    result = diff_states(before, after)
    assert result.before is before and result.after is after
    assert result.changes == ()


def test_snapshot_date_is_compared_under_the_campaign_domain() -> None:
    before = SaveSnapshot(source=BEFORE, date="2030-01-01")
    after = SaveSnapshot(source=AFTER, date="2030-02-01")
    (change,) = changes_of(before, after)
    assert (change.domain, change.entity_id, change.field, change.kind) == ("campaign", None, "date", ChangeKind.VALUE)
    assert (change.before, change.after) == ("2030-01-01", "2030-02-01")
    assert change.evidence.before_location == SourceLocation(BEFORE)
    assert change.evidence.after_location == SourceLocation(AFTER)


def test_scalar_transition_is_a_value_change_with_both_locations() -> None:
    change = single(1000.0, 1200.0)
    assert change is not None
    assert change.kind is ChangeKind.VALUE and change.detail is None
    assert (change.before, change.after) == (1000.0, 1200.0)
    assert change.entity_id == EntityId(EntityDomain.NATION, "1")
    assert change.evidence.before_location is not None and change.evidence.before_location.save_id == BEFORE
    assert change.evidence.after_location is not None and change.evidence.after_location.save_id == AFTER
    assert change.evidence.description == "f changed"


@pytest.mark.parametrize(("before", "after"), [(1, 1.0), (True, 1), (0, False), ((1, 2), (1.0, 2)), (None, 0)])
def test_equality_is_strict_about_types(before: Observed, after: Observed) -> None:
    change = single(before, after)
    assert change is not None and change.kind is ChangeKind.VALUE


def test_strict_equality_recurses_into_containers_and_treats_one_object_as_equal_to_itself() -> None:
    nested = (freeze({"a": [1, True]}),)
    assert strict_equal(nested, nested)
    assert strict_equal(nested, (freeze({"a": [1, True]}),))
    assert not strict_equal(nested, (freeze({"a": [1.0, True]}),))
    assert not strict_equal(nested, (freeze({"a": [1, 1]}),))
    assert not strict_equal(freeze({"a": 1}), freeze({"b": 1}))
    assert not strict_equal(Unknown(UnknownReason.UNPARSEABLE, 1), Unknown(UnknownReason.UNPARSEABLE, 1.0))
    assert strict_equal(ref("2"), ref("2")) and not strict_equal(ref("2"), ref("3"))
    nan = float("nan")
    assert strict_equal(nan, nan) and not strict_equal(nan, float("nan"))


def test_a_field_on_one_side_only_is_an_unknown_change_in_name_order() -> None:
    before = snapshot(BEFORE, nation("1", BEFORE, a=1, b=2, c=3))
    after = snapshot(AFTER, nation("1", AFTER, b=2, c=4, d=5))
    changes = changes_of(before, after)
    assert [(change.field, change.kind) for change in changes] == [
        ("a", ChangeKind.UNKNOWN),
        ("c", ChangeKind.VALUE),
        ("d", ChangeKind.UNKNOWN),
    ]


def test_reference_transitions_are_value_changes() -> None:
    assert single(None, ref("2")) is not None
    change = single(ref("2"), ref("3"))
    assert change is not None and change.kind is ChangeKind.VALUE
    assert single(ref("2"), ref("2")) is None


def test_unknown_on_either_side_is_an_unknown_change() -> None:
    change = single(Unknown(), 5)
    assert change is not None and change.kind is ChangeKind.UNKNOWN
    assert change.before == Unknown() and change.after == 5
    assert change.evidence.description == "f is unknown on at least one side"
    assert single(ref("2"), Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 999}))) is not None
    differing_raw = single(
        Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 1})),
        Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 2})),
    )
    assert differing_raw is not None and differing_raw.kind is ChangeKind.UNKNOWN
    assert single(Unknown(), Unknown()) is None
    assert single(Unknown(UnknownReason.MISSING), Unknown(UnknownReason.UNPARSEABLE)) is not None


def test_field_present_on_one_side_only_is_unknown_not_a_default() -> None:
    before = snapshot(BEFORE, nation("1", BEFORE, defended=False))
    after = snapshot(AFTER, nation("1", AFTER))
    (change,) = changes_of(before, after)
    assert (change.field, change.kind, change.before, change.after) == (
        "defended",
        ChangeKind.UNKNOWN,
        False,
        Unknown(),
    )


def test_reference_list_membership_ignores_order_and_sorts_members_naturally() -> None:
    assert single((ref("2"), ref("10")), (ref("10"), ref("2"))) is None
    change = single((ref("2"), ref("10"), ref("10")), (ref("10"), ref("9"), ref("11")))
    assert change is not None and change.kind is ChangeKind.MEMBERSHIP
    assert change.detail == MembershipDetail(added=(ref("9"), ref("11")), removed=(ref("2"), ref("10")))
    assert change.evidence.description == "f membership changed: 2 added, 2 removed"
    assert (change.before, change.after) == ((ref("2"), ref("10"), ref("10")), (ref("10"), ref("9"), ref("11")))


def test_name_list_membership_is_a_multiset_too() -> None:
    change = single(("b", "a"), ("a", "c", "c"))
    assert change is not None and change.kind is ChangeKind.MEMBERSHIP
    assert change.detail == MembershipDetail(added=("c", "c"), removed=("b",))
    assert single((), ("a",)) is not None
    assert single(("a", "b"), ("b", "a")) is None


def test_other_sequences_are_atomic_values() -> None:
    change = single((1, 2, 3), (3, 2, 1))
    assert change is not None and change.kind is ChangeKind.VALUE and change.detail is None
    mixed = single((ref("2"),), ("a",))
    assert mixed is not None and mixed.kind is ChangeKind.VALUE
    maps = single((freeze({"a": 1}),), (freeze({"a": 1}), freeze({"b": 2})))
    assert maps is not None and maps.kind is ChangeKind.VALUE


def test_map_change_names_keys_and_keeps_whole_values() -> None:
    before = freeze({"Money": 10.0, "Influence": 2.5, "Boost": 1})
    after = freeze({"Money": 12.5, "Influence": 2.5, "Water": 0})
    change = single(before, after)
    assert change is not None and change.kind is ChangeKind.MAP
    assert change.detail == MapDetail(added=("Water",), removed=("Boost",), changed=("Money",))
    assert (change.before, change.after) == (before, after)
    assert change.evidence.description == "f map changed: 1 added, 1 removed, 1 changed"
    assert single(FrozenMap((("a", 1),)), FrozenMap((("a", 1.0),))) is not None
    to_null = single(before, None)
    assert to_null is not None and to_null.kind is ChangeKind.VALUE


def test_entity_present_on_one_side_is_absent_not_destroyed() -> None:
    gone = nation("1", BEFORE, GDP=1.0)
    new = nation("2", AFTER, GDP=2.0)
    disappeared, appeared = changes_of(snapshot(BEFORE, gone), snapshot(AFTER, new))
    assert disappeared.kind is ChangeKind.DISAPPEARED and disappeared.field is None
    assert disappeared.entity_id == gone.ref.entity_id
    assert (disappeared.before, disappeared.after) == (gone.ref, Unknown())
    assert disappeared.evidence.before_location == gone.location
    assert disappeared.evidence.after_location == SourceLocation(AFTER)
    assert disappeared.evidence.description == "absent from the after snapshot"
    assert appeared.kind is ChangeKind.APPEARED and appeared.field is None
    assert (appeared.before, appeared.after) == (Unknown(), new.ref)
    assert appeared.evidence.before_location == SourceLocation(BEFORE)
    assert appeared.evidence.after_location == new.location
    assert appeared.evidence.description == "present only in the after snapshot"
    for change in (disappeared, appeared):
        for word in ("destroy", "creat", "purg", "annex"):
            assert word not in change.evidence.description


def test_entities_match_by_id_not_by_display_name() -> None:
    before = snapshot(BEFORE, nation("1", BEFORE, name="Old", displayName="Old"))
    after = snapshot(AFTER, nation("1", AFTER, name="New", displayName="New"))
    (change,) = changes_of(before, after)
    assert (change.field, change.before, change.after) == ("displayName", "Old", "New")
    assert (
        changes_of(snapshot(BEFORE, nation("1", BEFORE, name="Old")), snapshot(AFTER, nation("1", AFTER, name="New")))
        == ()
    )


def test_changes_are_ordered_by_domain_natural_entity_key_and_field() -> None:
    before = snapshot(
        BEFORE,
        nation("9", BEFORE, z=1, a=1),
        nation("10", BEFORE, m=1),
        technologies=(EntityState(tech("B"), (("finished", False),)), EntityState(tech("A"), (("finished", False),))),
        armies=(EntityState(ref("5", EntityDomain.ARMY, "TIArmyState"), (("strength", 1.0),)),),
    )
    after = snapshot(
        AFTER,
        nation("9", AFTER, z=2, a=2),
        nation("10", AFTER, m=2),
        technologies=(EntityState(tech("B"), (("finished", True),)), EntityState(tech("A"), (("finished", True),))),
        armies=(EntityState(ref("5", EntityDomain.ARMY, "TIArmyState"), (("strength", 2.0),)),),
    )
    keys = [(c.domain, str(c.entity_id), c.field) for c in changes_of(before, after)]
    assert keys == [
        ("army", "army:5", "strength"),
        ("nation", "nation:9", "a"),
        ("nation", "nation:9", "z"),
        ("nation", "nation:10", "m"),
        ("technology", "technology:A", "finished"),
        ("technology", "technology:B", "finished"),
    ]


def tech(name: str) -> EntityRef:
    return EntityRef(
        EntityId(EntityDomain.TECHNOLOGY, name), IdentityConfidence.NAME_KEY, "TIGlobalResearchState", name
    )


def test_campaign_metadata_and_research_are_compared_without_an_entity() -> None:
    location = SourceLocation(BEFORE, "TIGlobalResearchState", 150, "/gamestates/x/0/Value")
    before = SaveSnapshot(
        source=BEFORE,
        date="d",
        campaign_day=1,
        campaign=CampaignMetadata(player_faction_name="P", difficulty="Normal"),
        research=ResearchState(finished_techs_names=("A",), campaign_start_year=2030, location=location),
        raw_metadata=(("current_id", 10),),
    )
    after = SaveSnapshot(
        source=AFTER,
        date="d",
        campaign_day=2,
        campaign=CampaignMetadata(player_faction_name="P", difficulty="Hard"),
        research=ResearchState(finished_techs_names=("B", "A"), campaign_start_year=2030),
        raw_metadata=(("current_id", 20),),
    )
    changes = changes_of(before, after)
    assert [(c.domain, c.field, c.kind) for c in changes] == [
        ("campaign", "campaign_day", ChangeKind.VALUE),
        ("campaign", "difficulty", ChangeKind.VALUE),
        ("research", "finished_techs_names", ChangeKind.MEMBERSHIP),
    ]
    assert all(c.entity_id is None for c in changes)
    research = changes[2]
    assert research.detail == MembershipDetail(added=("B",))
    assert research.evidence.before_location == location
    assert research.evidence.after_location == SourceLocation(AFTER)


def test_repeated_runs_are_identical_objects_and_bytes() -> None:
    before = snapshot(BEFORE, nation("1", BEFORE, GDP=1.0, allies=(ref("3"), ref("2"))), nation("2", BEFORE))
    after = snapshot(AFTER, nation("1", AFTER, GDP=2.0, allies=(ref("4"),)), nation("3", AFTER))
    first, second = diff_states(before, after), diff_states(before, after)
    assert first == second
    assert json.dumps(first.to_dict()) == json.dumps(second.to_dict())
    assert len(first.changes) == 4
    for change in first.changes:
        assert change.evidence.before_location is not None and change.evidence.after_location is not None
        assert change.evidence.before == change.before and change.evidence.after == change.after


FACTION = EntityRef(EntityId(EntityDomain.FACTION, "15"), IdentityConfidence.IN_SAVE_ID, "TIFactionState")


def record(
    save: str, field: str, kind: RecordKind, entries: tuple[RecordEntry, ...] | Unknown, owner: EntityRef = FACTION
) -> RecordSet:
    path = f"/gamestates/TIFactionState/0/Value/{field}"
    return RecordSet(owner, field, kind, SourceLocation(save, "TIFactionState", 15, path), entries)


def record_change(before: RecordSet, after: RecordSet) -> StateChange | None:
    changes = changes_of(snapshot(BEFORE, records=(before,)), snapshot(AFTER, records=(after,)))
    assert len(changes) <= 1
    return changes[0] if changes else None


def ledger(index: int, amount: float, date: str) -> LedgerEntry:
    return LedgerEntry(index, "FixtureCause", "Money", amount, date)


def test_appended_log_entries_are_a_records_change_with_counts_and_entries() -> None:
    first, second, third = (
        ledger(0, 1.0, "2031-01-01T00:00:00"),
        ledger(1, 2.0, "2031-02-01T00:00:00"),
        ledger(2, 3.0, "d"),
    )
    before = record(BEFORE, "Transactions", RecordKind.LEDGER, (first, second))
    after = record(AFTER, "Transactions", RecordKind.LEDGER, (first, second, third))
    change = record_change(before, after)
    assert change is not None
    assert (change.domain, change.entity_id, change.field, change.kind) == (
        "faction",
        FACTION.entity_id,
        "Transactions",
        ChangeKind.RECORDS,
    )
    assert (change.before, change.after) == (2, 3)
    assert change.detail == RecordsDetail(added=(third,))
    assert change.evidence.before_location == before.location
    assert change.evidence.after_location == after.location
    assert change.evidence.description == "Transactions records changed: 1 added, 0 removed, 0 changed"
    assert render_change(change) == "faction:15 Transactions: +1 entries"


def test_a_ledger_change_in_skipped_entry_count_still_produces_a_record_change() -> None:
    before = record(BEFORE, "Transactions", RecordKind.LEDGER, (), owner=FACTION)
    after = RecordSet(
        FACTION,
        "Transactions",
        RecordKind.LEDGER,
        SourceLocation(AFTER, "TIFactionState", 15, "/gamestates/TIFactionState/0/Value/Transactions"),
        (),
        skipped_entries=3,
    )
    change = record_change(before, after)
    assert change is not None
    assert (change.before, change.after) == (0, 3)
    assert change.detail == RecordsDetail()
    assert "Money" not in render_change(change) and "FixtureCause" not in render_change(change)


def test_a_violated_prefix_reports_the_missing_entries_literally() -> None:
    kept, dropped = ledger(0, 1.0, "a"), ledger(1, 2.0, "b")
    change = record_change(
        record(BEFORE, "Transactions", RecordKind.LEDGER, (kept, dropped)),
        record(AFTER, "Transactions", RecordKind.LEDGER, (kept,)),
    )
    assert change is not None and change.kind is ChangeKind.RECORDS
    assert change.detail == RecordsDetail(removed=(dropped,))
    assert render_change(change) == "faction:15 Transactions: -1 entries"


def test_log_entries_match_by_content_not_by_index() -> None:
    reordered_before = (ledger(0, 1.0, "a"), ledger(1, 2.0, "b"))
    reordered_after = (ledger(0, 2.0, "b"), ledger(1, 1.0, "a"))
    assert (
        record_change(
            record(BEFORE, "Transactions", RecordKind.LEDGER, reordered_before),
            record(AFTER, "Transactions", RecordKind.LEDGER, reordered_after),
        )
        is None
    )
    duplicated = record_change(
        record(BEFORE, "Transactions", RecordKind.LEDGER, (ledger(0, 1.0, "a"),)),
        record(AFTER, "Transactions", RecordKind.LEDGER, (ledger(0, 1.0, "a"), ledger(1, 1.0, "a"))),
    )
    assert duplicated is not None and duplicated.detail == RecordsDetail(added=(ledger(1, 1.0, "a"),))


def test_log_entries_that_differ_only_by_index_are_unchanged() -> None:
    assert (
        record_change(
            record(
                BEFORE, "HabDestructionLog", RecordKind.DESTRUCTION_LOG, (DestructionEntry(0, "Base", None, 1, None),)
            ),
            record(
                AFTER, "HabDestructionLog", RecordKind.DESTRUCTION_LOG, (DestructionEntry(4, "Base", None, 1, None),)
            ),
        )
        is None
    )


def test_keyed_records_report_added_removed_and_changed_keys() -> None:
    hated = ref("16", EntityDomain.FACTION, "TIFactionState")
    newcomer = ref("17", EntityDomain.FACTION, "TIFactionState")
    gone = ref("18", EntityDomain.FACTION, "TIFactionState")
    before = record(
        BEFORE, "factionHate", RecordKind.REFERENCE_VALUES, (KeyedEntry(0, hated, 0.5), KeyedEntry(1, gone, 1.0))
    )
    after = record(
        AFTER, "factionHate", RecordKind.REFERENCE_VALUES, (KeyedEntry(0, hated, 0.7), KeyedEntry(1, newcomer, 0.1))
    )
    change = record_change(before, after)
    assert change is not None and change.kind is ChangeKind.RECORDS
    assert change.detail == RecordsDetail(
        added=(KeyedEntry(1, newcomer, 0.1),),
        removed=(KeyedEntry(1, gone, 1.0),),
        changed=((KeyedEntry(0, hated, 0.5), KeyedEntry(0, hated, 0.7)),),
    )
    assert render_change(change) == "faction:15 factionHate: +1 -1 ~1 entries"
    same_value_other_index = record(
        AFTER, "factionHate", RecordKind.REFERENCE_VALUES, (KeyedEntry(1, gone, 1.0), KeyedEntry(0, hated, 0.5))
    )
    assert record_change(before, same_value_other_index) is None


def test_keyed_records_with_repeated_keys_fall_back_to_the_multiset_rule() -> None:
    before = record(
        BEFORE, "objectiveNames", RecordKind.LABEL_VALUES, (KeyedEntry(0, "A", "Locked"), KeyedEntry(1, "A", "Locked"))
    )
    after = record(AFTER, "objectiveNames", RecordKind.LABEL_VALUES, (KeyedEntry(0, "A", "Locked"),))
    change = record_change(before, after)
    assert change is not None
    assert change.detail == RecordsDetail(removed=(KeyedEntry(1, "A", "Locked"),))


def test_keyed_value_comparison_is_strict() -> None:
    before = record(BEFORE, "armiesLost", RecordKind.LABEL_VALUES, (KeyedEntry(0, "Human", 1),))
    after = record(AFTER, "armiesLost", RecordKind.LABEL_VALUES, (KeyedEntry(0, "Human", 1.0),))
    change = record_change(before, after)
    assert change is not None and change.detail is not None
    assert isinstance(change.detail, RecordsDetail) and len(change.detail.changed) == 1


def test_scalar_records_are_compared_like_fields() -> None:
    counter = record_change(
        record(BEFORE, "abductions", RecordKind.COUNTER, (ItemEntry(0, 3),)),
        record(AFTER, "abductions", RecordKind.COUNTER, (ItemEntry(0, 5),)),
    )
    assert counter is not None
    assert (counter.kind, counter.before, counter.after, counter.entity_id) == (
        ChangeKind.VALUE,
        3,
        5,
        FACTION.entity_id,
    )
    assert counter.evidence.before_location is not None and counter.evidence.before_location.path.endswith(
        "/abductions"
    )
    assert render_change(counter) == "faction:15 abductions: 3 -> 5"
    other = ref("16", EntityDomain.FACTION, "TIFactionState")
    sharing = record_change(
        record(BEFORE, "intelSharingFactions", RecordKind.REFERENCE_LIST, (ItemEntry(0, ()),)),
        record(AFTER, "intelSharingFactions", RecordKind.REFERENCE_LIST, (ItemEntry(0, (other,)),)),
    )
    assert sharing is not None and sharing.kind is ChangeKind.MEMBERSHIP
    assert sharing.detail == MembershipDetail(added=(other,))
    date = record_change(
        record(BEFORE, "dateOfNewGovernment", RecordKind.DATE, (ItemEntry(0, None),)),
        record(AFTER, "dateOfNewGovernment", RecordKind.DATE, (ItemEntry(0, "2031-04-20T00:00:00"),)),
    )
    assert date is not None and date.kind is ChangeKind.VALUE


def test_unknown_record_sets_are_unknown_changes_or_nothing() -> None:
    known = record(AFTER, "Transactions", RecordKind.LEDGER, (ledger(0, 1.0, "a"), ledger(1, 2.0, "b")))
    change = record_change(record(BEFORE, "Transactions", RecordKind.LEDGER, Unknown()), known)
    assert change is not None
    assert (change.kind, change.before, change.after) == (ChangeKind.UNKNOWN, Unknown(), 2)
    assert render_change(change) == "faction:15 Transactions: unknown (missing) -> 2"
    unparseable = Unknown(UnknownReason.UNPARSEABLE, ())
    assert (
        record_change(
            record(BEFORE, "Transactions", RecordKind.LEDGER, Unknown()),
            record(AFTER, "Transactions", RecordKind.LEDGER, Unknown()),
        )
        is None
    )
    assert (
        record_change(
            record(BEFORE, "Transactions", RecordKind.LEDGER, unparseable),
            record(AFTER, "Transactions", RecordKind.LEDGER, unparseable),
        )
        is None
    )
    missing_to_unparseable = record_change(
        record(BEFORE, "Transactions", RecordKind.LEDGER, Unknown()),
        record(AFTER, "Transactions", RecordKind.LEDGER, unparseable),
    )
    assert missing_to_unparseable is not None and missing_to_unparseable.kind is ChangeKind.UNKNOWN


def test_record_sets_whose_owner_is_on_one_side_only_add_no_changes() -> None:
    only_after = record(AFTER, "Transactions", RecordKind.LEDGER, (ledger(0, 1.0, "a"),))
    changes = changes_of(snapshot(BEFORE), snapshot(AFTER, records=(only_after,)))
    assert changes == ()


def test_record_changes_sort_with_the_owner_entity_field_changes() -> None:
    owner_before = EntityState(FACTION, (("resources", 1.0),), SourceLocation(BEFORE, "TIFactionState", 15))
    owner_after = EntityState(FACTION, (("resources", 2.0),), SourceLocation(AFTER, "TIFactionState", 15))
    before = snapshot(
        BEFORE, factions=(owner_before,), records=(record(BEFORE, "Transactions", RecordKind.LEDGER, ()),)
    )
    after = snapshot(
        AFTER,
        factions=(owner_after,),
        records=(record(AFTER, "Transactions", RecordKind.LEDGER, (ledger(0, 1.0, "a"),)),),
    )
    assert [(c.entity_id, c.field) for c in changes_of(before, after)] == [
        (FACTION.entity_id, "Transactions"),
        (FACTION.entity_id, "resources"),
    ]
    assert json.dumps(diff_states(before, after).to_dict(), sort_keys=True) == json.dumps(
        diff_states(before, after).to_dict(), sort_keys=True
    )


def notification(
    index: int, template: str, date: str, outcome: str = "None", subject: Observed = None
) -> NotificationEntry:
    return NotificationEntry(index, template, date, "Fixture summary.", outcome, subject, False, (FACTION,), (FACTION,))


def notification_change(before: tuple[RecordEntry, ...], after: tuple[RecordEntry, ...]) -> StateChange | None:
    field = "notificationSummaryQueue"
    return record_change(
        record(BEFORE, field, RecordKind.NOTIFICATION_LOG, before),
        record(AFTER, field, RecordKind.NOTIFICATION_LOG, after),
    )


def test_notification_entries_are_added_and_removed_by_key_with_duplicates_as_a_multiset() -> None:
    kept = notification(0, "LogFleetDetected", "2031-01-01T00:00:00")
    dropped = notification(1, "LogHabDestroyed", "2031-01-02T00:00:00")
    added = notification(1, "LogSpaceBattleTakesPlace", "2031-02-01T00:00:00")
    twin = notification(2, "LogSpaceBattleTakesPlace", "2031-02-01T00:00:00")
    change = notification_change((kept, dropped), (kept, added, twin))
    assert change is not None and change.kind is ChangeKind.RECORDS
    assert change.detail == RecordsDetail(added=(added, twin), removed=(dropped,))
    assert notification_change((kept,), (notification(3, "LogFleetDetected", "2031-01-01T00:00:00"),)) is None


def test_a_notification_with_the_same_key_but_another_outcome_is_changed_not_replaced() -> None:
    old = notification(0, "LogMissionOutcome", "2031-01-01T00:00:00")
    new = notification(4, "LogMissionOutcome", "2031-01-01T00:00:00", outcome="Success")
    change = notification_change((old,), (new,))
    assert change is not None and change.detail == RecordsDetail(changed=((old, new),))
    rewritten = notification(0, "LogMissionOutcome", "2031-01-01T00:00:00", subject=FACTION)
    change = notification_change((rewritten,), (old,))
    assert change is not None and change.detail == RecordsDetail(changed=((rewritten, old),))
    other_date = notification(0, "LogMissionOutcome", "2031-01-02T00:00:00")
    replaced = notification_change((old,), (other_date,))
    assert replaced is not None and replaced.detail == RecordsDetail(added=(other_date,), removed=(old,))


def combat_entry(index: int, winner: EntityRef, attacks: Observed = ()) -> CombatEntry:
    sides = ((FACTION, FrozenMap((("FixtureEscort", 2),))),)
    return CombatEntry(index, None, sides, None, winner, attacks, "No")


def test_combat_entries_are_a_multiset_of_their_content() -> None:
    other = ref("16", EntityDomain.FACTION, "TIFactionState")
    kept = combat_entry(0, FACTION)
    dropped = combat_entry(1, other)
    added = combat_entry(1, other, (FrozenMap((("WeaponDataName", "FixtureLaser"),)),))
    twin = combat_entry(2, other, (FrozenMap((("WeaponDataName", "FixtureLaser"),)),))

    def change_of(before: tuple[RecordEntry, ...], after: tuple[RecordEntry, ...]) -> StateChange | None:
        return record_change(
            record(BEFORE, "CombatLogs", RecordKind.COMBAT_LOG, before),
            record(AFTER, "CombatLogs", RecordKind.COMBAT_LOG, after),
        )

    change = change_of((kept, dropped), (kept, added, twin))
    assert change is not None and change.kind is ChangeKind.RECORDS
    assert change.detail == RecordsDetail(added=(added, twin), removed=(dropped,))
    assert change_of((kept,), (combat_entry(7, FACTION),)) is None  # index aside
