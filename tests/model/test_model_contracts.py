"""Construction, equality, unknown-vs-empty and deterministic ordering of the model contracts."""

import json
from dataclasses import FrozenInstanceError

import pytest

from tinarrative.model.changes import ChangeKind, MapDetail, MembershipDetail, RecordsDetail, StateChange, StateDiff
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import Confidence, DateBasis, Event, EventSource, EventStatus, Significance, SourceRole
from tinarrative.model.evidence import Evidence, SourceLocation, pointer_path
from tinarrative.model.records import (
    CombatEntry,
    DestructionEntry,
    ItemEntry,
    KeyedEntry,
    LedgerEntry,
    RecordKind,
    RecordSet,
    record_counts,
)
from tinarrative.model.snapshot import STATE_COLLECTIONS, EntityState, ResearchState, SaveSnapshot
from tinarrative.model.values import FrozenMap, Unknown, UnknownReason, freeze, is_unknown, to_jsonable


def _ref(key: str, domain: EntityDomain = EntityDomain.NATION) -> EntityRef:
    return EntityRef(EntityId(domain, key), IdentityConfidence.IN_SAVE_ID, "TINationState")


def _change(field: str, key: str = "123") -> StateChange:
    before_loc = SourceLocation("a.save", "TINationState", int(key), "/gamestates/x/Value/population")
    after_loc = SourceLocation("b.save", "TINationState", int(key), "/gamestates/x/Value/population")
    return StateChange(
        domain="nation",
        field=field,
        before=1,
        after=Unknown(),
        evidence=Evidence("nation", "population", 1, Unknown(), before_loc, after_loc),
        entity_id=EntityId(EntityDomain.NATION, key),
    )


@pytest.mark.parametrize("known", [None, False, 0, "", ()])
def test_unknown_is_distinct_from_known_values(known: object) -> None:
    assert Unknown() != known
    assert not is_unknown(known)  # type: ignore[arg-type]
    assert is_unknown(Unknown(UnknownReason.UNRESOLVED_REFERENCE))


def test_freeze_is_hashable_and_deterministic() -> None:
    assert freeze({"b": [1, 2], "a": None}) == freeze({"a": None, "b": [1, 2]})
    assert isinstance(freeze({"a": [1]}), FrozenMap)
    assert hash(freeze({"a": [1]})) == hash(freeze({"a": [1]}))
    with pytest.raises(TypeError):
        freeze(object())


def test_to_jsonable_keeps_unknown_visible() -> None:
    assert to_jsonable(Unknown()) == {"unknown": "missing"}
    assert to_jsonable(()) == []
    assert to_jsonable(None) is None


def test_unresolved_reference_keeps_its_raw_value() -> None:
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 999}))
    assert is_unknown(unresolved)
    assert unresolved != Unknown(UnknownReason.UNRESOLVED_REFERENCE)
    assert to_jsonable(unresolved) == {"unknown": "unresolved_reference", "raw": {"value": 999}}


def test_entity_ref_is_a_field_value() -> None:
    ref = _ref("4")
    assert freeze(ref) is ref
    assert freeze([ref]) == (ref,)
    assert to_jsonable(ref) == {"ref": "nation:4", "state_type": "TINationState", "confidence": "in-save-id"}
    assert to_jsonable((ref,)) == [to_jsonable(ref)]


def test_entity_id_is_domain_qualified() -> None:
    assert EntityId(EntityDomain.NATION, "1") != EntityId(EntityDomain.REGION, "1")
    assert str(EntityId(EntityDomain.NATION, "1")) == "nation:1"
    assert _ref("1") != EntityRef(EntityId(EntityDomain.NATION, "1"), IdentityConfidence.NAME_KEY, "TINationState")


def test_change_traces_to_values_and_locations() -> None:
    change = _change("population")
    assert change.evidence.before_location is not None
    assert change.evidence.before_location.provenance_key == "TINationState:123"
    assert change.evidence.after_location is not None
    assert change.evidence.after_location.save_id == "b.save"
    assert change.before == 1
    assert is_unknown(change.after)
    assert SourceLocation("a.save").provenance_key is None


def test_diff_orders_changes_deterministically() -> None:
    before = SaveSnapshot(source="a.save", date="2030-01-01")
    after = SaveSnapshot(source="b.save", date="2030-02-01")
    changes = [_change("z", "2"), _change("a", "2"), _change("m", "10"), _change("m", "9")]
    forward = StateDiff(before, after, tuple(changes))
    backward = StateDiff(before, after, tuple(reversed(changes)))
    assert forward == backward
    assert [(c.entity_id.key if c.entity_id else None, c.field) for c in forward.changes] == [
        ("2", "a"),
        ("2", "z"),
        ("9", "m"),
        ("10", "m"),
    ]
    assert json.dumps(forward.to_dict()) == json.dumps(backward.to_dict())
    assert forward.to_dict()["before_date"] == "2030-01-01"


def test_change_kind_detail_and_absent_field_serialize() -> None:
    plain = _change("population")
    assert plain.kind is ChangeKind.VALUE and plain.detail is None
    data = plain.to_dict()
    assert (data["kind"], data["detail"], data["description"]) == ("value", None, "population")
    presence = StateChange(
        domain="nation",
        field=None,
        before=Unknown(),
        after=_ref("7"),
        evidence=Evidence("nation", "present only in the after snapshot", Unknown(), _ref("7")),
        entity_id=EntityId(EntityDomain.NATION, "7"),
        kind=ChangeKind.APPEARED,
    )
    assert presence.sort_key == ("nation", 0, 1, "7", "")
    assert presence.to_dict()["field"] is None
    assert presence.to_dict()["kind"] == "appeared"
    membership = StateChange(
        domain="nation",
        field="allies",
        before=(),
        after=(_ref("2"),),
        evidence=Evidence("nation", "allies membership changed: 1 added, 0 removed", (), (_ref("2"),)),
        entity_id=EntityId(EntityDomain.NATION, "7"),
        kind=ChangeKind.MEMBERSHIP,
        detail=MembershipDetail(added=(_ref("2"),)),
    )
    assert membership.to_dict()["detail"] == {"added": [to_jsonable(_ref("2"))], "removed": []}
    assert MapDetail(changed=("Money",)).to_dict() == {"added": [], "removed": [], "changed": ["Money"]}
    assert isinstance(hash(membership), int)
    name_keyed = EntityId(EntityDomain.TECHNOLOGY, "Alpha").sort_key
    assert EntityId(EntityDomain.TECHNOLOGY, "9").sort_key < name_keyed


def test_snapshot_orders_collections_and_is_immutable() -> None:
    states = (EntityState(_ref("20")), EntityState(_ref("3")))
    snapshot = SaveSnapshot(source="a.save", date="2030-01-01", **{name: states for name in STATE_COLLECTIONS})
    reversed_states = tuple(reversed(states))
    assert snapshot == SaveSnapshot(
        source="a.save", date="2030-01-01", **{name: reversed_states for name in STATE_COLLECTIONS}
    )
    assert {"fleets", "ships", "habs", "technologies"} <= set(STATE_COLLECTIONS)
    for name in STATE_COLLECTIONS:
        assert [s.ref.entity_id.key for s in getattr(snapshot, name)] == ["3", "20"]  # natural, not lexical
    with pytest.raises(FrozenInstanceError):
        snapshot.source = "x"  # type: ignore[misc]
    assert isinstance(hash(snapshot), int)


def test_missing_field_differs_from_known_empty() -> None:
    state = EntityState(_ref("1"), fields=(("allies", ()), ("at_war", False)))
    assert state.get("allies") == ()
    assert state.get("at_war") is False
    assert state.get("borders") == Unknown()
    snapshot = SaveSnapshot(source="a.save", date="d", nations=(state,))
    data = snapshot.to_dict()
    assert json.loads(json.dumps(data)) == data
    assert data["campaign"]["difficulty"] == {"unknown": "missing"}
    assert data["campaign"]["scenario_template"] == {"unknown": "missing"}
    assert data["date"] == "d"
    assert data["campaign_day"] == {"unknown": "missing"}
    assert data["control_points"] == []
    assert data["nations"][0]["fields"] == {"allies": [], "at_war": False}


def test_snapshot_serialization_keeps_state_provenance() -> None:
    location = SourceLocation("a.save", "TINationState", 7, "/gamestates/x/0")
    snapshot = SaveSnapshot(source="a.save", date="d", nations=(EntityState(_ref("7"), location=location),))
    entry = snapshot.to_dict()["nations"][0]
    assert entry["state_type"] == "TINationState"
    assert entry["location"] == location.to_dict()


def test_research_state_defaults_to_unknown_and_serializes_with_its_location() -> None:
    empty = ResearchState()
    assert empty.finished_techs_names == Unknown()
    assert empty.tech_progress == Unknown()
    assert empty.location is None
    assert empty.to_dict()["campaign_start_year"] == {"unknown": "missing"}
    assert empty.to_dict()["location"] is None
    location = SourceLocation("a.save", "TIGlobalResearchState", 150, "/gamestates/x/0/Value")
    research = ResearchState(finished_techs_names=("A", "B"), campaign_start_year=2030, location=location)
    data = SaveSnapshot(source="a.save", date="d", research=research).to_dict()["research"]
    assert data == {
        "finished_techs_names": ["A", "B"],
        "finished_one_time_only_project_names": {"unknown": "missing"},
        "tech_progress": {"unknown": "missing"},
        "campaign_start_year": 2030,
        "end_game_techs_completed_by_category": {"unknown": "missing"},
        "location": location.to_dict(),
    }
    assert SaveSnapshot(source="a.save", date="d").research == empty
    with pytest.raises(FrozenInstanceError):
        research.campaign_start_year = 1  # type: ignore[misc]


FACTION = EntityRef(EntityId(EntityDomain.FACTION, "15"), IdentityConfidence.IN_SAVE_ID, "TIFactionState")
FIELD_LOCATION = SourceLocation("a.save", "TIFactionState", 15, "/gamestates/x/0/Value/Transactions")


def _record(field: str, kind: RecordKind, *entries: object, key: str = "15") -> RecordSet:
    owner = EntityRef(EntityId(EntityDomain.FACTION, key), IdentityConfidence.IN_SAVE_ID, "TIFactionState")
    location = SourceLocation("a.save", "TIFactionState", int(key), f"/gamestates/x/0/Value/{field}")
    return RecordSet(owner, field, kind, location, tuple(entries))  # type: ignore[arg-type]


def test_pointer_path_escapes_tokens() -> None:
    assert pointer_path("/gamestates", "a/b~c", 0, "Value") == "/gamestates/a~1b~0c/0/Value"
    assert pointer_path("") == ""


def test_record_set_defaults_to_unknown_entries_and_is_immutable() -> None:
    missing = RecordSet(FACTION, "Transactions", RecordKind.LEDGER, FIELD_LOCATION)
    assert missing.entries == Unknown()
    assert missing.to_dict()["entries"] == {"unknown": "missing"}
    assert missing.to_dict()["owner"] == "faction:15"
    assert missing.to_dict()["location"] == FIELD_LOCATION.to_dict()
    with pytest.raises(FrozenInstanceError):
        missing.field = "x"  # type: ignore[misc]
    assert isinstance(hash(missing), int)
    assert record_counts(
        [missing, _record("milestones", RecordKind.NAME_LOG, ItemEntry(0, "A"), ItemEntry(1, "B"))]
    ) == (1, 2)


def test_record_entries_locate_by_label_index_or_key() -> None:
    ledger = _record("Transactions", RecordKind.LEDGER, LedgerEntry(2, "Cause/With~Slash", "Money", 1.0, "d"))
    assert ledger.entry_location(ledger.entries[0]).path == "/gamestates/x/0/Value/Transactions/Cause~1With~0Slash/2"  # type: ignore[index]
    assert ledger.entry_location(ledger.entries[0]).provenance_key == "TIFactionState:15"  # type: ignore[index]
    destruction = _record("HabDestructionLog", RecordKind.DESTRUCTION_LOG, DestructionEntry(1, "Base", None, "d", None))
    assert destruction.entry_location(destruction.entries[0]).path.endswith("/HabDestructionLog/1")  # type: ignore[index]
    combat = _record("CombatLogs", RecordKind.COMBAT_LOG, CombatEntry(4, None, (), None, FACTION, (), "No"))
    assert combat.entry_location(combat.entries[0]).path.endswith("/CombatLogs/4")  # type: ignore[index]
    pair_map = _record("factionHate", RecordKind.REFERENCE_VALUES, KeyedEntry(3, FACTION, 0.5))
    assert pair_map.entry_location(pair_map.entries[0]).path.endswith("/factionHate/3")  # type: ignore[index]
    label_map = _record("armiesLost", RecordKind.LABEL_VALUES, KeyedEntry(0, "Human", 1))
    assert label_map.entry_location(label_map.entries[0]).path.endswith("/armiesLost/Human")  # type: ignore[index]
    scalar = _record("abductions", RecordKind.COUNTER, ItemEntry(0, 3))
    assert scalar.entry_location(scalar.entries[0]).path == "/gamestates/x/0/Value/abductions"  # type: ignore[index]


def test_snapshot_orders_records_by_owner_then_field_and_serializes_them() -> None:
    later = _record("milestones", RecordKind.NAME_LOG, ItemEntry(0, "A"), key="20")
    second = _record("milestones", RecordKind.NAME_LOG, key="3")
    first = _record("Transactions", RecordKind.LEDGER, key="3")
    snapshot = SaveSnapshot(source="a.save", date="d", records=(later, second, first))
    assert snapshot.records == (first, second, later)
    assert snapshot == SaveSnapshot(source="a.save", date="d", records=(first, later, second))
    data = snapshot.to_dict()
    assert json.loads(json.dumps(data)) == data
    assert [(r["owner"], r["field"], r["kind"]) for r in data["records"]] == [
        ("faction:3", "Transactions", "ledger"),
        ("faction:3", "milestones", "name_log"),
        ("faction:20", "milestones", "name_log"),
    ]
    assert data["records"][2]["entries"] == [{"index": 0, "value": "A"}]
    assert SaveSnapshot(source="a.save", date="d").records == ()


def test_records_detail_serializes_entries_and_changed_pairs() -> None:
    before, after = KeyedEntry(0, "Human", 0), KeyedEntry(0, "Human", 1)
    detail = RecordsDetail(added=(ItemEntry(1, "B"),), changed=((before, after),))
    assert detail.to_dict() == {
        "added": [{"index": 1, "value": "B"}],
        "removed": [],
        "changed": [
            {"before": {"index": 0, "key": "Human", "value": 0}, "after": {"index": 0, "key": "Human", "value": 1}}
        ],
    }
    assert ChangeKind.RECORDS.value == "records"
    assert isinstance(hash(detail), int)


def _event_source(role: SourceRole = SourceRole.PRIMARY, member: object = None) -> EventSource:
    change = _change("allies", "20")
    return EventSource(change, role, member, SourceLocation("b.save", "TINationState", 20, "/x/allies/0"))  # type: ignore[arg-type]


def test_event_sorts_its_parts_and_serializes_json_friendly() -> None:
    later = _event_source(SourceRole.CORROBORATING)
    earlier = _event_source(SourceRole.PRIMARY, _ref("2"))
    event = Event(
        id="nation.relation_changed/nation:20/allies/nation:2/added",
        event_type="nation.relation_changed",
        status=EventStatus.OBJECTIVE,
        confidence=Confidence.HIGH,
        date="2030-02-01",
        date_basis=DateBasis.INTERVAL,
        not_before="2030-01-01",
        sources=(later, earlier),
        entities=(_ref("20"), _ref("2"), _ref("20")),
        attributes=(("transition", "added"), ("relation", "allies"), ("raw", Unknown())),
    )
    assert event.sources == (earlier, later)  # primary first
    assert event.entities == (_ref("20"), _ref("2"))  # order kept (subject first), duplicates dropped
    assert [key for key, _ in event.attributes] == ["raw", "relation", "transition"]
    assert event.attribute("relation") == "allies" and event.attribute("missing") == Unknown()
    assert event.sort_key == ("2030-02-01", "nation.relation_changed", event.id)
    data = event.to_dict()
    assert json.loads(json.dumps(data)) == data
    assert data["date_basis"] == "interval" and data["attributes"]["raw"] == {"unknown": "missing"}
    assert event.significance is Significance.MINOR and data["significance"] == "minor"  # analyzers leave the default
    assert data["sources"][0] == {
        "role": "primary",
        "member": to_jsonable(_ref("2")),
        "entry": {"save_id": "b.save", "state_type": "TINationState", "map_id": 20, "path": "/x/allies/0"},
        "change": earlier.change.to_dict(),
    }
    assert isinstance(hash(event), int)
    with pytest.raises(FrozenInstanceError):
        event.id = "x"  # type: ignore[misc]
    undated = Event(**{**event.__dict__, "date": Unknown(), "date_basis": DateBasis.RECORD})
    assert undated.sort_key[0] == "" and undated.sort_key < event.sort_key
    assert undated.to_dict()["date"] == {"unknown": "missing"}
