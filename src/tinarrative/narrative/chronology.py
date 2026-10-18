"""Chronological ordering of events across the intervals of a save sequence.

An event ID names a type and a subject (``region.nation_changed/region:12``), so it is unique within one interval
but not across a sequence: the same region can change hands twice, and a notification ID carries a queue index
that means a different entry in each save. ``qualify`` makes an ID unique by appending the interval key
(``@2045-11-01T00:00:00``), and rewrites every reference to an ID of the same interval with it (the
``constituents`` of an inferred event and its ID-valued attributes). Consecutive intervals report disjoint
changes, so no event is merged with another: the stream is the qualified events of every interval, sorted.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import replace

from ..model.events import Event
from ..reconstruction import ID_ATTRIBUTES

INTERVAL_SEPARATOR = "@"


def qualified_id(event_id: str, key: str) -> str:
    """The ID of an event of the interval ``key`` within a sequence."""
    return f"{event_id}{INTERVAL_SEPARATOR}{key}"


def qualify(event: Event, key: str) -> Event:
    """The event with its ID, its constituents and its ID-valued attributes qualified by the interval ``key``."""
    attributes = tuple(
        (name, tuple(qualified_id(str(item), key) for item in value))
        if name in ID_ATTRIBUTES and isinstance(value, tuple)
        else (name, value)
        for name, value in event.attributes
    )
    return replace(
        event,
        id=qualified_id(event.id, key),
        constituents=tuple(qualified_id(constituent, key) for constituent in event.constituents),
        attributes=attributes,
    )


def chronological(events: Iterable[Event]) -> list[Event]:
    """Events in date order (undated first), then by type and ID; a duplicate ID is a programming error."""
    ordered = sorted(events, key=lambda event: event.sort_key)
    ids = Counter(event.id for event in ordered)
    duplicates = sorted(event_id for event_id, count in ids.items() if count > 1)
    if duplicates:
        raise ValueError(f"event stream has duplicate event IDs: {duplicates[:3]}")
    return ordered
