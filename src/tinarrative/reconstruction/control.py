"""Explicit reconstruction rule: which faction controls a nation, read from its control points.

The control-point analyzer reports each point's controller and nothing more; only the rule here says that a
faction's hold on a nation changed. Evidence is cited as ``reconstruction.common`` describes.

The evidence is the investigation of 2026-10-18 recorded in ``docs/game-data-notes/higher-level-event-sources.md``
(nation control; the five older private saves, counts only). Every one of the 295 nations with control points has
exactly one point with ``positionInNation = 0`` (295 of 540 points), typed ``Executive`` on 177 of them and after
the regime on the rest, so position 0 is the executive seat. Between consecutive saves (re-checked 2026-10-19)
the faction holding it changed on 1, 2, 5 and 4 nations, the plurality controller on 3, 2, 3 and 4 and the sole
controller on 1, 2, 3 and 3.

Rule:

- ``faction.nation_control_changed``: one per nation and scope whose holder differs between the two snapshots,
  for a nation with at least one ``control_point.controller_changed`` (primary). The scopes are ``executive``
  (the faction holding the position-0 point), ``plurality`` (the faction holding most points; a tie or no
  controlled point is ``null``) and ``sole`` (the faction holding every point, else ``null``). ``shares_before`` and
  ``shares_after`` count the points per faction. The nation's ``nation.executive_change_recorded``,
  ``control_point.loss_recorded`` and control-point presence events corroborate. High when the executive record
  names the new executive holder and that faction is the scope's new holder, and then dated by the record;
  medium otherwise; low when any point of the nation is unresolved on either side, the scope's holder then
  ``Unknown``. A nation with a point whose ``nation`` changed is skipped: that is territory, not control.

The line says control changed; the recorded cause is an attribute, never a reading (coup, purge): that is the
``faction.takeover`` narrative rule's work.
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
from ..model.changes import StateDiff
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import Confidence, Event
from ..model.snapshot import SaveSnapshot
from ..model.values import FrozenMap, Observed, Unknown, UnknownReason
from .common import ObjectiveIndex, Support, control_points, executive_seat, inferred

NATION_CONTROL_CHANGED = "faction.nation_control_changed"
RULE_TYPES = (NATION_CONTROL_CHANGED,)

EXECUTIVE = "executive"
PLURALITY = "plurality"
SOLE = "sole"
SCOPES = (EXECUTIVE, PLURALITY, SOLE)

_UNRESOLVED = Unknown(UnknownReason.UNRESOLVED_REFERENCE)

Holder = EntityRef | None | Unknown
"""A scope's holder: a faction, no faction (``null``), or ``Unknown`` when a point it depends on is unresolved."""


@dataclass(frozen=True)
class Holdings:
    """A nation's control points on one side: each point's controller, and the scopes read from them."""

    controllers: tuple[Holder, ...]
    executive: Holder

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
        self.build = EventBuilder(before, after)

    def of_type(self, event_type: str) -> tuple[Event, ...]:
        return self.objective.of_type(event_type)

    def nations_of(self, point: EntityId) -> set[EntityId]:
        """The nations the point belongs to on either side."""
        refs = (self.lookup.ref_field(point, "nation", side) for side in (Side.BEFORE, Side.AFTER))
        return {ref.entity_id for ref in refs if ref is not None}

    def holdings(self, nation: EntityId, side: Side) -> Holdings | None:
        """The nation's control points on one side; ``None`` when the nation or its point list is not there."""
        points = control_points(self.lookup, nation, side)
        if points is None:
            return None
        controllers = tuple(self._controller(point.entity_id, side) for point in points)
        seat = executive_seat(self.lookup, nation, side)
        executive = self._controller(seat.ref.entity_id, side) if seat is not None else _UNRESOLVED
        return Holdings(controllers, executive)

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
    skipped: set[EntityId] = set()
    for event in context.of_type(NATION_CHANGED):
        point = _point(event)
        if point is not None:
            skipped |= context.nations_of(point)

    changed: dict[EntityId, list[Event]] = defaultdict(list)
    for event in context.of_type(CONTROLLER_CHANGED):
        point = _point(event)
        nations = context.nations_of(point) if point is not None else set()
        if len(nations) != 1:
            skipped |= nations  # a point listed under two nations moved between them
            continue
        changed[next(iter(nations))].append(event)

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
        if nation not in skipped:
            inferred_events.extend(_nation_control(context, nation, primary, corroborating[nation]))
    return inferred_events


def _nation_control(
    context: ControlContext, nation: EntityId, primary: list[Event], corroborating: list[Event]
) -> list[Event]:
    earlier, later = context.holdings(nation, Side.BEFORE), context.holdings(nation, Side.AFTER)
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
    for scope in SCOPES:
        was, now = earlier.holder(scope), later.holder(scope)
        if (isinstance(was, Unknown) and isinstance(now, Unknown)) or _same(was, now):
            continue
        agrees = _same(new_executive if isinstance(new_executive, EntityRef) else None, later.executive) and _same(
            later.executive, now
        )
        if unresolved:
            confidence = Confidence.LOW
        else:
            confidence = Confidence.HIGH if agrees else Confidence.MEDIUM
        attributes: list[tuple[str, Observed]] = [
            ("scope", scope),
            ("before", was),
            ("after", now),
            ("shares_before", earlier.shares()),
            ("shares_after", later.shares()),
            ("point_count_before", len(earlier.controllers)),
            ("point_count_after", len(later.controllers)),
            ("cause", cause),
            ("recorded_on", recorded_on),
            ("new_executive", new_executive),
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
