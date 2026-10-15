"""Region alien sub-state transitions a save shows directly: crashdown, landing, facility, xenoforming level.

Each ``TIRegion*State`` belongs to one region through its ``region`` back-reference, so every event names that
region first and the sub-state second. A crashdown carries its own ``crashdownTime`` record, which dates the
event when it is set. Levels and flags are reported literally: whether xenoforming was detected or cleared, or
a landing repelled, is a reconstruction question. ``currentHP``, ``deployingArmy``, ``supportingArmyBuildup``,
``alienMissionsDetected`` and sub-state presence stay in the diff.
"""

from __future__ import annotations

from ...model.changes import StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId
from ...model.events import Event
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed
from ..common import (
    ChangeIndex,
    EventBuilder,
    Lookup,
    classify,
    confidence_for,
    primary,
    transition_attributes,
)

CRASHDOWN_CHANGED = "region.crashdown_changed"
LANDING_CHANGED = "region.landing_changed"
ALIEN_FACILITY_CHANGED = "region.alien_facility_changed"
XENOFORMING_CHANGED = "region.xenoforming_changed"

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
        index = ChangeIndex(diff)
        lookup = Lookup(before, after)
        build = EventBuilder(before, after)
        events: list[Event] = []

        events.extend(_crashdowns(index, lookup, build))
        for field_name, event_type in VALUE_FIELDS:
            for change in index.fields(DOMAIN, field_name):
                event = _region_event(event_type, change, lookup, build)
                if event is not None:
                    events.append(event)
        return events


def _region_event(
    event_type: str,
    change: StateChange,
    lookup: Lookup,
    build: EventBuilder,
    *,
    extra: tuple[StateChange, ...] = (),
    attributes: tuple[tuple[str, Observed], ...] = (),
    recorded_on: Observed = None,
) -> Event | None:
    """One sub-state field changed: the region first, then the sub-state, the literal transition and ``extra``."""
    transition = classify(change.before, change.after)
    if transition is None or change.entity_id is None:
        return None
    state_id = change.entity_id
    return build.event(
        event_type,
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
