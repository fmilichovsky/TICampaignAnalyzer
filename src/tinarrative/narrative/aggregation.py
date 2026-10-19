"""Narrative aggregation: named rules that join the qualified event stream of a sequence into developments.

A narrative event is an ``Event`` with its narrative fields set (architecture 11.2). Rules see the whole qualified
stream and one situation report per save (11.1), never a snapshot, and declare their window in game days. A rule
emits only from its anchor evidence; it decides which further events join the anchor, and ``NarrativeBuilder``
applies the shared policy to what it joins:

- span: ``start`` is the earliest constituent start (its ``not_before``, or its record date when it is record-dated,
  which narrows the span), ``end`` the latest constituent date, each with the basis it came from;
- ``open`` when the rule's anchor entity is still present in the last save;
- confidence: the minimum over the constituents, lowered one level for a heuristic join;
- significance: the rule's level, never below the most significant constituent;
- status: objective only when every constituent is objective and the join is by entity ID.

Nesting is one rule order at a time: a rule sees the atomic stream and the narrative events of lower orders only, so
it can never build on a rule of its own order and there are no cycles.
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
from .chronology import chronological, interval_of, interval_sort_key, qualified_id
from .situation import SituationReport

logger = get_logger(__name__)

_CONFIDENCE_ORDER = (Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH)


class Join(StrEnum):
    """How a rule joined its constituents to the anchor."""

    ENTITY = "entity"
    """By a stable entity ID: a war, a federation, a nation across its own events."""
    HEURISTIC = "heuristic"
    """By a shared entity within a time window."""


class NarrativeRule(Protocol):
    """A named rule building one kind of narrative event.

    ``order`` places it among the rules: it sees the narrative events of lower orders. ``window_days`` is the span of
    game days it joins evidence over, ``None`` for the whole sequence.
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
    """Game days from ``earlier`` to ``later`` (ISO dates); ``None`` when either is unknown or unparseable."""
    if not isinstance(earlier, str) or not isinstance(later, str):
        return None
    try:
        return (datetime.fromisoformat(later) - datetime.fromisoformat(earlier)).total_seconds() / 86400
    except ValueError:
        return None


def present_in(report: SituationReport, ref: EntityRef) -> bool:
    """Whether the report lists the entity as a nation, federation, war or faction."""
    listed = (
        *(nation.nation for nation in report.nations),
        *(federation.federation for federation in report.federations),
        *(war.war for war in report.wars),
        *(faction.faction for faction in report.factions),
    )
    return any(item.entity_id == ref.entity_id for item in listed)


class NarrativeBuilder:
    """Builds narrative events under the shared policy of the module docstring, against one sequence's reports."""

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
    ) -> Event:
        """A narrative event over ``constituents``; the ID is qualified by its first interval.

        ``confidence`` overrides the minimum-over-constituents policy; a rule that passes it documents why.
        """
        if not constituents:
            raise ValueError(f"narrative event {event_type} has no constituents")
        intervals = tuple(sorted({key for event in constituents for key in _intervals(event)}, key=interval_sort_key))
        starts = [dated for dated in map(_start, constituents) if dated is not None]
        ends = [dated for dated in map(_end, constituents) if dated is not None]
        start = min(starts, key=lambda dated: dated.key) if starts else None
        end = max(ends, key=lambda dated: (dated.date, -dated.key[1])) if ends else None
        bounds = [event.not_before for event in constituents if isinstance(event.not_before, str)]
        role_list = tuple(roles)
        return Event(
            id=qualified_id(event_id(event_type, *id_parts), intervals[0]),
            event_type=event_type,
            status=self._status(constituents, join),
            confidence=confidence or self._confidence(constituents, join),
            date=end.date if end else Unknown(),
            date_basis=end.basis if end else DateBasis.INTERVAL,
            not_before=min(bounds) if bounds else Unknown(),
            sources=tuple(cite(constituents, Support())),
            entities=tuple(ref for _, ref in sorted(role_list, key=lambda item: item[0].rank)),
            attributes=tuple(attributes),
            significance=self._significance(constituents, significance),
            constituents=tuple(event.id for event in constituents),
            start=start.date if start else Unknown(),
            start_basis=start.basis if start else None,
            end=end.date if end else Unknown(),
            end_basis=end.basis if end else None,
            open=anchor is not None and self._last is not None and present_in(self._last, anchor),
            intervals=intervals,
            roles=role_list,
        )

    @staticmethod
    def _status(constituents: Sequence[Event], join: Join) -> EventStatus:
        objective = join is Join.ENTITY and all(event.status is EventStatus.OBJECTIVE for event in constituents)
        return EventStatus.OBJECTIVE if objective else EventStatus.INFERRED

    @staticmethod
    def _confidence(constituents: Sequence[Event], join: Join) -> Confidence:
        least = min((event.confidence for event in constituents), key=_CONFIDENCE_ORDER.index)
        return lower(least) if join is Join.HEURISTIC else least

    @staticmethod
    def _significance(constituents: Sequence[Event], ruled: Significance | None) -> Significance:
        levels = [event.significance for event in constituents]
        if ruled is not None:
            levels.append(ruled)
        return max(levels, key=lambda level: level.rank)


NARRATIVE_RULES: tuple[NarrativeRule, ...] = ()
"""The rules ``aggregate`` runs by default; the geopolitical and space catalogue (architecture 11.3) adds them."""


def aggregate(
    stream: Sequence[Event],
    situations: Sequence[SituationReport],
    rules: Sequence[NarrativeRule] = NARRATIVE_RULES,
) -> list[Event]:
    """The narrative events the rules build over a qualified chronological stream, sorted.

    Rules run by order, then name; each sees ``stream`` and the narrative events of lower orders. A rule name used
    twice, a narrative event that cites a narrative event of its own or a higher order or an ID it cannot see, an
    event that is not narrative, and a duplicate ID are programming errors (``ValueError``).
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
