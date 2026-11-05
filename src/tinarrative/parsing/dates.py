"""Componentized game dates: ``{year, month, day, hour, minute, second[, millisecond]}`` objects."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from ..model.values import Observed, Unknown, UnknownReason, freeze

if TYPE_CHECKING:
    from .unknowns import UnknownCollector


COMPONENTIZED_DATE = "componentized_date"
"""``field_shape`` detail for a date field whose value is not a complete componentized date."""


def game_datetime(components: Any) -> datetime | None:
    """Build a naive game-calendar datetime from a componentized date object; ``None`` when it is not one."""
    if not isinstance(components, dict):
        return None
    try:
        key = (
            components["year"],
            components["month"],
            components["day"],
            components["hour"],
            components["minute"],
            components["second"],
            components.get("millisecond", 0),
        )
    except KeyError:
        return None
    # The same dates recur across entries and saves. Only exact ints are cached: ``True == 1`` as a cache key.
    if set(map(type, key)) == {int}:
        return _cached_datetime(*key)
    if any(isinstance(part, bool) or not isinstance(part, int) for part in key):
        return None
    return _cached_datetime.__wrapped__(*(int(part) for part in key))


@lru_cache(maxsize=8192)
def _cached_datetime(
    year: int, month: int, day: int, hour: int, minute: int, second: int, millisecond: int
) -> datetime | None:
    try:
        return datetime(year, month, day, hour, minute, second, millisecond * 1000)
    except ValueError:
        return None


def iso_date(components: Any, state_type: str, field: str, collector: UnknownCollector) -> Observed:
    """``null`` stays ``None`` and a componentized date becomes ISO-8601 text.

    Anything else is kept raw on an ``UNPARSEABLE`` ``Unknown`` and reported as an unexpected field shape.
    """
    if components is None:
        return None
    timestamp = game_datetime(components)
    if timestamp is None:
        collector.field_shape(state_type, field, COMPONENTIZED_DATE, components)
        return Unknown(UnknownReason.UNPARSEABLE, freeze(components))
    return timestamp.isoformat()
