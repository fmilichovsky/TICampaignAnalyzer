"""Construction, equality, unknown-vs-empty and deterministic ordering of the model contracts."""

import json
from dataclasses import FrozenInstanceError

import pytest

from tinarrative.model.changes import StateChange, StateDiff
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.evidence import Evidence, SourceLocation
from tinarrative.model.snapshot import EntityState, SaveSnapshot
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
    changes = [_change("z", "2"), _change("a", "2"), _change("m", "1")]
    forward = StateDiff(before, after, tuple(changes))
    backward = StateDiff(before, after, tuple(reversed(changes)))
    assert forward == backward
    assert [c.field for c in forward.changes] == ["m", "a", "z"]
    assert json.dumps(forward.to_dict()) == json.dumps(backward.to_dict())


def test_snapshot_orders_collections_and_is_immutable() -> None:
    states = (EntityState(_ref("20")), EntityState(_ref("3")))
    snapshot = SaveSnapshot(source="a.save", date="2030-01-01", nations=states)
    assert snapshot == SaveSnapshot(source="a.save", date="2030-01-01", nations=tuple(reversed(states)))
    assert [s.ref.entity_id.key for s in snapshot.nations] == ["20", "3"]
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
    assert data["nations"][0]["fields"] == {"allies": [], "at_war": False}


def test_snapshot_serialization_keeps_state_provenance() -> None:
    location = SourceLocation("a.save", "TINationState", 7, "/gamestates/x/0")
    snapshot = SaveSnapshot(source="a.save", date="d", nations=(EntityState(_ref("7"), location=location),))
    entry = snapshot.to_dict()["nations"][0]
    assert entry["state_type"] == "TINationState"
    assert entry["location"] == location.to_dict()
