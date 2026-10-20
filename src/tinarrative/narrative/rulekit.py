"""Helpers shared by the narrative rule modules: dates and windows, entity and attribute access, grouping.

A window is in game days. *Anchored* runs bound their span from the first member; *chained* runs let a sequence
continue as long as each member follows the previous one closely enough.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta

from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import DateBasis, Event
from ..model.values import Observed
from .aggregation import days_between
from .chronology import interval_of, interval_sort_key
from .situation import SituationReport

# --- Dates and windows -------------------------------------------------------------------------------------------


def earliest(event: Event) -> str | None:
    """The earliest date the event can have happened on: its start, record date or ``not_before``."""
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
    """Whether the event can have happened between ``low`` and ``high`` (inclusive; unknown bounds never match)."""
    after_low, before_high = days_between(low, latest(event)), days_between(earliest(event), high)
    return after_low is not None and before_high is not None and after_low >= 0 and before_high >= 0


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
    """Events split into runs whose members can each have happened within ``days`` of the run's first date."""
    runs: list[list[Event]] = []
    for event in sorted(events, key=event_order):
        if runs and within(latest(runs[-1][0]), earliest(event), days):
            runs[-1].append(event)
        else:
            runs.append([event])
    return runs


def chained(events: Iterable[Event], days: int) -> list[list[Event]]:
    """Events split into runs whose members can each have happened within ``days`` of the run's latest date."""
    runs: list[list[Event]] = []
    for event in sorted(events, key=event_order):
        if runs and within(max((latest(item) or "" for item in runs[-1]), default=None), earliest(event), days):
            runs[-1].append(event)
        else:
            runs.append([event])
    return runs


def intervals_of(events: Iterable[Event]) -> list[str]:
    """The interval keys the events span, in sequence order."""
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


def unique_refs(refs: Iterable[EntityRef]) -> tuple[EntityRef, ...]:
    """References in natural ID order, one per entity (the first seen keeps its name)."""
    seen: dict[EntityId, EntityRef] = {}
    for ref in refs:
        seen.setdefault(ref.entity_id, ref)
    return tuple(seen[key] for key in sorted(seen, key=lambda entity_id: entity_id.sort_key))


def by_type(stream: Iterable[Event], *types: str) -> list[Event]:
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
