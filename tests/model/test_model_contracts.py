"""Construction, equality, unknown-vs-empty and deterministic ordering of the model contracts."""

import json
from dataclasses import FrozenInstanceError, replace

import pytest

from tinarrative.model.changes import ChangeKind, MapDetail, MembershipDetail, RecordsDetail, StateChange, StateDiff
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import (
    SCORE_BANDS,
    SIGNIFICANCE_ORDER,
    Confidence,
    DateBasis,
    Event,
    EventSource,
    EventStatus,
    Role,
    Significance,
    SourceRole,
)
from tinarrative.model.evidence import Evidence, SourceLocation, pointer_path
from tinarrative.model.records import (
    CombatEntry,
    DestructionEntry,
    ItemEntry,
    KeyedEntry,
    LedgerEntry,
    RecordKind,
    RecordSet,
    diff_key,
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


def test_freeze_keeps_scalar_types_and_accepts_subclasses() -> None:
    class Text(str):
        pass

    for scalar in (True, 1, 1.0, "x", None):
        frozen = freeze(scalar)
        assert frozen == scalar
        assert type(frozen) is type(scalar)
    assert freeze([True, 1, 1.0]) == (True, 1, 1.0)
    assert [type(item) for item in freeze([True, 1, 1.0])] == [bool, int, float]  # type: ignore[union-attr]
    assert freeze({"a": {"b": [1]}}) == FrozenMap((("a", FrozenMap((("b", (1,)),))),))
    assert freeze(Text("x")) == "x"
    assert freeze((1, [2])) == (1, (2,))
    assert freeze(_ref("1")) == _ref("1")


def test_to_jsonable_keeps_unknown_visible() -> None:
    assert to_jsonable(Unknown()) == {"unknown": "missing"}
    assert to_jsonable(()) == []
    assert to_jsonable(None) is None


def test_a_reference_reads_as_its_name_and_id_and_serializes_the_name_only_when_it_has_one() -> None:
    bare = _ref("3857")
    named = replace(bare, name="Germany")
    assert bare.label() == "nation:3857"
    assert named.label() == "Germany (nation:3857)"
    assert "name" not in to_jsonable(bare)
    assert to_jsonable(named)["name"] == "Germany"
    keyed = EntityRef(EntityId(EntityDomain.TECHNOLOGY, "FixtureTech"), IdentityConfidence.NAME_KEY, name="FixtureTech")
    assert keyed.label() == "technology:FixtureTech"


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


def test_a_snapshot_indexes_its_states_and_records_once_without_changing_equality() -> None:
    nation, faction = EntityState(_ref("3")), EntityState(_ref("15", EntityDomain.FACTION))
    record = _record("Transactions", RecordKind.LEDGER)
    snapshot = SaveSnapshot(source="a.save", date="d", nations=(nation,), factions=(faction,), records=(record,))
    fresh = replace(snapshot)
    assert snapshot.state_index is snapshot.state_index
    assert snapshot.collection_index is snapshot.collection_index
    assert snapshot.record_index is snapshot.record_index
    assert snapshot.state_index == {nation.ref.entity_id: nation, faction.ref.entity_id: faction}
    assert snapshot.collection_index["nations"] == {nation.ref.entity_id: nation}
    assert snapshot.collection_index["ships"] == {}
    assert snapshot.record_index == {(FACTION.entity_id, "Transactions"): record}
    assert snapshot == fresh and hash(snapshot) == hash(fresh)  # a filled cache is not part of the value
    assert repr(snapshot) == repr(fresh) and snapshot.to_dict() == fresh.to_dict()


def test_a_diff_indexes_its_changes_once() -> None:
    snapshot = SaveSnapshot(source="a.save", date="d")
    diff = StateDiff(before=snapshot, after=snapshot, changes=(_change("gdp"),))
    assert diff.index is diff.index
    assert diff.index.fields(EntityDomain.NATION, "gdp") == diff.changes


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
    assert event.score == 37 and data["score"] == 37  # the default level's base
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
    assert event.constituents == () and data["constituents"] == []  # objective events cite no events


def test_the_score_bands_cover_0_to_100_in_level_order_with_their_midpoints_as_bases() -> None:
    assert tuple(SCORE_BANDS) == SIGNIFICANCE_ORDER
    assert [level.band for level in SIGNIFICANCE_ORDER] == [(0, 24), (25, 49), (50, 74), (75, 100)]
    assert [level.base for level in SIGNIFICANCE_ORDER] == [12, 37, 62, 87]
    edges = {0: "trivial", 24: "trivial", 25: "minor", 49: "minor", 50: "major", 74: "major", 75: "campaign_defining"}
    for score, level in {**edges, 100: "campaign_defining"}.items():
        assert Significance.of(score) is Significance(level), score
    for invalid in (-1, 101, True, 50.0):
        with pytest.raises(ValueError, match="significance score"):
            Significance.of(invalid)  # type: ignore[arg-type]


def test_an_event_score_defaults_to_its_level_base_and_never_leaves_its_band() -> None:
    event = _event(significance=Significance.MAJOR)
    assert event.score == 62 and event.to_dict()["score"] == 62
    assert _event(significance=Significance.MAJOR, score=74).score == 74
    assert replace(event, significance=Significance.TRIVIAL, score=0).score == 0
    with pytest.raises(ValueError, match="score 75 is outside the major band"):
        _event(significance=Significance.MAJOR, score=75)
    with pytest.raises(ValueError, match="outside the trivial band"):
        replace(event, significance=Significance.TRIVIAL)  # a level change must bring its score
    with pytest.raises(ValueError, match="runs 0-100"):
        _event(significance=Significance.CAMPAIGN_DEFINING, score=101)


def _event(**overrides: object) -> Event:
    fields: dict[str, object] = {
        "id": "nation.renamed/nation:1",
        "event_type": "nation.renamed",
        "status": EventStatus.OBJECTIVE,
        "confidence": Confidence.HIGH,
        "date": "2030-02-01",
        "date_basis": DateBasis.INTERVAL,
        "not_before": "2030-01-01",
        "sources": (),
        "entities": (),
        **overrides,
    }
    return Event(**fields)  # type: ignore[arg-type]


def test_inferred_event_constituents_are_sorted_unique_and_serialized() -> None:
    event = Event(
        id="nation.independence/nation:20",
        event_type="nation.independence",
        status=EventStatus.INFERRED,
        confidence=Confidence.MEDIUM,
        date="2030-02-01",
        date_basis=DateBasis.INTERVAL,
        not_before="2030-01-01",
        sources=(_event_source(),),
        entities=(_ref("20"),),
        constituents=(
            "region.nation_changed/region:41",
            "region.nation_changed/region:40",
            "region.nation_changed/region:41",
        ),
    )
    assert event.constituents == ("region.nation_changed/region:40", "region.nation_changed/region:41")
    assert event.to_dict()["constituents"] == list(event.constituents)


def _narrative_event(**overrides: object) -> Event:
    fields: dict[str, object] = {
        "id": "nation.changed.arc/nation:1@2032-04-01T00:00:00",
        "event_type": "nation.changed.arc",
        "status": EventStatus.OBJECTIVE,
        "confidence": Confidence.HIGH,
        "date": "2032-07-01T00:00:00",
        "date_basis": DateBasis.INTERVAL,
        "not_before": "2032-01-01T00:00:00",
        "sources": (),
        "entities": (),
        "start": "2032-01-01T00:00:00",
        "start_basis": DateBasis.INTERVAL,
        "end": "2032-07-01T00:00:00",
        "end_basis": DateBasis.RECORD,
        "intervals": ("2032-04-01T00:00:00", "2032-07-01T00:00:00"),
    }
    fields.update(overrides)
    return Event(**fields)  # type: ignore[arg-type]


def test_an_atomic_event_serializes_without_narrative_fields() -> None:
    atomic = replace(_narrative_event(), intervals=())

    assert not atomic.is_narrative
    assert not {"start", "start_basis", "end", "end_basis", "open", "intervals", "roles"} & set(atomic.to_dict())


def test_a_narrative_event_serializes_its_span_and_sorted_unique_roles() -> None:
    narrative = _narrative_event(
        open=True,
        roles=(
            (Role.TARGET, _ref("2")),
            (Role.ACTOR, _ref("10", EntityDomain.FACTION)),
            (Role.TARGET, _ref("2")),
            (Role.ACTOR, _ref("9", EntityDomain.FACTION)),
        ),
    )

    document = narrative.to_dict()

    assert narrative.is_narrative
    assert (document["start"], document["start_basis"], document["end"], document["end_basis"]) == (
        "2032-01-01T00:00:00",
        "interval",
        "2032-07-01T00:00:00",
        "record",
    )
    assert document["open"] is True
    assert document["intervals"] == ["2032-04-01T00:00:00", "2032-07-01T00:00:00"]
    assert [(role["role"], role["entity"]["ref"]) for role in document["roles"]] == [
        ("actor", "faction:9"),
        ("actor", "faction:10"),
        ("target", "nation:2"),
    ]


def test_a_narrative_event_is_placed_by_its_start() -> None:
    assert _narrative_event().sort_key[0] == "2032-01-01T00:00:00"


def test_a_diff_key_ignores_the_index_but_not_the_entry_type() -> None:
    assert diff_key(ItemEntry(0, "a")) == diff_key(ItemEntry(3, "a"))
    assert diff_key(ItemEntry(0, "a")) != diff_key(ItemEntry(0, "b"))
    assert diff_key(ItemEntry(0, "a")) != diff_key(KeyedEntry(0, "a", None))
    assert diff_key(KeyedEntry(0, "a", None)) != diff_key(DestructionEntry(0, "a", None, None, None))
