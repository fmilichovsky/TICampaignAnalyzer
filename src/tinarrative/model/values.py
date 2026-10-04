"""Explicit known/unknown value representation.

A field that the save does not provide is ``Unknown``; it is never coerced to ``False``, zero, or an
empty collection. ``None`` is a *known* JSON null, and ``()`` is a *known* empty sequence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Union


class UnknownReason(StrEnum):
    MISSING = "missing"
    UNRESOLVED_REFERENCE = "unresolved_reference"
    UNPARSEABLE = "unparseable"


@dataclass(frozen=True)
class Unknown:
    reason: UnknownReason = UnknownReason.MISSING


@dataclass(frozen=True)
class FrozenMap:
    """Immutable, hashable mapping with items sorted by key."""

    items: tuple[tuple[str, FieldValue], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(sorted(self.items, key=lambda item: item[0])))


FieldValue = Union[None, bool, int, float, str, tuple["FieldValue", ...], FrozenMap]  # noqa: UP007  (recursive alias needs a runtime Union)
Observed = Union[FieldValue, Unknown]  # noqa: UP007  (recursive alias needs a runtime Union)


def is_unknown(value: Observed) -> bool:
    return isinstance(value, Unknown)


def freeze(value: Any) -> FieldValue:
    """Convert decoded JSON (lists/dicts) into an immutable, deterministic value."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list | tuple):
        return tuple(freeze(item) for item in value)
    if isinstance(value, dict):
        return FrozenMap(tuple((str(key), freeze(item)) for key, item in value.items()))
    raise TypeError(f"cannot freeze value of type {type(value).__name__}")


def to_jsonable(value: Observed) -> Any:
    """JSON-friendly form; unknown values stay distinguishable from null/empty."""
    if isinstance(value, Unknown):
        return {"unknown": value.reason.value}
    if isinstance(value, FrozenMap):
        return {key: to_jsonable(item) for key, item in value.items}
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    return value
