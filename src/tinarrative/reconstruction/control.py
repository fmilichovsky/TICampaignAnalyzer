"""Reconstruction rule ``faction.nation_control_changed``: which faction holds a nation, read from its control points.

The control-point analyzer reports each point's controller only; this rule says a faction's hold changed, per scope
(``executive`` seat, ``plurality``, ``sole``). Evidence: ``docs/game-data-notes/higher-level-event-sources.md``
(nation control). High only when ``lastExecutiveChange`` names the new holder of an ``Executive``-typed seat (a
position-0 stand-in is never cross-checked); low when a point is unresolved. Points that changed nation are
territory, not control: they are left out and lower every confidence. The cause stays an attribute; reading it
(coup, purge) is the narrative layer's work.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from ..analyzers.common import EventBuilder, Lookup, Side
from ..analyzers.politics.control_points import (
    APPEARED,
    CONTROLLER_CHANGED,
    DISAPPEARED,
    LOSS_RECORDED,
    NATION_CHANGED,
)
from ..analyzers.politics.nations import EXECUTIVE_CHANGE_RECORDED
from ..log import fields as log_fields
from ..log import get_logger
from ..model.changes import StateDiff
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import Confidence, Event
from ..model.snapshot import SaveSnapshot
from ..model.values import FrozenMap, Observed, Unknown, UnknownReason
from .common import ObjectiveIndex, SeatBasis, Support, control_points, executive_seat, inferred, lower

NATION_CONTROL_CHANGED = "faction.nation_control_changed"
RULE_TYPES = (NATION_CONTROL_CHANGED,)

EXECUTIVE = "executive"
PLURALITY = "plurality"
SOLE = "sole"
SCOPES = (EXECUTIVE, PLURALITY, SOLE)

logger = get_logger(__name__)

_UNRESOLVED = Unknown(UnknownReason.UNRESOLVED_REFERENCE)

Holder = EntityRef | None | Unknown
"""A scope's holder: a faction, no faction (``null``), or ``Unknown`` when a point it depends on is unresolved."""


@dataclass(frozen=True)
class Holdings:
    """A nation's control points on one side: each point's controller, and the scopes read from them."""

    controllers: tuple[Holder, ...]
    executive: Holder
    seat_basis: SeatBasis | None
    seat_point: EntityId | None

    @property
    def unresolved(self) -> bool:
        return any(isinstance(controller, Unknown) for controller in self.controllers) or isinstance(
            self.executive, Unknown
        )

    def shares(self) -> FrozenMap:
        """Points held per faction, keyed by the faction's ID text."""
        counts = Counter(str(ref.entity_id) for ref in self.controllers if isinstance(ref, EntityRef))
        return FrozenMap(tuple(counts.items()))

    def holder(self, scope: str) -> Holder:
        if scope == EXECUTIVE:
            return self.executive
        if any(isinstance(controller, Unknown) for controller in self.controllers):
            return _UNRESOLVED
        held = [ref for ref in self.controllers if isinstance(ref, EntityRef)]
        counts = Counter(ref.entity_id for ref in held)
        if scope == SOLE:
            return held[0] if len(counts) == 1 and len(held) == len(self.controllers) else None
        ranked = counts.most_common(2)
        if not ranked or (len(ranked) > 1 and ranked[0][1] == ranked[1][1]):
            return None
        return next(ref for ref in held if ref.entity_id == ranked[0][0])


def _same(first: Holder, second: Holder) -> bool:
    if isinstance(first, EntityRef) and isinstance(second, EntityRef):
        return first.entity_id == second.entity_id
    return first is None and second is None


class ControlContext:
    """The interval's objective events indexed for the control rule, with the snapshot lookups."""

    def __init__(self, events: Iterable[Event], before: SaveSnapshot, after: SaveSnapshot) -> None:
        self.objective = ObjectiveIndex(events)
        self.lookup = Lookup(before, after)
        self.build = EventBuilder(before, after, self.lookup)

    def of_type(self, event_type: str) -> tuple[Event, ...]:
        return self.objective.of_type(event_type)

    def nations_of(self, point: EntityId) -> set[EntityId]:
        """The nations the point belongs to on either side."""
        refs = (self.lookup.ref_field(point, "nation", side) for side in (Side.BEFORE, Side.AFTER))
        return {ref.entity_id for ref in refs if ref is not None}

    def holdings(self, nation: EntityId, side: Side, moved: frozenset[EntityId] = frozenset()) -> Holdings | None:
        """The nation's control points on one side, without the ``moved`` ones; ``None`` when the nation or its
        point list is not there. The seat is read from all of the nation's points."""
        points = control_points(self.lookup, nation, side)
        if points is None:
            return None
        controllers = tuple(self._controller(point.entity_id, side) for point in points if point.entity_id not in moved)
        seat = executive_seat(self.lookup, nation, side)
        executive = self._controller(seat.state.ref.entity_id, side) if seat is not None else _UNRESOLVED
        return Holdings(
            controllers,
            executive,
            seat.basis if seat is not None else None,
            seat.state.ref.entity_id if seat is not None else None,
        )

    def _controller(self, point: EntityId, side: Side) -> Holder:
        state = self.lookup.state(point, side)
        faction = state.get("faction") if state is not None else _UNRESOLVED
        if faction is None:
            return None
        if isinstance(faction, EntityRef):
            return self.lookup.resolve(faction)
        return _UNRESOLVED


def _point(event: Event) -> EntityId | None:
    """The control point an event of the control-point analyzer is about (its first entity)."""
    if event.entities and event.entities[0].entity_id.domain is EntityDomain.CONTROL_POINT:
        return event.entities[0].entity_id
    return None


def control_events(events: Iterable[Event], before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
    """Every nation-control inference of one interval (unsorted); the diff is not read, the analyzers cite it."""
    context = ControlContext(events, before, after)
    moved: set[EntityId] = set()  # points listed under two nations moved between them: territory, not control
    for event in context.of_type(NATION_CHANGED):
        point = _point(event)
        if point is not None:
            moved.add(point)
    changed: dict[EntityId, list[Event]] = defaultdict(list)
    for event in context.of_type(CONTROLLER_CHANGED):
        point = _point(event)
        nations = context.nations_of(point) if point is not None else set()
        if point is not None and len(nations) > 1:
            moved.add(point)
        if point is not None and len(nations) == 1 and point not in moved:
            changed[next(iter(nations))].append(event)
    territorial: dict[EntityId, set[EntityId]] = defaultdict(set)
    for point in moved:
        for nation in context.nations_of(point):
            territorial[nation].add(point)
    logger.debug(
        "control points moved between nations: %s",
        log_fields(points=len(moved), nations=len(territorial)),
    )

    corroborating: dict[EntityId, list[Event]] = defaultdict(list)
    for event_type in (LOSS_RECORDED, APPEARED, DISAPPEARED):
        for event in context.of_type(event_type):
            point = _point(event)
            for nation in context.nations_of(point) if point is not None else ():
                corroborating[nation].append(event)
    for event in context.of_type(EXECUTIVE_CHANGE_RECORDED):
        if event.entities:
            corroborating[event.entities[0].entity_id].append(event)

    inferred_events: list[Event] = []
    for nation, primary in sorted(changed.items(), key=lambda item: item[0].sort_key):
        primary = [event for event in primary if _point(event) not in moved]
        if primary:
            inferred_events.extend(
                _nation_control(context, nation, primary, corroborating[nation], frozenset(territorial.get(nation, ())))
            )
    return inferred_events


def _nation_control(
    context: ControlContext,
    nation: EntityId,
    primary: list[Event],
    corroborating: list[Event],
    moved: frozenset[EntityId],
) -> list[Event]:
    earlier, later = context.holdings(nation, Side.BEFORE, moved), context.holdings(nation, Side.AFTER, moved)
    if earlier is None or later is None:
        return []  # a nation appearing or vanishing is presence, not control
    records = [event for event in corroborating if event.event_type == EXECUTIVE_CHANGE_RECORDED]
    record = records[0] if records else None
    new_executive = record.attribute("new_executive") if record is not None else None
    recorded_on = record.attribute("recorded_on") if record is not None else None
    cause = record.attribute("cause") if record is not None else None
    regions = context.lookup.state(nation, Side.AFTER)
    region_ids = regions.get("regions") if regions is not None else Unknown()
    population = (
        context.lookup.population((ref.entity_id for ref in region_ids if isinstance(ref, EntityRef)), Side.AFTER)
        if isinstance(region_ids, tuple)
        else Unknown()
    )
    unresolved = earlier.unresolved or later.unresolved
    support = Support(events=tuple(corroborating))

    events: list[Event] = []
    seat_comparable = not moved or (
        earlier.seat_point is not None and earlier.seat_point == later.seat_point and earlier.seat_point not in moved
    )
    for scope in SCOPES:
        if scope == EXECUTIVE and not seat_comparable:
            continue  # the seat itself moved between nations, or is another point afterwards
        was, now = earlier.holder(scope), later.holder(scope)
        if (isinstance(was, Unknown) and isinstance(now, Unknown)) or _same(was, now):
            continue
        agrees = (
            later.seat_basis is SeatBasis.EXECUTIVE_POINT
            and _same(new_executive if isinstance(new_executive, EntityRef) else None, later.executive)
            and _same(later.executive, now)
        )
        if unresolved:
            confidence = Confidence.LOW
        else:
            confidence = Confidence.HIGH if agrees else Confidence.MEDIUM
            if moved:
                confidence = lower(confidence)
        attributes: list[tuple[str, Observed]] = [
            ("scope", scope),
            ("before", was),
            ("after", now),
            ("shares_before", earlier.shares()),
            ("shares_after", later.shares()),
            ("point_count_before", len(earlier.controllers)),
            ("point_count_after", len(later.controllers)),
            ("points_moved", len(moved)),
            ("cause", cause),
            ("recorded_on", recorded_on),
            ("new_executive", new_executive),
            ("seat", later.seat_basis.value if later.seat_basis is not None else None),
            ("population", population),
        ]
        events.append(
            inferred(
                context.build,
                NATION_CONTROL_CHANGED,
                id_parts=(nation, scope),
                primary=primary,
                support=support,
                entities=(
                    context.lookup.ref(nation),
                    was if isinstance(was, EntityRef) else None,
                    now if isinstance(now, EntityRef) else None,
                ),
                attributes=attributes,
                confidence=confidence,
                recorded_on=recorded_on if agrees and not unresolved else None,
            )
        )
    return events
