"""Explicit known/unknown value representation.

A field that the save does not provide is ``Unknown``; it is never coerced to ``False``, zero, or an
empty collection. ``None`` is a *known* JSON null, and ``()`` is a *known* empty sequence. A resolved
in-save reference is an ``EntityRef``; an unresolved one is ``Unknown`` carrying the raw serialized value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Union

from .entities import EntityRef


class UnknownReason(StrEnum):
    MISSING = "missing"
    UNRESOLVED_REFERENCE = "unresolved_reference"
    UNPARSEABLE = "unparseable"


@dataclass(frozen=True)
class FrozenMap:
    """Immutable, hashable mapping with items sorted by key."""

    items: tuple[tuple[str, FieldValue], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(sorted(self.items, key=lambda item: item[0])))


FieldValue = Union[None, bool, int, float, str, tuple["FieldValue", ...], FrozenMap, EntityRef]  # noqa: UP007  (recursive alias needs a runtime Union)


@dataclass(frozen=True)
class Unknown:
    """A value the save did not establish; ``raw`` keeps what was serialized, if anything."""

    reason: UnknownReason = UnknownReason.MISSING
    raw: FieldValue = None


Observed = Union[FieldValue, Unknown]  # noqa: UP007  (recursive alias needs a runtime Union)


def is_unknown(value: Observed) -> bool:
    return isinstance(value, Unknown)


def freeze(value: Any) -> FieldValue:
    """Convert decoded JSON (lists/dicts) into an immutable, deterministic value."""
    kind = type(value)
    # Exact-type checks first: decoded JSON is almost all plain scalars, and the union isinstance below is slower.
    if kind is str or kind is int or kind is float or kind is bool or value is None:
        return value  # type: ignore[no-any-return]
    if kind is list:
        return tuple(freeze(item) for item in value)
    if kind is dict:
        return FrozenMap(tuple((str(key), freeze(item)) for key, item in value.items()))
    if value is None or isinstance(value, bool | int | float | str | EntityRef):
        return value
    if isinstance(value, list | tuple):
        return tuple(freeze(item) for item in value)
    if isinstance(value, dict):
        return FrozenMap(tuple((str(key), freeze(item)) for key, item in value.items()))
    raise TypeError(f"cannot freeze value of type {type(value).__name__}")


def to_jsonable(value: Observed) -> Any:
    """JSON-friendly form; unknown values stay distinguishable from null/empty."""
    if isinstance(value, Unknown):
        if value.raw is None:
            return {"unknown": value.reason.value}
        return {"unknown": value.reason.value, "raw": to_jsonable(value.raw)}
    if isinstance(value, EntityRef):
        rendered = {"ref": str(value.entity_id), "state_type": value.state_type, "confidence": value.confidence.value}
        return rendered if value.name is None else {**rendered, "name": value.name}
    if isinstance(value, FrozenMap):
        return {key: to_jsonable(item) for key, item in value.items}
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    return value
