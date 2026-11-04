"""Narrative aggregation: named rules that join the qualified event stream of a sequence into developments.

See architecture 11.1 and 11.2. A rule sees only lower orders, so rules cannot form cycles.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from ..analyzers.common import event_id
from ..log import fields, get_logger
from ..model.entities import EntityRef
from ..model.events import (
    Confidence,
    DateBasis,
    Event,
    EventStatus,
    Role,
    Significance,
)
from ..model.values import Observed, Unknown
from ..reconstruction.common import Support, cite, lower
from .chronology import chronological, interval_keys, interval_of, interval_sort_key, qualified_id
from .situation import SituationReport

logger = get_logger(__name__)

_CONFIDENCE_ORDER = (Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH)


class Join(StrEnum):
    """A heuristic join lowers confidence one level and is never objective."""

    ENTITY = "entity"
    """By a stable entity ID: a war, a federation, a nation across its own events."""
    HEURISTIC = "heuristic"
    """By a shared entity within a time window."""


class NarrativeRule(Protocol):
    """A named rule building one kind of narrative event.

    It sees the narrative events of lower ``order`` only. ``window_days`` is ``None`` for the whole sequence.
    """

    @property
    def name(self) -> str: ...

    @property
    def order(self) -> int: ...

    @property
    def window_days(self) -> int | None: ...

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]: ...


@dataclass(frozen=True)
class _Dated:
    date: str
    basis: DateBasis

    @property
    def key(self) -> tuple[str, int]:
        return (self.date, 0 if self.basis is DateBasis.RECORD else 1)


def _start(event: Event) -> _Dated | None:
    if event.is_narrative:
        return _dated(event.start, event.start_basis)
    if event.date_basis is DateBasis.RECORD:
        return _dated(event.date, DateBasis.RECORD)
    return _dated(event.not_before, DateBasis.INTERVAL)


def _end(event: Event) -> _Dated | None:
    if event.is_narrative:
        return _dated(event.end, event.end_basis)
    return _dated(event.date, event.date_basis)


def _dated(value: Observed, basis: DateBasis | None) -> _Dated | None:
    if isinstance(value, str) and basis is not None:
        return _Dated(value, basis)
    return None


def _intervals(event: Event) -> tuple[str, ...]:
    return event.intervals if event.is_narrative else (interval_of(event.id),)


def days_between(earlier: Observed, later: Observed) -> float | None:
    """``None`` when either date is unknown or unparseable."""
    if not isinstance(earlier, str) or not isinstance(later, str):
        return None
    try:
        return (datetime.fromisoformat(later) - datetime.fromisoformat(earlier)).total_seconds() / 86400
    except ValueError:
        return None


def interval_reports(situations: Sequence[SituationReport]) -> dict[str, tuple[SituationReport, SituationReport]]:
    """Keyed as ``sequence.plan_sequence`` keys intervals."""
    dates = [str(report.date) for report in situations]
    keys = interval_keys(dates)
    return {keys[index]: (situations[index - 1], situations[index]) for index in range(1, len(situations))}


def present_in(report: SituationReport, ref: EntityRef) -> bool:
    listed = (
        *(nation.nation for nation in report.nations),
        *(federation.federation for federation in report.federations),
        *(war.war for war in report.wars),
        *(faction.faction for faction in report.factions),
    )
    return any(item.entity_id == ref.entity_id for item in listed)


class NarrativeBuilder:
    """Applies the shared policy: confidence is the constituents' minimum, the score never below the highest-scored
    cited event or the base of the rule's level, and ``open`` while the anchor is in the last report."""

    def __init__(self, situations: Sequence[SituationReport]) -> None:
        self._last = situations[-1] if situations else None

    def event(
        self,
        event_type: str,
        *,
        id_parts: Sequence[object],
        constituents: Sequence[Event],
        roles: Iterable[tuple[Role, EntityRef]],
        join: Join,
        attributes: Iterable[tuple[str, Observed]] = (),
        anchor: EntityRef | None = None,
        significance: Significance | None = None,
        confidence: Confidence | None = None,
        open: bool | None = None,
        starts_on: str | None = None,
        corroborating: Sequence[Event] = (),
    ) -> Event:
        """The ID is qualified by the first interval.

        A rule that overrides ``confidence``, ``open`` or ``starts_on`` documents why. ``corroborating`` events date
        only a start: they precede the effect they corroborate.
        """
        if not constituents:
            raise ValueError(f"narrative event {event_type} has no constituents")
        cited = [*constituents, *(event for event in corroborating if event not in constituents)]
        intervals = tuple(sorted({key for event in cited for key in _intervals(event)}, key=interval_sort_key))
        starts = [dated for dated in map(_start, cited) if dated is not None]
        ends = [dated for dated in map(_end, constituents) if dated is not None]
        start = min(starts, key=lambda dated: dated.key) if starts else None
        if starts_on is not None:
            start = _Dated(starts_on, DateBasis.RECORD)
        end = max(ends, key=lambda dated: (dated.date, -dated.key[1])) if ends else None
        bounds = [event.not_before for event in cited if isinstance(event.not_before, str)]
        role_list = tuple(roles)
        score = self._score(cited, significance)
        return Event(
            id=qualified_id(event_id(event_type, *id_parts), intervals[0]),
            event_type=event_type,
            status=self._status(cited, join),
            confidence=confidence or self._confidence(cited, join),
            date=end.date if end else Unknown(),
            date_basis=end.basis if end else DateBasis.INTERVAL,
            not_before=min(bounds) if bounds else Unknown(),
            sources=tuple(cite(cited, Support())),
            entities=tuple(ref for _, ref in sorted(role_list, key=lambda item: item[0].rank)),
            attributes=tuple(attributes),
            significance=Significance.of(score),
            score=score,
            constituents=tuple(event.id for event in cited),
            start=start.date if start else Unknown(),
            start_basis=start.basis if start else None,
            end=end.date if end else Unknown(),
            end_basis=end.basis if end else None,
            open=self._open(anchor) if open is None else open,
            intervals=intervals,
            roles=role_list,
        )

    def _open(self, anchor: EntityRef | None) -> bool:
        return anchor is not None and self._last is not None and present_in(self._last, anchor)

    @staticmethod
    def _status(constituents: Sequence[Event], join: Join) -> EventStatus:
        objective = join is Join.ENTITY and all(event.status is EventStatus.OBJECTIVE for event in constituents)
        return EventStatus.OBJECTIVE if objective else EventStatus.INFERRED

    @staticmethod
    def _confidence(constituents: Sequence[Event], join: Join) -> Confidence:
        least = min((event.confidence for event in constituents), key=_CONFIDENCE_ORDER.index)
        return lower(least) if join is Join.HEURISTIC else least

    @staticmethod
    def _score(cited: Sequence[Event], ruled: Significance | None) -> int:
        """Never a sum: one fact is often recorded several times."""
        scores = [event.score for event in cited]
        if ruled is not None:
            scores.append(ruled.base)
        return max(scores)


def aggregate(
    stream: Sequence[Event],
    situations: Sequence[SituationReport],
    rules: Sequence[NarrativeRule],
) -> list[Event]:
    """Rules run by order, then name.

    A duplicate rule name or ID, a non-narrative event, or a citation of an event of the same or a higher order or
    of an unseen ID raises ``ValueError``: these are programming errors.
    """
    names = [rule.name for rule in rules]
    duplicated = sorted({name for name in names if names.count(name) > 1})
    if duplicated:
        raise ValueError(f"narrative rules share a name: {duplicated}")
    build = NarrativeBuilder(situations)
    built: list[Event] = []
    for order in sorted({rule.order for rule in rules}):
        visible = chronological([*stream, *built])
        visible_ids = {event.id for event in visible}
        produced = [
            (rule, rule.apply(visible, situations, build))
            for rule in sorted((rule for rule in rules if rule.order == order), key=lambda rule: rule.name)
        ]
        same_order = {event.id for _, events in produced for event in events}
        for rule, events in produced:
            for event in events:
                _check(rule, event, visible_ids, same_order)
            logger.debug("narrative rule done %s", fields(rule=rule.name, order=order, events=len(events)))
            built.extend(events)
    chronological([*stream, *built])
    narrative = chronological(built)
    logger.info("narrative aggregated %s", fields(rules=len(rules), stream=len(stream), events=len(narrative)))
    return narrative


def _check(rule: NarrativeRule, event: Event, visible: set[str], same_order: set[str]) -> None:
    if not event.is_narrative:
        raise ValueError(f"narrative rule {rule.name} emitted a non-narrative event {event.id}")
    for constituent in event.constituents:
        if constituent in same_order:
            raise ValueError(
                f"narrative rule {rule.name} (order {rule.order}) cites {constituent} of the same order; a rule "
                "builds only on narrative events of a lower order"
            )
        if constituent not in visible:
            raise ValueError(
                f"narrative rule {rule.name} (order {rule.order}) cites {constituent}, which is neither in the "
                "stream nor a narrative event of a lower order"
            )
