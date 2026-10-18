"""Building blocks every reconstruction rule shares: evidence bundles, citation and the inferred event itself.

An inferred event names each objective event it rests on in ``constituents`` and cites all of their sources, so
it never loses the evidence beneath it (architecture sections 6 and 10). The events a rule is built on keep their
source roles; every other source is corroborating. A diff change that no analyzer reports is cited directly. A
fact read from a snapshot alone only qualifies evidence, it is never the evidence.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

from ..analyzers.common import EventBuilder
from ..model.changes import StateChange
from ..model.entities import EntityRef
from ..model.events import Confidence, Event, EventSource, EventStatus, SourceRole
from ..model.evidence import SourceLocation
from ..model.values import FieldValue, Observed

_LOWER = {Confidence.HIGH: Confidence.MEDIUM, Confidence.MEDIUM: Confidence.LOW, Confidence.LOW: Confidence.LOW}


def lower(confidence: Confidence) -> Confidence:
    """One confidence level lower; low stays low."""
    return _LOWER[confidence]


@dataclass(frozen=True)
class Support:
    """Evidence behind a rule: constituent events, and diff changes no event reports (cited directly)."""

    events: tuple[Event, ...] = ()
    changes: tuple[StateChange, ...] = ()

    def __add__(self, other: Support) -> Support:
        return Support(self.events + other.events, self.changes + other.changes)

    def __bool__(self) -> bool:
        return bool(self.events or self.changes)


class ObjectiveIndex:
    """The objective events of one interval, by ID and by type; inferred input events are dropped."""

    def __init__(self, events: Iterable[Event]) -> None:
        self.events: list[Event] = []
        self.by_id: dict[str, Event] = {}
        self._by_type: dict[str, list[Event]] = defaultdict(list)
        for event in events:
            if event.status is not EventStatus.OBJECTIVE:
                continue
            self.events.append(event)
            self.by_id[event.id] = event
            self._by_type[event.event_type].append(event)

    def of_type(self, event_type: str) -> tuple[Event, ...]:
        return tuple(self._by_type.get(event_type, ()))


def inferred(
    build: EventBuilder,
    event_type: str,
    *,
    id_parts: Sequence[object],
    primary: Sequence[Event],
    support: Support,
    entities: Iterable[EntityRef | None],
    attributes: Iterable[tuple[str, Observed]],
    confidence: Confidence,
    primary_changes: Sequence[EventSource] = (),
    recorded_on: Observed = None,
) -> Event:
    """An inferred event citing every source of its ``primary`` events (roles kept), the ``primary_changes``
    cited directly, and every source of its support (corroborating)."""
    return build.event(
        event_type,
        id_parts=id_parts,
        sources=cite(primary, support, primary_changes),
        entities=entities,
        attributes=attributes,
        confidence=confidence,
        status=EventStatus.INFERRED,
        constituents=[event.id for event in (*primary, *support.events)],
        recorded_on=recorded_on,
    )


def cite(primary: Sequence[Event], support: Support, primary_changes: Sequence[EventSource] = ()) -> list[EventSource]:
    """The union of the cited sources, each change and member once; a primary citation wins over a corroborating one."""
    cited: dict[tuple[StateChange, FieldValue | None, SourceLocation | None], EventSource] = {}

    def add(source: EventSource) -> None:
        key = (source.change, source.member, source.entry)
        existing = cited.get(key)
        if existing is None or (existing.role is not SourceRole.PRIMARY and source.role is SourceRole.PRIMARY):
            cited[key] = source

    for source in primary_changes:
        add(source)
    for event in primary:
        for source in event.sources:
            add(source)
    for event in support.events:
        for source in event.sources:
            add(replace(source, role=SourceRole.CORROBORATING))
    for change in support.changes:
        add(EventSource(change, SourceRole.CORROBORATING))
    return list(cited.values())
