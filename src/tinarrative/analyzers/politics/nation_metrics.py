"""Nation statistic shifts above a threshold, with the per-cause deltas the game itself tracked.

Most statistic change is routine drift, so only a change past its threshold is reported
(``docs/game-data-notes/higher-level-event-sources.md``, "Metric shift magnitudes"). Thresholds scale with the
interval as ``max(floor, rate × months)``; the floor alone applies without a known interval. ``causes`` (per-reason
delta of the ``tracker_<Statistic>ChangeReason_AllTime`` map) is arithmetic over evidence; reading it as an annexation
or unification is reconstruction work. Placeholder nations are skipped.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ...model.changes import ChangeIndex, ChangeKind, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId
from ...model.events import Event, EventSource, SourceRole
from ...model.snapshot import SaveSnapshot
from ...model.values import FrozenMap, Observed, Unknown
from ..common import EventBuilder, Lookup, Side, primary

STATISTIC_SHIFTED = "nation.statistic_shifted"
PUBLIC_OPINION = "publicOpinion"
DAYS_PER_MONTH = 365.25 / 12


class Measure(StrEnum):
    ABSOLUTE = "absolute"
    """``|after - before|``."""
    RELATIVE = "relative"
    """``|after - before| / |before|``; infinite when ``before`` is zero."""


@dataclass(frozen=True)
class StatisticThreshold:
    """A shift counts when its measure reaches ``max(floor, rate_per_month × months)``."""

    measure: Measure
    floor: float
    rate_per_month: float | None = None
    """``None`` for a discrete statistic: the floor applies whatever the interval."""

    def limit(self, days: float | None) -> float:
        if self.rate_per_month is None or days is None:
            return self.floor
        return max(self.floor, self.rate_per_month * days / DAYS_PER_MONTH)


GDP = StatisticThreshold(Measure.RELATIVE, 0.05, 0.04)
"""Relative: routine GDP drift is a few percent a month; territory changes move it by orders of magnitude."""

SOCIAL_SCORE = StatisticThreshold(Measure.ABSOLUTE, 0.5, 0.2)
"""Inequality, education and democracy (0-10 scales) drift by about 0.2 a month at most."""

COHESION = StatisticThreshold(Measure.ABSOLUTE, 2.0, 0.75)
"""Cohesion moves in steps under ``CohesionReason_Effect``, so the floor sits above a single step."""

UNREST = StatisticThreshold(Measure.ABSOLUTE, 1.0, 0.5)
"""Unrest moves in 0.25 steps (mostly ``UnrestReason_MovementToRestValue``)."""

SUSTAINABILITY = StatisticThreshold(Measure.ABSOLUTE, 0.5, 0.15)
"""Sustainability drifts slowly (under 0.1 a month)."""

MILITARY_TECH = StatisticThreshold(Measure.ABSOLUTE, 0.25, 0.1)
"""Military tech level moves in small steps."""

SPACE_FUNDING = StatisticThreshold(Measure.RELATIVE, 0.5, 0.25)
"""Relative: large budgets drift by a few percent, small ones jump; a budget from zero always counts."""

DISCRETE = StatisticThreshold(Measure.ABSOLUTE, 1)
"""``numNuclearWeapons`` is a count that rarely changes, so any change counts, whatever the interval."""

STATISTIC_THRESHOLDS: Mapping[str, StatisticThreshold] = {
    "GDP": GDP,
    "inequality": SOCIAL_SCORE,
    "education": SOCIAL_SCORE,
    "democracy": SOCIAL_SCORE,
    "cohesion": COHESION,
    "unrest": UNREST,
    "sustainability": SUSTAINABILITY,
    "militaryTechLevel": MILITARY_TECH,
    "spaceFunding_year": SPACE_FUNDING,
    "numNuclearWeapons": DISCRETE,
}
"""The scalar statistics and their thresholds, in the order they are analyzed."""

PUBLIC_OPINION_THRESHOLD = StatisticThreshold(Measure.ABSOLUTE, 0.15, 0.05)
"""Applied to each key (faction ideologies and ``Undecided``) of the ``publicOpinion`` share map on its own."""

TRACKERS: Mapping[str, str] = {
    "GDP": "tracker_GDPChangeReason_AllTime",
    "inequality": "tracker_InequalityChangeReason_AllTime",
    "education": "tracker_EducationChangeReason_AllTime",
    "democracy": "tracker_DemocracyChangeReason_AllTime",
    "cohesion": "tracker_CohesionChangeReason_AllTime",
    "unrest": "tracker_UnrestChangeReason_AllTime",
}
"""The cumulative cause map of each statistic that has one (reason identifier -> cumulative number)."""


def interval_days(before: SaveSnapshot, after: SaveSnapshot) -> float | None:
    """Game days between the two saves; ``None`` when a date is unknown or the interval is not positive."""
    start, end = _moment(before), _moment(after)
    if start is None or end is None:
        return None
    days = (end - start).total_seconds() / 86400
    return days if days > 0 else None


def _moment(snapshot: SaveSnapshot) -> datetime | None:
    if snapshot.timestamp is not None:
        return snapshot.timestamp
    if isinstance(snapshot.date, str):
        try:
            return datetime.fromisoformat(snapshot.date)
        except ValueError:
            return None
    return None


def number(value: Observed) -> float | None:
    """The value when it is a number (never a flag), else ``None``."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value


def relative_change(before: float, after: float) -> float:
    """``|after - before| / |before|``; infinite for a change from zero."""
    if before == 0:
        return 0.0 if after == 0 else math.inf
    return abs(after - before) / abs(before)


def is_shift(before: float, after: float, threshold: StatisticThreshold, days: float | None) -> bool:
    """Whether the change reaches the threshold scaled to an interval of ``days`` (``None``: the floor alone)."""
    if threshold.measure is Measure.RELATIVE:
        measured = relative_change(before, after)
    else:
        measured = abs(after - before)
    return measured >= threshold.limit(days)


class NationMetricAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        build = EventBuilder(before, after, lookup)
        days = interval_days(before, after)
        events: list[Event] = []
        for statistic, threshold in STATISTIC_THRESHOLDS.items():
            for change in index.fields(EntityDomain.NATION, statistic):
                event = _statistic_shift(change, threshold, days, index, lookup, build)
                if event is not None:
                    events.append(event)
        for change in index.fields(EntityDomain.NATION, PUBLIC_OPINION):
            events.extend(_opinion_shifts(change, days, lookup, build))
        return events


def placeholder(nation: EntityId, lookup: Lookup) -> bool:
    """A nation without regions on both sides (its statistics are frozen); unknown sides are not placeholders."""
    for side in (Side.BEFORE, Side.AFTER):
        state = lookup.state(nation, side)
        if state is None or state.get("regions") != ():
            return False
    return True


def _statistic_shift(
    change: StateChange,
    threshold: StatisticThreshold,
    days: float | None,
    index: ChangeIndex,
    lookup: Lookup,
    build: EventBuilder,
) -> Event | None:
    nation = change.entity_id
    if change.kind is not ChangeKind.VALUE or nation is None or change.field is None:
        return None
    before, after = number(change.before), number(change.after)
    if before is None or after is None:
        return None
    if placeholder(nation, lookup) or not is_shift(before, after, threshold, days):
        return None
    sources = [primary(change)]
    attributes: list[tuple[str, Observed]] = [
        ("statistic", change.field),
        ("before", before),
        ("after", after),
        ("relative_change", _relative_attribute(before, after)),
        ("interval_days", days),
    ]
    tracker = TRACKERS.get(change.field)
    if tracker is not None:
        tracker_change = index.field(nation, tracker)
        if tracker_change is None:
            attributes.append(("causes", FrozenMap()))
        else:
            sources.append(EventSource(tracker_change, SourceRole.CORROBORATING))
            attributes.append(("causes", cause_deltas(tracker_change.before, tracker_change.after)))
    return build.event(
        STATISTIC_SHIFTED,
        id_parts=(nation, change.field),
        sources=sources,
        entities=(lookup.ref(nation),),
        attributes=attributes,
    )


def cause_deltas(before: Observed, after: Observed) -> FrozenMap | Unknown:
    """Per-reason ``after - before`` of two cumulative cause maps, non-zero deltas only (a missing key is 0).

    ``Unknown`` when either side is not a map of numbers: the tracker changed but its deltas cannot be read.
    """
    if not (isinstance(before, FrozenMap) and isinstance(after, FrozenMap)):
        return Unknown()
    earlier, later = dict(before.items), dict(after.items)
    deltas: list[tuple[str, float]] = []
    for reason in sorted(earlier.keys() | later.keys()):
        old, new = number(earlier.get(reason, 0)), number(later.get(reason, 0))
        if old is None or new is None:
            return Unknown()
        if new != old:
            deltas.append((reason, new - old))
    return FrozenMap(tuple(deltas))


def _opinion_shifts(change: StateChange, days: float | None, lookup: Lookup, build: EventBuilder) -> list[Event]:
    """One event per ``publicOpinion`` key whose share shifted past the threshold (a missing key is 0)."""
    nation = change.entity_id
    if change.kind is not ChangeKind.MAP or nation is None or placeholder(nation, lookup):
        return []
    if not (isinstance(change.before, FrozenMap) and isinstance(change.after, FrozenMap)):
        return []
    earlier, later = dict(change.before.items), dict(change.after.items)
    events: list[Event] = []
    for key in sorted(earlier.keys() | later.keys()):
        before, after = number(earlier.get(key, 0)), number(later.get(key, 0))
        if before is None or after is None:
            continue
        if before == after or not is_shift(before, after, PUBLIC_OPINION_THRESHOLD, days):
            continue
        events.append(
            build.event(
                STATISTIC_SHIFTED,
                id_parts=(nation, PUBLIC_OPINION, key),
                sources=(primary(change, member=key),),
                entities=(lookup.ref(nation),),
                attributes=(
                    ("statistic", PUBLIC_OPINION),
                    ("key", key),
                    ("before", before),
                    ("after", after),
                    ("relative_change", _relative_attribute(before, after)),
                    ("interval_days", days),
                ),
            )
        )
    return events


def _relative_attribute(before: float, after: float) -> float | None:
    """The relative change as an attribute; ``None`` for a change from zero (no finite ratio)."""
    ratio = relative_change(before, after)
    return None if math.isinf(ratio) else ratio
