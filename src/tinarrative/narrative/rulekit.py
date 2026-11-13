"""Helpers shared by the narrative rule modules: dates and windows, entity and attribute access, grouping, metric
shifts.

Windows are in game days.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from datetime import datetime, timedelta

from ..analyzers.politics.bands import BANDS, band
from ..kinds import nations as nation_kinds
from ..kinds.military import NATION_ARMIES_CHANGED as NATION_ARMIES_CHANGED_KIND
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import DateBasis, Event, Role
from ..model.values import FieldValue, FrozenMap, Observed, Unknown, number
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


NATION_ARMIES_CHANGED = NATION_ARMIES_CHANGED_KIND.event_type


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


# --- Metric shifts -----------------------------------------------------------------------------------------------

STATISTIC_SHIFTED = nation_kinds.STATISTIC_SHIFTED.event_type
LEADING_STATISTICS = frozenset({"numNuclearWeapons"})
"""Rank ahead of any relative change when shifts are bounded: a shift from zero has no relative change but is the
story."""


def literal(value: Observed) -> FieldValue:
    """A known value as it is; ``None`` for an unknown one."""
    return None if isinstance(value, Unknown) else value


def metric_shifts(
    stream: Iterable[Event],
    nations: Iterable[EntityId],
    intervals: Iterable[str],
    windows: Mapping[EntityId, Collection[str]] | None = None,
) -> tuple[FrozenMap, ...]:
    """One net entry per nation, statistic and key over the ``nation.statistic_shifted`` events in ``intervals``.

    The net covers the reported shifts only: an interval whose change stayed below the analyzer's threshold is missing
    from it. ``relative_change`` is unsigned. ``windows`` limits a nation to its own intervals; a nation without a
    window keeps all of ``intervals``. Shifts are context, never constituents.
    """
    wanted, keys = set(nations), set(intervals)
    groups: dict[tuple[EntityId, str, str], list[Event]] = defaultdict(list)
    for event in EventStream.of(stream).of_subject(wanted, STATISTIC_SHIFTED):
        nation = subject_id(event)
        if nation is None or interval_of(event.id) not in keys:
            continue
        if windows is not None and nation in windows and interval_of(event.id) not in windows[nation]:
            continue
        key = event.attribute("key")
        groups[(nation, str(event.attribute("statistic")), key if isinstance(key, str) else "")].append(event)
    entries = []
    for (_, statistic, key), shifts in sorted(groups.items(), key=lambda item: (item[0][0].sort_key, item[0][1:])):
        shifts.sort(key=lambda event: interval_sort_key(interval_of(event.id)))
        before, after = literal(shifts[0].attribute("before")), literal(shifts[-1].attribute("after"))
        low, high = number(before), number(after)
        relative = abs(high - low) / abs(low) if low is not None and high is not None and low != 0 else None
        items: list[tuple[str, FieldValue]] = [
            ("nation", shifts[0].entities[0]),
            ("statistic", statistic),
            ("before", before),
            ("after", after),
            ("relative_change", relative),
            ("not_before", literal(shifts[0].not_before)),
            ("date", literal(shifts[-1].date)),
            ("date_basis", shifts[-1].date_basis.value),
            ("events", tuple(event.id for event in shifts)),
        ]
        if key:
            items.append(("key", key))
        if statistic in BANDS and low is not None and high is not None:
            items.extend((("from_band", band(statistic, low)), ("to_band", band(statistic, high))))
        causes = _summed_causes(shifts)
        if causes is not None:
            items.append(("causes", causes))
        entries.append(FrozenMap(tuple(items)))
    return tuple(entries)


def _summed_causes(shifts: Sequence[Event]) -> FrozenMap | None:
    maps = [value for value in (event.attribute("causes") for event in shifts) if isinstance(value, FrozenMap)]
    if not maps:
        return None
    totals: dict[str, float] = defaultdict(float)
    for causes in maps:
        for reason, delta in causes.items:
            amount = number(delta)
            if amount is not None:
                totals[reason] += amount
    return FrozenMap(tuple((reason, total) for reason, total in totals.items() if total != 0))


def bounded_shifts(
    entries: Sequence[FrozenMap], roles: Iterable[tuple[Role, EntityRef]], limit: int
) -> tuple[tuple[str, FieldValue], ...]:
    """At most ``limit`` entries, with ``metric_shifts_omitted`` counting the cut.

    Selection prefers role nations, then ``LEADING_STATISTICS``, then the largest ``relative_change``; the kept entries
    keep their original order.
    """
    first = {ref.entity_id for _, ref in roles if ref.entity_id.domain is EntityDomain.NATION}

    def rank(position: int) -> tuple[bool, bool, bool, float, int]:
        entry = dict(entries[position].items)
        relative = number(entry.get("relative_change"))
        nation = entry.get("nation")
        return (
            not (isinstance(nation, EntityRef) and nation.entity_id in first),
            entry.get("statistic") not in LEADING_STATISTICS,
            relative is None,
            -(relative or 0.0),
            position,
        )

    kept = sorted(sorted(range(len(entries)), key=rank)[:limit])
    attributes: tuple[tuple[str, FieldValue], ...] = (("metric_shifts", tuple(entries[index] for index in kept)),)
    if len(kept) < len(entries):
        attributes += (("metric_shifts_omitted", len(entries) - len(kept)),)
    return attributes
