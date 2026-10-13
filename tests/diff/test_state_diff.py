"""Behavioral coverage of ``diff_states``: kinds, strict equality, membership, ordering, evidence, determinism."""

import json

import pytest

from tinarrative.diff.state_diff import ChangeKind, MapDetail, MembershipDetail, StateChange, diff_states
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.evidence import SourceLocation
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
