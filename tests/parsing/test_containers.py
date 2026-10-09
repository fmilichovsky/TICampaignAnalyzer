"""Pair-map container decoding per containers-and-references.md."""

import pytest

from tinarrative.identity import STATE_PREFIX
from tinarrative.parsing.containers import StateEntry, decode_state_map, entry_path
from tinarrative.parsing.errors import UnsupportedSaveShapeError

NATION = STATE_PREFIX + "TINationState"


def pair(key: object, inner: object, **fields: object) -> dict[str, object]:
    return {"Key": {"value": key}, "Value": {"ID": {"value": inner}, **fields}}


def test_absent_and_empty_object_containers_decode_to_no_entries() -> None:
    assert decode_state_map({}, "TINationState") == ()
    assert decode_state_map({NATION: {}}, "TINationState") == ()
    assert decode_state_map({NATION: []}, "TINationState") == ()


def test_pair_array_decodes_to_entries_in_serialized_order() -> None:
    entries = decode_state_map({NATION: [pair(7, 7, a=1), pair(3, 3)]}, "TINationState")
    assert entries == (
        StateEntry(7, 0, {"ID": {"value": 7}, "a": 1}),
        StateEntry(3, 1, {"ID": {"value": 3}}),
    )


@pytest.mark.parametrize(
    ("container", "message"),
    [
        ("text", "expected a pair array"),
        ({"Key": 1}, "expected a pair array"),
        (["not an entry"], "not a Key/Value object"),
        ([{"Key": {"value": 3}}], "missing integer"),
        ([pair("3", 3)], "missing integer"),
        ([pair(True, True)], "missing integer"),
        ([pair(1, 2)], "Key.value 1 != Value.ID.value 2"),
        ([pair(1, 1), pair(1, 1)], "duplicate map ID 1"),
    ],
)
def test_malformed_containers_are_rejected(container: object, message: str) -> None:
    with pytest.raises(UnsupportedSaveShapeError, match=message) as info:
        decode_state_map({NATION: container}, "TINationState")
    assert NATION in str(info.value)


def test_entry_path_is_an_rfc6901_pointer() -> None:
    assert entry_path(NATION, 4) == f"/gamestates/{NATION}/4/Value"
    assert entry_path("a/b~c", 0) == "/gamestates/a~1b~0c/0/Value"
