"""Fleet transitions: faction, docking, orbit, barycenter, parent fleet, combat flag, presence.

A fleet ID lives only as long as the fleet (merged fleets vanish, ``parentFleet`` often dangles), so presence and
unresolved ``parentFleet`` changes are reported literally, never as evidence of a merge or a loss.
"""

from __future__ import annotations

from ...kinds.space import (
    FACTION_FLEETS_CHANGED,
    FLEET_APPEARED,
    FLEET_BARYCENTER_CHANGED,
    FLEET_DISAPPEARED,
    FLEET_DOCKED_LOCATION_CHANGED,
    FLEET_FACTION_CHANGED,
    FLEET_IN_COMBAT_CHANGED,
    FLEET_ORBIT_CHANGED,
    FLEET_PARENT_CHANGED,
    HAB_DOCKED_FLEETS_CHANGED,
)
from ...model.changes import ChangeKind, StateChange, StateDiff
from ...model.entities import EntityDomain
from ...model.events import Event, SourceRole
from ...model.kinds import EventKind
from ...model.snapshot import SaveSnapshot
from ..common import (
    EventBuilder,
    Lookup,
    MembershipLedger,
    Side,
    Transition,
    classify,
    confidence_for,
    list_changed_event,
    mirrored_sources,
    primary,
    transition_attributes,
    value_transition_event,
)

FACTION_CHANGED = FLEET_FACTION_CHANGED.event_type
DOCKED_LOCATION_CHANGED = FLEET_DOCKED_LOCATION_CHANGED.event_type
ORBIT_CHANGED = FLEET_ORBIT_CHANGED.event_type
BARYCENTER_CHANGED = FLEET_BARYCENTER_CHANGED.event_type
PARENT_FLEET_CHANGED = FLEET_PARENT_CHANGED.event_type
IN_COMBAT_CHANGED = FLEET_IN_COMBAT_CHANGED.event_type
APPEARED = FLEET_APPEARED.event_type
DISAPPEARED = FLEET_DISAPPEARED.event_type
FACTION_LIST_CHANGED = FACTION_FLEETS_CHANGED.event_type
DOCKED_LIST_CHANGED = HAB_DOCKED_FLEETS_CHANGED.event_type

HANDLED_LISTS = ((EntityDomain.FACTION, "fleets"), (EntityDomain.SPACE_OBJECT, "dockedFleets"))
MIRRORED_FIELDS = (
    ("faction", FLEET_FACTION_CHANGED, "fleets"),
    ("dockedLocation", FLEET_DOCKED_LOCATION_CHANGED, "dockedFleets"),
)
"""Reference fields whose owner lists fleets, with the owner's list field."""
VALUE_FIELDS = (
    ("orbitState", FLEET_ORBIT_CHANGED),
    ("barycenter", FLEET_BARYCENTER_CHANGED),
    ("parentFleet", FLEET_PARENT_CHANGED),
    ("inCombat", FLEET_IN_COMBAT_CHANGED),
)

_LIST_EVENT = {
    EntityDomain.FACTION.value: FACTION_FLEETS_CHANGED,
    EntityDomain.SPACE_OBJECT.value: HAB_DOCKED_FLEETS_CHANGED,
}


class FleetAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        ledger = MembershipLedger(index, HANDLED_LISTS)
        build = EventBuilder(before, after, lookup)
        events: list[Event] = []

        for field_name, event_type, list_field in MIRRORED_FIELDS:
            for change in index.fields(EntityDomain.FLEET, field_name):
                event = _mirrored(event_type, list_field, change, lookup, ledger, build)
                if event is not None:
                    events.append(event)
        for field_name, event_type in VALUE_FIELDS:
            for change in index.fields(EntityDomain.FLEET, field_name):
                assert change.entity_id is not None
                faction = lookup.context_ref(change.entity_id, "faction")
                event = value_transition_event(event_type, change, lookup, build, context=(faction,))
                if event is not None:
                    events.append(event)
        for change in index.presence(EntityDomain.FLEET):
            events.append(_presence(change, lookup, ledger, build))
        for change, member, transition in ledger.leftovers():
            events.append(list_changed_event(_LIST_EVENT[change.domain], change, member, transition, lookup, build))
        return events


def _mirrored(
    event_type: EventKind,
    list_field: str,
    change: StateChange,
    lookup: Lookup,
    ledger: MembershipLedger,
    build: EventBuilder,
) -> Event | None:
    transition = classify(change.before, change.after)
    if transition is None or change.entity_id is None:
        return None
    fleet_id = change.entity_id
    context = lookup.context_ref(fleet_id, "faction") if change.field != "faction" else None
    return build.event(
        event_type,
        id_parts=(fleet_id,),
        sources=mirrored_sources(change, ledger, list_field, fleet_id),
        entities=(lookup.ref(fleet_id), context, lookup.resolve(change.before), lookup.resolve(change.after)),
        attributes=transition_attributes(change, transition),
        confidence=confidence_for(transition),
    )


def _presence(change: StateChange, lookup: Lookup, ledger: MembershipLedger, build: EventBuilder) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    side = Side.AFTER if appeared else Side.BEFORE
    membership = Transition.ADDED if appeared else Transition.REMOVED
    fleet_id = change.entity_id
    assert fleet_id is not None
    sources = [primary(change)]
    faction = lookup.ref_field(fleet_id, "faction", side)
    docked = lookup.ref_field(fleet_id, "dockedLocation", side)
    for owner, list_field in ((faction, "fleets"), (docked, "dockedFleets")):
        if owner is not None:
            cited = ledger.claim(owner.entity_id, list_field, fleet_id, membership, SourceRole.CORROBORATING)
            if cited is not None:
                sources.append(cited)
    return build.event(
        FLEET_APPEARED if appeared else FLEET_DISAPPEARED,
        id_parts=(fleet_id,),
        sources=sources,
        entities=(lookup.ref(fleet_id), faction, docked),
        attributes=(("side", side.value),),
    )
