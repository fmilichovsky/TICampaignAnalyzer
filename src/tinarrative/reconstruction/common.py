"""Building blocks every reconstruction rule shares: evidence bundles, citation and the inferred event itself.

An inferred event cites every source of its constituents, so it never loses the evidence beneath it (architecture
sections 6 and 10). A fact read from a snapshot alone only qualifies evidence, it is never the evidence.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from ..analyzers.common import EventBuilder, Lookup, Side
from ..model.changes import StateChange
from ..model.entities import EntityId, EntityRef
from ..model.events import Confidence, Event, EventSource, EventStatus, SourceRole
from ..model.evidence import SourceLocation
from ..model.snapshot import EntityState
from ..model.values import FieldValue, Observed

EXECUTIVE_POSITION = 0
"""The ``positionInNation`` of the fallback executive seat: every nation with control points has exactly one point
there, typed after its regime (``TheParty``, ``Aristocracy``, ...) or ``Executive`` (notes, nation control)."""
EXECUTIVE_TYPE = "Executive"
"""The ``controlPointType`` of the point whose controller the nation's ``lastExecutiveChange`` record follows."""

_LOWER = {Confidence.HIGH: Confidence.MEDIUM, Confidence.MEDIUM: Confidence.LOW, Confidence.LOW: Confidence.LOW}


def lower(confidence: Confidence) -> Confidence:
    """One confidence level lower; low stays low."""
    return _LOWER[confidence]


def control_points(lookup: Lookup, nation: EntityId, side: Side) -> tuple[EntityRef, ...] | None:
    """The references in ``nation``'s ``controlPoints`` list on one side; ``None`` when the list is not known."""
    state = lookup.state(nation, side)
    points = state.get("controlPoints") if state is not None else None
    if not isinstance(points, tuple):
        return None
    return tuple(point for point in points if isinstance(point, EntityRef))


class SeatBasis(StrEnum):
    """Why a control point is the executive seat."""

    EXECUTIVE_POINT = "executive_point"
    """The nation's point typed ``Executive``, wherever it sits; ``lastExecutiveChange`` follows its controller."""
    POSITION_ZERO = "position_0"
    """The nation has no ``Executive`` point; the point at position 0 stands in. ``lastExecutiveChange`` is no
    cross-check there: it is a record that nothing keeps current."""


@dataclass(frozen=True)
class ExecutiveSeat:
    """A nation's executive seat: the control point's state and the basis it was chosen on."""

    state: EntityState
    basis: SeatBasis


def executive_seat(lookup: Lookup, nation: EntityId, side: Side) -> ExecutiveSeat | None:
    """``nation``'s executive seat on one side, if it is found: its ``Executive``-typed point, else the point at the
    fallback position."""
    fallback: EntityState | None = None
    for point in control_points(lookup, nation, side) or ():
        point_state = lookup.state(point.entity_id, side)
        if point_state is None:
            continue
        if point_state.get("controlPointType") == EXECUTIVE_TYPE:
            return ExecutiveSeat(point_state, SeatBasis.EXECUTIVE_POINT)
        position = point_state.get("positionInNation")
        if fallback is None and position == EXECUTIVE_POSITION and not isinstance(position, bool):
            fallback = point_state
    return ExecutiveSeat(fallback, SeatBasis.POSITION_ZERO) if fallback is not None else None


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
