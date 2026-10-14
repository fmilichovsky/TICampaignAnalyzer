"""Componentized game dates: ``{year, month, day, hour, minute, second[, millisecond]}`` objects."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..model.values import Observed, Unknown, UnknownReason, freeze

if TYPE_CHECKING:
    from .unknowns import UnknownCollector

_DATE_COMPONENTS = ("year", "month", "day", "hour", "minute", "second")

COMPONENTIZED_DATE = "componentized_date"
"""``field_shape`` detail for a date field whose value is not a complete componentized date."""


def game_datetime(components: Any) -> datetime | None:
    """Build a naive game-calendar datetime from a componentized date object; ``None`` when it is not one."""
    if not isinstance(components, dict):
        return None
    try:
        parts: list[Any] = [components[name] for name in _DATE_COMPONENTS]
        millisecond: Any = components.get("millisecond", 0)
        if any(isinstance(part, bool) or not isinstance(part, int) for part in [*parts, millisecond]):
            return None
        year, month, day, hour, minute, second = (int(part) for part in parts)
        return datetime(year, month, day, hour, minute, second, int(millisecond) * 1000)
    except (KeyError, TypeError, ValueError):
        return None


def iso_date(components: Any, state_type: str, field: str, collector: UnknownCollector) -> Observed:
    """``null`` stays ``None``; a componentized date becomes its ISO-8601 text; anything else is unparseable.

    The unparseable value is kept raw on the ``Unknown`` and reported as an unexpected field shape.
    """
    if components is None:
        return None
    timestamp = game_datetime(components)
    if timestamp is None:
        collector.field_shape(state_type, field, COMPONENTIZED_DATE, components)
        return Unknown(UnknownReason.UNPARSEABLE, freeze(components))
    return timestamp.isoformat()
