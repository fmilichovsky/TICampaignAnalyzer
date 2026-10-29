"""Chronological ordering of events across the intervals of a save sequence.

An event ID is unique within one interval but not across a sequence (the same region can change hands twice), so
``qualify`` appends the interval key. Consecutive intervals report disjoint changes, so no event is ever merged.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import replace

from ..model.events import Event
from ..reconstruction import ID_ATTRIBUTES

INTERVAL_SEPARATOR = "@"
TIE_SEPARATOR = "#"
"""Joins a game time and the position of a save among distinct saves with the same time (``...T00:00:00#2``)."""


def qualified_id(event_id: str, key: str) -> str:
    return f"{event_id}{INTERVAL_SEPARATOR}{key}"


def interval_keys(dates: Sequence[str]) -> list[str]:
    """The game time, with ``#n`` for the n-th distinct save of that time."""
    keys: list[str] = []
    for position, date in enumerate(dates):
        tied = sum(1 for earlier in dates[:position] if earlier == date)
        keys.append(date if tied == 0 else f"{date}{TIE_SEPARATOR}{tied + 1}")
    return keys


def interval_of(event_id: str) -> str:
    return event_id.rpartition(INTERVAL_SEPARATOR)[2]


def interval_sort_key(key: str) -> tuple[str, int]:
    """The bare time sorts before its ``#2``."""
    time, _, tie = key.partition(TIE_SEPARATOR)
    return (time, int(tie) if tie.isdigit() else 1)


def qualify(event: Event, key: str) -> Event:
    """Also qualifies constituents and ID-valued attributes; a narrative event is born qualified and is returned
    unchanged."""
    if event.is_narrative:
        return event
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
    """Undated events first; a duplicate ID is a programming error."""
    ordered = sorted(events, key=lambda event: event.sort_key)
    ids = Counter(event.id for event in ordered)
    duplicates = sorted(event_id for event_id, count in ids.items() if count > 1)
    if duplicates:
        raise ValueError(f"event stream has duplicate event IDs: {duplicates[:3]}")
    return ordered
