"""Region alien sub-state transitions: crashdown, landing, facility, xenoforming level.

Events name the region (the sub-state's ``region`` back-reference) first, then the sub-state; a set
``crashdownTime`` dates the crashdown event. Flags and levels are literal: what they mean (a landing repelled,
xenoforming cleared) is a reconstruction question.
"""

from __future__ import annotations

from ...kinds.aliens import ALIEN_FACILITY_CHANGED, CRASHDOWN_CHANGED, LANDING_CHANGED, XENOFORMING_CHANGED
from ...model.changes import ChangeIndex, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId
from ...model.events import Event
from ...model.kinds import EventKind
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed
from ..common import (
    EventBuilder,
    Lookup,
    classify,
    confidence_for,
    primary,
    transition_attributes,
)

DOMAIN = EntityDomain.REGION_ALIEN_STATE
CRASHDOWN_PRESENT = "crashdownPresent"
CRASHDOWN_TIME = "crashdownTime"
VALUE_FIELDS = (
    ("landingPresent", LANDING_CHANGED),
    ("built", ALIEN_FACILITY_CHANGED),
    ("xenoformingLevel", XENOFORMING_CHANGED),
)
"""Headline field of a sub-state type and its event; the field names are unique across the five types."""


class RegionAlienAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        build = EventBuilder(before, after, lookup)
        events: list[Event] = []

        events.extend(_crashdowns(index, lookup, build))
        for field_name, kind in VALUE_FIELDS:
            for change in index.fields(DOMAIN, field_name):
                event = _region_event(kind, change, lookup, build)
                if event is not None:
                    events.append(event)
        return events


def _region_event(
    kind: EventKind,
    change: StateChange,
    lookup: Lookup,
    build: EventBuilder,
    *,
    extra: tuple[StateChange, ...] = (),
    attributes: tuple[tuple[str, Observed], ...] = (),
    recorded_on: Observed = None,
) -> Event | None:
    transition = classify(change.before, change.after)
    if transition is None or change.entity_id is None:
        return None
    state_id = change.entity_id
    return build.event(
        kind,
        id_parts=(state_id,),
        sources=(primary(change), *(primary(other) for other in extra)),
        entities=(lookup.context_ref(state_id, "region"), lookup.ref(state_id)),
        attributes=(*transition_attributes(change, transition), *attributes),
        confidence=confidence_for(transition),
        recorded_on=recorded_on,
    )


def _crashdowns(index: ChangeIndex, lookup: Lookup, build: EventBuilder) -> list[Event]:
    """One event per crashdown sub-state whose flag or ``crashdownTime`` record changed, dated by the new time."""
    present = {change.entity_id: change for change in index.fields(DOMAIN, CRASHDOWN_PRESENT)}
    times = {change.entity_id: change for change in index.fields(DOMAIN, CRASHDOWN_TIME)}
    events: list[Event] = []
    for state_id in sorted(present.keys() | times.keys(), key=_sort_key):
        flag, time = present.get(state_id), times.get(state_id)
        recorded_on = time.after if time is not None else None
        event: Event | None = None
        if flag is not None:
            extra = (time,) if time is not None else ()
            attributes = (("crashdown_time", time.after),) if time is not None else ()
            event = _region_event(
                CRASHDOWN_CHANGED, flag, lookup, build, extra=extra, attributes=attributes, recorded_on=recorded_on
            )
        if event is None and time is not None:
            event = _region_event(CRASHDOWN_CHANGED, time, lookup, build, recorded_on=recorded_on)
        if event is not None:
            events.append(event)
    return events


def _sort_key(state_id: EntityId | None) -> str:
    return str(state_id)
