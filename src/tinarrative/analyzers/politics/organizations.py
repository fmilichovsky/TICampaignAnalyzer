"""Organization events: presence, the assigned councilor and the faction pool.

A councilor's ``orgs`` and a faction's ``unassignedOrgs`` mirror ``assignedCouncilor``, so an assignment cites them as
corroboration; only unexplained list changes are reported on their own. Which acquisitions matter is reconstruction.
"""

from __future__ import annotations

from ...kinds.control import (
    COUNCILOR_ORGS_CHANGED,
    FACTION_UNASSIGNED_ORGS_CHANGED,
    ORGANIZATION_APPEARED,
    ORGANIZATION_ASSIGNED_COUNCILOR_CHANGED,
    ORGANIZATION_DISAPPEARED,
    ORGANIZATION_FACTION_ORBIT_CHANGED,
)
from ...model.changes import ChangeKind, StateChange, StateDiff
from ...model.entities import EntityDomain
from ...model.events import Event, SourceRole
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

APPEARED = ORGANIZATION_APPEARED.event_type
DISAPPEARED = ORGANIZATION_DISAPPEARED.event_type
ASSIGNED_COUNCILOR_CHANGED = ORGANIZATION_ASSIGNED_COUNCILOR_CHANGED.event_type
FACTION_ORBIT_CHANGED = ORGANIZATION_FACTION_ORBIT_CHANGED.event_type
UNASSIGNED_ORGS_CHANGED = FACTION_UNASSIGNED_ORGS_CHANGED.event_type

HANDLED_LISTS = (
    (EntityDomain.COUNCILOR, "orgs"),
    (EntityDomain.FACTION, "unassignedOrgs"),
)
LIST_EVENT_TYPES = {"orgs": COUNCILOR_ORGS_CHANGED, "unassignedOrgs": FACTION_UNASSIGNED_ORGS_CHANGED}


class OrganizationAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        ledger = MembershipLedger(index, HANDLED_LISTS)
        build = EventBuilder(before, after, lookup)
        events: list[Event] = []

        for change in index.presence(EntityDomain.ORGANIZATION):
            events.append(_presence(change, lookup, ledger, build))
        for change in index.fields(EntityDomain.ORGANIZATION, "assignedCouncilor"):
            event = _assignment(change, lookup, ledger, build)
            if event is not None:
                events.append(event)
        for change in index.fields(EntityDomain.ORGANIZATION, "factionOrbit"):
            event = value_transition_event(
                ORGANIZATION_FACTION_ORBIT_CHANGED,
                change,
                lookup,
                build,
                context=(lookup.context_ref(change.entity_id, "homeRegion"),) if change.entity_id else (),
            )
            if event is not None:
                events.append(event)
        for change, member, transition in ledger.leftovers():
            event_type = LIST_EVENT_TYPES[change.field or ""]
            events.append(list_changed_event(event_type, change, member, transition, lookup, build))
        return events


def _assignment(change: StateChange, lookup: Lookup, ledger: MembershipLedger, build: EventBuilder) -> Event | None:
    transition = classify(change.before, change.after)
    org_id = change.entity_id
    if transition is None or org_id is None:
        return None
    sources = mirrored_sources(change, ledger, "orgs", org_id)
    # an assignment takes the organization out of its new holder's faction pool; a release puts it back
    if transition is Transition.SET:
        holder, side, membership = change.after, Side.AFTER, Transition.REMOVED
    elif transition is Transition.CLEARED:
        holder, side, membership = change.before, Side.BEFORE, Transition.ADDED
    else:
        holder, side, membership = None, Side.AFTER, Transition.ADDED
    councilor = lookup.resolve(holder)
    faction = lookup.ref_field(councilor.entity_id, "faction", side) if councilor is not None else None
    if faction is not None:
        cited = ledger.claim(faction.entity_id, "unassignedOrgs", org_id, membership, SourceRole.CORROBORATING)
        if cited is not None:
            sources.append(cited)
    return build.event(
        ORGANIZATION_ASSIGNED_COUNCILOR_CHANGED,
        id_parts=(org_id,),
        sources=sources,
        entities=(
            lookup.ref(org_id),
            lookup.context_ref(org_id, "homeRegion"),
            lookup.resolve(change.before),
            lookup.resolve(change.after),
        ),
        attributes=transition_attributes(change, transition),
        confidence=confidence_for(transition),
    )


def _presence(change: StateChange, lookup: Lookup, ledger: MembershipLedger, build: EventBuilder) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    side = Side.AFTER if appeared else Side.BEFORE
    org_id = change.entity_id
    assert org_id is not None
    sources = [primary(change)]
    councilor = lookup.ref_field(org_id, "assignedCouncilor", side)
    if councilor is not None:
        membership = Transition.ADDED if appeared else Transition.REMOVED
        cited = ledger.claim(councilor.entity_id, "orgs", org_id, membership, SourceRole.CORROBORATING)
        if cited is not None:
            sources.append(cited)
    return build.event(
        ORGANIZATION_APPEARED if appeared else ORGANIZATION_DISAPPEARED,
        id_parts=(org_id,),
        sources=sources,
        entities=(lookup.ref(org_id), lookup.ref_field(org_id, "homeRegion", side), councilor),
        attributes=(("side", side.value),),
    )
