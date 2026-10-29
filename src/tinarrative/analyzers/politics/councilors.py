"""Councilor events for the transitions a save shows directly: faction, status, location, detention, presence.

Presence is reported as-is; whether a vanished councilor died or was dismissed is left to reconstruction.
"""

from __future__ import annotations

from ...model.changes import ChangeKind, StateChange, StateDiff
from ...model.entities import EntityDomain
from ...model.events import Event, SourceRole
from ...model.snapshot import SaveSnapshot
from ..common import (
    ChangeIndex,
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
)

FACTION_CHANGED = "councilor.faction_changed"
STATUS_CHANGED = "councilor.status_changed"
LOCATION_CHANGED = "councilor.location_changed"
DETAINING_FACTION_CHANGED = "councilor.detaining_faction_changed"
APPEARED = "councilor.appeared"
DISAPPEARED = "councilor.disappeared"
ROSTER_CHANGED = "faction.councilors_changed"

HANDLED_LISTS = ((EntityDomain.FACTION, "councilors"),)
VALUE_FIELDS = (
    ("status", STATUS_CHANGED),
    ("location", LOCATION_CHANGED),
    ("detainingFaction", DETAINING_FACTION_CHANGED),
)
"""Fields whose change is an event on its own; ``XP``, ``attributes``, ``priorLocation`` stay in the diff."""


class CouncilorAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = ChangeIndex(diff)
        lookup = Lookup(before, after)
        ledger = MembershipLedger(index, HANDLED_LISTS)
        build = EventBuilder(before, after)
        events: list[Event] = []

        for change in index.fields(EntityDomain.COUNCILOR, "faction"):
            transition = classify(change.before, change.after)
            if transition is None or change.entity_id is None:
                continue
            councilor_id = change.entity_id
            events.append(
                build.event(
                    FACTION_CHANGED,
                    id_parts=(councilor_id,),
                    sources=mirrored_sources(change, ledger, "councilors", councilor_id),
                    entities=(lookup.ref(councilor_id), lookup.resolve(change.before), lookup.resolve(change.after)),
                    attributes=transition_attributes(change, transition),
                    confidence=confidence_for(transition),
                )
            )
        for field_name, event_type in VALUE_FIELDS:
            for change in index.fields(EntityDomain.COUNCILOR, field_name):
                transition = classify(change.before, change.after)
                if transition is None or change.entity_id is None:
                    continue
                councilor_id = change.entity_id
                events.append(
                    build.event(
                        event_type,
                        id_parts=(councilor_id,),
                        sources=(primary(change),),
                        entities=(
                            lookup.ref(councilor_id),
                            lookup.context_ref(councilor_id, "faction"),
                            lookup.resolve(change.before),
                            lookup.resolve(change.after),
                        ),
                        attributes=transition_attributes(change, transition),
                        confidence=confidence_for(transition),
                    )
                )
        for change in index.presence(EntityDomain.COUNCILOR):
            events.append(_presence(change, lookup, ledger, build))
        for change, member, transition in ledger.leftovers():
            events.append(list_changed_event(ROSTER_CHANGED, change, member, transition, lookup, build))
        return events


def _presence(change: StateChange, lookup: Lookup, ledger: MembershipLedger, build: EventBuilder) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    side = Side.AFTER if appeared else Side.BEFORE
    councilor_id = change.entity_id
    assert councilor_id is not None
    sources = [primary(change)]
    faction = lookup.ref_field(councilor_id, "faction", side)
    if faction is not None:
        membership = Transition.ADDED if appeared else Transition.REMOVED
        cited = ledger.claim(faction.entity_id, "councilors", councilor_id, membership, SourceRole.CORROBORATING)
        if cited is not None:
            sources.append(cited)
    return build.event(
        APPEARED if appeared else DISAPPEARED,
        id_parts=(councilor_id,),
        sources=sources,
        entities=(lookup.ref(councilor_id), faction),
        attributes=(("side", side.value),),
    )
