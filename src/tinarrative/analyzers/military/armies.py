"""Army transitions a save shows directly: region, faction, the ``destroyed`` flag, strength, type, presence.

The ``destroyed`` flag is the only place this analyzer uses that word, because the save carries it literally.
An army present in one snapshot only is reported as absent from (or present only in) that snapshot; whether
it was disbanded, lost in battle or merged is a reconstruction question. A presence event of a
``TIMegafaunaArmyState`` army carries ``megafauna = True``; regular armies carry no such attribute.
``priorRegion``, ``operationTarget``, ``destinationQueue``, ``currentOperations``, the transit dates,
``huntingXenofauna`` and ``bonusTechLevel`` stay in the diff.
"""

from __future__ import annotations

from ...model.changes import ChangeKind, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityRef
from ...model.events import Event, SourceRole
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed
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
    value_transition_event,
)

REGION_CHANGED = "army.region_changed"
FACTION_CHANGED = "army.faction_changed"
DESTROYED_CHANGED = "army.destroyed_changed"
STRENGTH_CHANGED = "army.strength_changed"
TYPE_CHANGED = "army.type_changed"
DEPLOYMENT_TYPE_CHANGED = "army.deployment_type_changed"
HOME_REGION_CHANGED = "army.home_region_changed"
APPEARED = "army.appeared"
DISAPPEARED = "army.disappeared"
MEGAFAUNA_STATE_TYPE = "TIMegafaunaArmyState"

LIST_FIELD = "armies"
LIST_OWNERS = (EntityDomain.FACTION, EntityDomain.NATION, EntityDomain.REGION)
HANDLED_LISTS = tuple((domain, LIST_FIELD) for domain in LIST_OWNERS)
"""Every list that names armies; a nation's list has no mirroring army field and is cited by presence only."""
MIRRORED_FIELDS = (("currentRegion", REGION_CHANGED), ("faction", FACTION_CHANGED))
"""Reference fields whose owner lists armies: the earlier owner's list loses the army, the later one's gains it."""
VALUE_FIELDS = (
    ("destroyed", DESTROYED_CHANGED),
    ("strength", STRENGTH_CHANGED),
    ("armyType", TYPE_CHANGED),
    ("deploymentType", DEPLOYMENT_TYPE_CHANGED),
    ("homeRegion", HOME_REGION_CHANGED),
)


def list_event_type(domain: str) -> str:
    return f"{domain}.{LIST_FIELD}_changed"


class ArmyAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = ChangeIndex(diff)
        lookup = Lookup(before, after)
        ledger = MembershipLedger(index, HANDLED_LISTS)
        build = EventBuilder(before, after)
        events: list[Event] = []

        for field_name, event_type in MIRRORED_FIELDS:
            for change in index.fields(EntityDomain.ARMY, field_name):
                event = _mirrored(event_type, change, lookup, ledger, build)
                if event is not None:
                    events.append(event)
        for field_name, event_type in VALUE_FIELDS:
            for change in index.fields(EntityDomain.ARMY, field_name):
                event = value_transition_event(event_type, change, lookup, build, context=_context(change, lookup))
                if event is not None:
                    events.append(event)
        for change in index.presence(EntityDomain.ARMY):
            events.append(_presence(change, lookup, ledger, build))
        for change, member, transition in ledger.leftovers():
            events.append(list_changed_event(list_event_type(change.domain), change, member, transition, lookup, build))
        return events


def _context(change: StateChange, lookup: Lookup) -> tuple[EntityRef | None, ...]:
    assert change.entity_id is not None
    return (lookup.context_ref(change.entity_id, "faction"), lookup.context_ref(change.entity_id, "currentRegion"))


def _mirrored(
    event_type: str, change: StateChange, lookup: Lookup, ledger: MembershipLedger, build: EventBuilder
) -> Event | None:
    transition = classify(change.before, change.after)
    if transition is None or change.entity_id is None:
        return None
    army_id = change.entity_id
    other = "currentRegion" if change.field == "faction" else "faction"
    return build.event(
        event_type,
        id_parts=(army_id,),
        sources=mirrored_sources(change, ledger, LIST_FIELD, army_id),
        entities=(
            lookup.ref(army_id),
            lookup.context_ref(army_id, other),
            lookup.resolve(change.before),
            lookup.resolve(change.after),
        ),
        attributes=transition_attributes(change, transition),
        confidence=confidence_for(transition),
    )


def _presence(change: StateChange, lookup: Lookup, ledger: MembershipLedger, build: EventBuilder) -> Event:
    """Cite every handled list (faction, nation, region) that names the army on the side where it exists."""
    appeared = change.kind is ChangeKind.APPEARED
    side = Side.AFTER if appeared else Side.BEFORE
    membership = Transition.ADDED if appeared else Transition.REMOVED
    army_id = change.entity_id
    assert army_id is not None
    sources = [primary(change)]
    for owner, member, transition in ledger.pending(LIST_FIELD):
        if transition is membership and member.entity_id == army_id:
            cited = ledger.claim(owner, LIST_FIELD, army_id, membership, SourceRole.CORROBORATING)
            if cited is not None:
                sources.append(cited)
    army = lookup.ref(army_id)
    attributes: list[tuple[str, Observed]] = [("side", side.value)]
    if army is not None and army.state_type == MEGAFAUNA_STATE_TYPE:
        attributes.append(("megafauna", True))
    return build.event(
        APPEARED if appeared else DISAPPEARED,
        id_parts=(army_id,),
        sources=sources,
        entities=(army, lookup.ref_field(army_id, "faction", side), lookup.ref_field(army_id, "currentRegion", side)),
        attributes=attributes,
    )
