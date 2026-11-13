"""Narrative aggregation: named rules that join the qualified event stream of a sequence into narrative events.

See ADR-0009. Rules run in layers derived from what they read and from which kinds own their constituents (ADR-0019).
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from graphlib import CycleError, TopologicalSorter
from typing import Protocol

from ..analyzers.common import event_id
from ..config import DEFAULT_SETTINGS, GeopoliticsSettings
from ..kinds import attributes as kind_attributes
from ..kinds import kind_for
from ..log import TIMING_LOGGER, fields, get_logger
from ..model.entities import EntityRef
from ..model.events import (
    Confidence,
    DateBasis,
    Event,
    EventStatus,
    Role,
    Significance,
)
from ..model.kinds import EventKind
from ..model.values import Observed, Unknown
from ..reconstruction.common import Support, cite, lower
from .chronology import chronological, interval_keys, interval_of, interval_sort_key, qualified_id
from .significance import narrative_score
from .situation import SituationReport
from .stream import EventStream, UndeclaredRead

logger = get_logger(__name__)
timing = get_logger(TIMING_LOGGER)

_CONFIDENCE_ORDER = (Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH)


class Join(StrEnum):
    """A heuristic join lowers confidence one level and is never objective."""

    ENTITY = "entity"
    """By a stable entity ID: a war, a federation, a nation across its own events."""
    HEURISTIC = "heuristic"
    """By a shared entity within a time window."""


class NarrativeRule(Protocol):
    """A named rule building narrative events of its ``emitted_types``.

    It sees every atomic event and the narrative events of the types it ``reads`` or that ``explains`` its own away,
    in chronological order: the rules emitting those run in an earlier layer. ``explains`` names the types whose
    events keep one of its own from existing. An event the stream says is not ``citable`` is an exclusive constituent
    of an earlier narrative event of another kind: the rule may read it for context, never cite it. ``window_days`` is
    ``None`` for the whole sequence.
    """

    @property
    def name(self) -> str: ...

    @property
    def emitted_types(self) -> frozenset[str]: ...

    @property
    def reads(self) -> frozenset[str]: ...

    @property
    def explains(self) -> frozenset[str]: ...

    @property
    def window_days(self) -> int | None: ...

    def apply(
        self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder
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
    """Applies the shared policy: confidence is the constituents' minimum, the score is significance's
    (``narrative_score``), and ``open`` while the anchor is in the last report.

    A rule chooses no level: the kind's base level and context rule do, never below the highest-scored cited event.
    """

    def __init__(
        self,
        situations: Sequence[SituationReport],
        geopolitics: GeopoliticsSettings = DEFAULT_SETTINGS.narrative.geopolitics,
    ) -> None:
        self._situations = tuple(situations)
        self._last = self._situations[-1] if self._situations else None
        self._geopolitics = geopolitics

    def scoring_with(self, geopolitics: GeopoliticsSettings) -> NarrativeBuilder:
        """This builder, scoring by the rule's own settings. TODO(#362): goes with ``top_gdp_nations``."""
        return NarrativeBuilder(self._situations, geopolitics)

    def event(
        self,
        kind: EventKind,
        *,
        id_parts: Sequence[object],
        constituents: Sequence[Event],
        roles: Iterable[tuple[Role, EntityRef]],
        join: Join,
        attributes: Iterable[tuple[str, Observed]] = (),
        anchor: EntityRef | None = None,
        confidence: Confidence | None = None,
        open: bool | None = None,
        starts_on: str | None = None,
        corroborating: Sequence[Event] = (),
        id_interval: str | None = None,
    ) -> Event:
        """The ID is qualified by ``id_interval``, else by the first interval.

        A rule passes ``id_interval`` when it may cite events from before its anchor: two events of one rule and one
        ``id_parts`` could otherwise share the earliest cited interval.

        A rule that overrides ``confidence``, ``open`` or ``starts_on`` documents why. ``corroborating`` events date
        only a start: they precede the effect they corroborate. A kind's attributes are checked by its constructor.
        """
        attributes = kind_attributes(kind, attributes)
        event_type = kind.event_type
        if not constituents:
            raise ValueError(f"narrative event {event_type} has no constituents")
        if not kind.narrative:
            raise ValueError(f"event type {event_type} is not a narrative-event kind")
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
        event = Event(
            id=qualified_id(event_id(event_type, *id_parts), id_interval or intervals[0]),
            event_type=event_type,
            status=self._status(cited, join),
            confidence=confidence or self._confidence(cited, join),
            date=end.date if end else Unknown(),
            date_basis=end.basis if end else DateBasis.INTERVAL,
            not_before=min(bounds) if bounds else Unknown(),
            sources=tuple(cite(cited, Support())),
            entities=tuple(ref for _, ref in sorted(role_list, key=lambda item: item[0].rank)),
            attributes=tuple(attributes),
            significance=kind.base,
            score=kind.base.base,
            constituents=tuple(event.id for event in cited),
            start=start.date if start else Unknown(),
            start_basis=start.basis if start else None,
            end=end.date if end else Unknown(),
            end_basis=end.basis if end else None,
            open=self._open(anchor) if open is None else open,
            intervals=intervals,
            roles=role_list,
        )
        score = narrative_score(kind, event, cited, self._geopolitics)
        return replace(event, significance=Significance.of(score), score=score)

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


def aggregate(
    stream: Sequence[Event],
    situations: Sequence[SituationReport],
    rules: Sequence[NarrativeRule],
    *,
    kinds: Callable[[str], EventKind | None] = kind_for,
) -> list[Event]:
    """Rules run in layers derived from what they read and which ``kinds`` have exclusive constituents, each layer by
    rule name. ``kinds`` is the registry; tests pass their own to declare fixture kinds exclusive.

    Narrative events already in ``stream`` are hidden from a rule that does not read their type, like those the rules
    build. These programming errors raise ``ValueError``: a duplicate rule name or event ID, rules reading each other
    in a cycle, a typed lookup of a narrative type the rule does not read, a narrative event of a type its rule does
    not emit, a citation of an event the rule cannot see, and a citation of an exclusive constituent of a narrative
    event of another kind, at any order.
    """
    names = [rule.name for rule in rules]
    duplicated = sorted({name for name in names if names.count(name) > 1})
    if duplicated:
        raise ValueError(f"narrative rules share a name: {duplicated}")
    narrative_types = frozenset(
        {event_type for rule in rules for event_type in rule.emitted_types}
        | {event.event_type for event in stream if event.is_narrative}
    )
    exclusive = frozenset(
        event_type
        for event_type in narrative_types
        if (kind := kinds(event_type)) is not None and kind.exclusive_constituents
    )
    layers = _layers(rules, exclusive)
    started = time.perf_counter()
    build = NarrativeBuilder(situations)
    built: list[Event] = []
    for layer, layer_rules in enumerate(layers):
        visible = EventStream(chronological([*stream, *built]))
        owners = _owners(visible, exclusive)
        produced = []
        for rule in layer_rules:
            withheld = (
                constituent
                for constituent, owned in owners.items()
                if any(owner.event_type not in rule.emitted_types for owner in owned)
            )
            seen = visible.hiding(narrative_types - rule.reads - rule.explains).withholding(withheld)
            produced.append((rule, seen, _timed_apply(rule, seen, situations, build)))
        same_layer = {event.id for _, _, events in produced for event in events}
        for rule, seen, events in produced:
            for event in events:
                _check(rule, event, seen, same_layer)
            logger.debug("narrative rule done %s", fields(rule=rule.name, layer=layer, events=len(events)))
            built.extend(events)
    _check_exclusive(built, _owners(chronological([*stream, *built]), exclusive))
    narrative = chronological(built)
    logger.info("narrative aggregated %s", fields(rules=len(rules), stream=len(stream), events=len(narrative)))
    timing.info("aggregate %s", fields(seconds=round(time.perf_counter() - started, 4)))
    return narrative


def _layers(rules: Sequence[NarrativeRule], exclusive: frozenset[str]) -> list[list[NarrativeRule]]:
    """Each rule one layer after the latest rule emitting a type it reads or that explains its events, and after every
    owner (a rule emitting an ``exclusive`` type) it does not feed. Two owners are ordered only by their reads."""
    emitters: dict[str, set[str]] = defaultdict(set)
    for rule in rules:
        for event_type in rule.emitted_types:
            emitters[event_type].add(rule.name)
    graph = {
        rule.name: {name for event_type in rule.reads | rule.explains for name in emitters.get(event_type, ())}
        for rule in rules
    }
    owners = [rule.name for rule in rules if rule.emitted_types & exclusive]
    feeding = {owner: _ancestors(graph, owner) for owner in owners}
    for rule in rules:
        if rule.name not in feeding:
            graph[rule.name] |= {owner for owner in owners if rule.name not in feeding[owner]}
    sorter = TopologicalSorter(graph)
    try:
        sorter.prepare()
    except CycleError as error:
        raise ValueError(f"narrative rules read each other in a cycle: {error.args[1]}") from error
    by_name = {rule.name: rule for rule in rules}
    layers = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready())
        layers.append([by_name[name] for name in ready])
        sorter.done(*ready)
    return layers


def _ancestors(graph: Mapping[str, set[str]], name: str) -> set[str]:
    found: set[str] = set()
    pending = list(graph.get(name, ()))
    while pending:
        current = pending.pop()
        if current not in found:
            found.add(current)
            pending.extend(graph.get(current, ()))
    return found


def _owners(events: Iterable[Event], exclusive: frozenset[str]) -> dict[str, list[Event]]:
    """Each exclusive constituent with the narrative events of an ``exclusive`` kind that cite it."""
    owners: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        if event.is_narrative and event.event_type in exclusive:
            for constituent in event.constituents:
                owners[constituent].append(event)
    return owners


def _check_exclusive(built: Iterable[Event], owners: Mapping[str, list[Event]]) -> None:
    for event in built:
        for constituent in event.constituents:
            for owner in owners.get(constituent, ()):
                if owner.event_type != event.event_type:
                    raise ValueError(
                        f"narrative event {event.id} cites {constituent}, an exclusive constituent of {owner.id}"
                    )


def _timed_apply(
    rule: NarrativeRule, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder
) -> list[Event]:
    started = time.perf_counter()
    try:
        events = rule.apply(stream, situations, build)
    except UndeclaredRead as error:
        raise ValueError(f"narrative rule {rule.name} {error}") from error
    timing.info("rule %s", fields(name=rule.name, seconds=round(time.perf_counter() - started, 4)))
    return events


def _check(rule: NarrativeRule, event: Event, seen: EventStream, same_layer: set[str]) -> None:
    if not event.is_narrative:
        raise ValueError(f"narrative rule {rule.name} emitted a non-narrative event {event.id}")
    if event.event_type not in rule.emitted_types:
        raise ValueError(f"narrative rule {rule.name} emitted {event.event_type}, which it does not declare")
    for constituent in event.constituents:
        if constituent in same_layer:
            raise ValueError(
                f"narrative rule {rule.name} cites {constituent} of its own layer; a rule builds only on narrative "
                "events of an earlier layer"
            )
        if seen.get(constituent) is None:
            raise ValueError(
                f"narrative rule {rule.name} cites {constituent}, which is neither in the stream nor a narrative "
                "event of a type it reads"
            )
