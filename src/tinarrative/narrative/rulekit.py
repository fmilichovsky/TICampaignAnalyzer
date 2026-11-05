"""Helpers shared by the narrative rule modules: dates and windows, entity and attribute access, grouping.

Windows are in game days.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta

from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import DateBasis, Event
from ..model.values import Observed
from .aggregation import days_between
from .chronology import interval_of, interval_sort_key
from .situation import SituationReport
from .stream import EventStream

# --- Dates and windows -------------------------------------------------------------------------------------------


def earliest(event: Event) -> str | None:
    """Its start, record date or ``not_before``."""
    if event.is_narrative:
        value: Observed = event.start
    elif event.date_basis is DateBasis.RECORD:
        value = event.date
    else:
        value = event.not_before
    return value if isinstance(value, str) else None


def latest(event: Event) -> str | None:
    value = event.date
    return value if isinstance(value, str) else None


def within(earlier: str | None, later: str | None, days: int) -> bool:
    gap = days_between(earlier, later)
    return gap is not None and gap <= days


def overlaps(event: Event, low: str | None, high: str | None) -> bool:
    """Inclusive; an unknown bound never matches."""
    after_low, before_high = days_between(low, latest(event)), days_between(earliest(event), high)
    return after_low is not None and before_high is not None and after_low >= 0 and before_high >= 0


class DatedEvents:
    """Events queried repeatedly by ``overlaps``: a point-dated event is found by bisection, any other one is checked
    with ``overlaps``. Results keep the input order."""

    def __init__(self, events: Iterable[Event]) -> None:
        points: list[tuple[datetime, int, Event]] = []
        self._others: list[tuple[int, Event]] = []
        for position, event in enumerate(events):
            moment = _moment(latest(event)) if earliest(event) == latest(event) else None
            if moment is None:
                self._others.append((position, event))
            else:
                points.append((moment, position, event))
        points.sort(key=lambda point: (point[0], point[1]))
        self._moments = [moment for moment, _, _ in points]
        self._points = [(position, event) for _, position, event in points]

    def overlapping(self, low: str | None, high: str | None) -> list[Event]:
        """Equals ``[event for event in events if overlaps(event, low, high)]``."""
        first, last = _moment(low), _moment(high)
        if first is None or last is None:
            return []
        found = self._points[bisect_left(self._moments, first) : bisect_right(self._moments, last)]
        found += [(position, event) for position, event in self._others if overlaps(event, low, high)]
        return [event for _, event in sorted(found, key=lambda item: item[0])]


def _moment(date: str | None) -> datetime | None:
    """Parsed as ``days_between`` parses."""
    try:
        return datetime.fromisoformat(date) if date is not None else None
    except ValueError:
        return None


def shifted(date: str | None, days: int) -> str | None:
    if date is None:
        return None
    try:
        return (datetime.fromisoformat(date) + timedelta(days=days)).isoformat()
    except ValueError:
        return None


def event_order(event: Event) -> tuple[str, tuple[str, int], str]:
    return (earliest(event) or "", interval_sort_key(intervals_of([event])[0]), event.id)


def anchored(events: Iterable[Event], days: int) -> list[list[Event]]:
    """Bounded runs: each member within ``days`` of the run's first date."""
    runs: list[list[Event]] = []
    for event in sorted(events, key=event_order):
        if runs and within(latest(runs[-1][0]), earliest(event), days):
            runs[-1].append(event)
        else:
            runs.append([event])
    return runs


def chained(events: Iterable[Event], days: int) -> list[list[Event]]:
    """Unbounded runs: each member within ``days`` of the run's latest date, so a run can last years."""
    runs: list[list[Event]] = []
    for event in sorted(events, key=event_order):
        if runs and within(max((latest(item) or "" for item in runs[-1]), default=None), earliest(event), days):
            runs[-1].append(event)
        else:
            runs.append([event])
    return runs


def intervals_of(events: Iterable[Event]) -> list[str]:
    keys = {key for event in events for key in (event.intervals if event.is_narrative else (interval_of(event.id),))}
    return sorted(keys, key=interval_sort_key)


def last_date(situations: Sequence[SituationReport]) -> str | None:
    date = situations[-1].date if situations else None
    return date if isinstance(date, str) else None


# --- Entities and attributes -------------------------------------------------------------------------------------


def subject(event: Event) -> EntityRef | None:
    return event.entities[0] if event.entities else None


def subject_id(event: Event) -> EntityId | None:
    ref = subject(event)
    return ref.entity_id if ref is not None else None


def ref_attribute(event: Event, name: str) -> EntityRef | None:
    value = event.attribute(name)
    return value if isinstance(value, EntityRef) else None


def refs_attribute(event: Event, name: str) -> tuple[EntityRef, ...]:
    value = event.attribute(name)
    return tuple(item for item in value if isinstance(item, EntityRef)) if isinstance(value, tuple) else ()


def mentions(event: Event, entity_id: EntityId) -> bool:
    return any(ref.entity_id == entity_id for ref in event.entities)


def entity_of(event: Event, domain: EntityDomain) -> EntityRef | None:
    return next((ref for ref in event.entities[1:] if ref.entity_id.domain is domain), None)


NATION_ARMIES_CHANGED = "nation.armies_changed"


def army_home(event: Event) -> EntityRef | None:
    """The nation an army event belongs to: the subject of a nation's army list change, else the army's home."""
    if event.event_type == NATION_ARMIES_CHANGED:
        return subject(event)
    return ref_attribute(event, "home_nation")


def unique_refs(refs: Iterable[EntityRef]) -> tuple[EntityRef, ...]:
    """The first seen keeps its name."""
    seen: dict[EntityId, EntityRef] = {}
    for ref in refs:
        seen.setdefault(ref.entity_id, ref)
    return tuple(seen[key] for key in sorted(seen, key=lambda entity_id: entity_id.sort_key))


def by_type(stream: Iterable[Event], *types: str) -> list[Event]:
    if isinstance(stream, EventStream):
        return stream.of_type(*types)
    return [event for event in stream if event.event_type in types]


def by_subject(events: Iterable[Event]) -> dict[EntityId, list[Event]]:
    grouped: dict[EntityId, list[Event]] = defaultdict(list)
    for event in events:
        key = subject_id(event)
        if key is not None:
            grouped[key].append(event)
    return grouped


def sorted_keys(grouped: Mapping[EntityId, object]) -> list[EntityId]:
    return sorted(grouped, key=lambda entity_id: entity_id.sort_key)
