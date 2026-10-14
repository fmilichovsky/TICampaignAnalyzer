"""Decode the observed typed-state pair-map containers.

See ``docs/game-data-notes/containers-and-references.md``: a populated state collection is an array of
``{"Key": {"value": id}, "Value": {"ID": {"value": id}, ...}}`` pairs, and an empty one is ``{}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..identity import STATE_PREFIX, read_id_value
from ..model.evidence import pointer_path
from .errors import UnsupportedSaveShapeError


@dataclass(frozen=True)
class StateEntry:
    """One decoded pair: its map ID, its index in the serialized array, and the ``Value`` object."""

    map_id: int
    index: int
    value: dict[str, Any]


def entry_path(full_type: str, index: int) -> str:
    """RFC 6901 pointer to one entry's ``Value`` object."""
    return pointer_path("/gamestates", full_type, index, "Value")


def decode_pair_map(value: Any) -> tuple[tuple[Any, Any], ...] | None:
    """Decode a field-level dictionary (``containers-and-references.md``, "Field-level dictionaries").

    An empty dictionary serializes as ``{}`` and a populated one as an array of ``{"Key", "Value"}`` objects;
    both decode to ``(key, value)`` pairs in serialized order. Any other value, including an array with one
    element that is not such an object, returns ``None`` so the caller can report the shape.
    """
    if value == {}:
        return ()
    if not isinstance(value, list):
        return None
    pairs: list[tuple[Any, Any]] = []
    for item in value:
        if not isinstance(item, dict) or "Key" not in item or "Value" not in item:
            return None
        pairs.append((item["Key"], item["Value"]))
    return tuple(pairs)


def decode_state_map(gamestates: dict[str, Any], short_type: str) -> tuple[StateEntry, ...]:
    """Return the entries of one state type; absent or ``{}`` containers are empty.

    Raises ``UnsupportedSaveShapeError`` for a non-empty container that does not follow the documented
    pair shape, whose ``Key.value`` and ``Value.ID.value`` disagree, or that repeats an ID.
    """
    full_type = STATE_PREFIX + short_type
    return decode_container(full_type, gamestates.get(full_type))


def decode_container(full_type: str, container: Any) -> tuple[StateEntry, ...]:
    """Decode one serialized state collection under its exact ``gamestates`` key (see ``decode_state_map``)."""
    if container is None or container == {}:
        return ()
    if not isinstance(container, list):
        raise UnsupportedSaveShapeError(f"{full_type}: expected a pair array or {{}}, got {type(container).__name__}")
    entries: list[StateEntry] = []
    seen: set[int] = set()
    for index, entry in enumerate(container):
        if not isinstance(entry, dict):
            raise UnsupportedSaveShapeError(f"{full_type}[{index}]: entry is not a Key/Value object")
        value = entry.get("Value")
        key_id = read_id_value(entry.get("Key"))
        inner_id = read_id_value(value.get("ID")) if isinstance(value, dict) else None
        if key_id is None or inner_id is None or not isinstance(value, dict):
            raise UnsupportedSaveShapeError(f"{full_type}[{index}]: missing integer Key.value or Value.ID.value")
        if key_id != inner_id:
            raise UnsupportedSaveShapeError(f"{full_type}[{index}]: Key.value {key_id} != Value.ID.value {inner_id}")
        if key_id in seen:
            raise UnsupportedSaveShapeError(f"{full_type}[{index}]: duplicate map ID {key_id}")
        seen.add(key_id)
        entries.append(StateEntry(map_id=key_id, index=index, value=value))
    return tuple(entries)
