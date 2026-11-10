"""Army transitions: region, faction, the literal ``destroyed`` flag, strength, type, presence.

Presence is reported literally (disbanded, lost or merged is a reconstruction question). Every event names the
army's home nation (the ``nation`` of its ``homeRegion``) as context only, never evidence and never cited.
"""

from __future__ import annotations

from ...kinds import military as army_kinds
from ...model.changes import ChangeKind, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId, EntityRef
from ...model.events import Event, SourceRole
from ...model.kinds import EventKind
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed
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

REGION_CHANGED = army_kinds.REGION_CHANGED.event_type
FACTION_CHANGED = army_kinds.FACTION_CHANGED.event_type
DESTROYED_CHANGED = army_kinds.DESTROYED_CHANGED.event_type
STRENGTH_CHANGED = army_kinds.STRENGTH_CHANGED.event_type
TYPE_CHANGED = army_kinds.TYPE_CHANGED.event_type
DEPLOYMENT_TYPE_CHANGED = army_kinds.DEPLOYMENT_TYPE_CHANGED.event_type
HOME_REGION_CHANGED = army_kinds.HOME_REGION_CHANGED.event_type
APPEARED = army_kinds.APPEARED.event_type
DISAPPEARED = army_kinds.DISAPPEARED.event_type
MEGAFAUNA_STATE_TYPE = "TIMegafaunaArmyState"

LIST_FIELD = "armies"
LIST_OWNERS = (EntityDomain.FACTION, EntityDomain.NATION, EntityDomain.REGION)
HANDLED_LISTS = tuple((domain, LIST_FIELD) for domain in LIST_OWNERS)
"""Every list that names armies; a nation's list has no mirroring army field and is cited by presence only."""
MIRRORED_FIELDS = (("currentRegion", army_kinds.REGION_CHANGED), ("faction", army_kinds.FACTION_CHANGED))
"""Reference fields whose owner lists armies: the earlier owner's list loses the army, the later one's gains it."""
VALUE_FIELDS = (
    ("destroyed", army_kinds.DESTROYED_CHANGED),
    ("strength", army_kinds.STRENGTH_CHANGED),
    ("armyType", army_kinds.TYPE_CHANGED),
    ("deploymentType", army_kinds.DEPLOYMENT_TYPE_CHANGED),
    ("homeRegion", army_kinds.HOME_REGION_CHANGED),
)


def list_event_type(domain: str) -> EventKind:
    return {
        EntityDomain.FACTION: army_kinds.FACTION_ARMIES_CHANGED,
        EntityDomain.NATION: army_kinds.NATION_ARMIES_CHANGED,
        EntityDomain.REGION: army_kinds.REGION_ARMIES_CHANGED,
    }[EntityDomain(domain)]


class ArmyAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        ledger = MembershipLedger(index, HANDLED_LISTS)
        build = EventBuilder(before, after, lookup)
        events: list[Event] = []

        for field_name, event_kind in MIRRORED_FIELDS:
            for change in index.fields(EntityDomain.ARMY, field_name):
                event = _mirrored(event_kind, change, lookup, ledger, build)
                if event is not None:
                    events.append(event)
        for field_name, event_kind in VALUE_FIELDS:
            for change in index.fields(EntityDomain.ARMY, field_name):
                assert change.entity_id is not None
                home = _home_nation(change.entity_id, lookup)
                event = value_transition_event(
                    event_kind,
                    change,
                    lookup,
                    build,
                    context=(*_context(change, lookup), home),
                    attributes=_home_attribute(home),
                )
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


def _home_nation(army_id: EntityId, lookup: Lookup) -> EntityRef | None:
    home_region = lookup.context_ref(army_id, "homeRegion")
    return lookup.context_ref(home_region.entity_id, "nation") if home_region is not None else None


def _home_attribute(home: EntityRef | None) -> tuple[tuple[str, Observed], ...]:
    return (("home_nation", home),) if home is not None else ()


def _mirrored(
    event_type: EventKind, change: StateChange, lookup: Lookup, ledger: MembershipLedger, build: EventBuilder
) -> Event | None:
    transition = classify(change.before, change.after)
    if transition is None or change.entity_id is None:
        return None
    army_id = change.entity_id
    other = "currentRegion" if change.field == "faction" else "faction"
    home = _home_nation(army_id, lookup)
    return build.event(
        event_type,
        id_parts=(army_id,),
        sources=mirrored_sources(change, ledger, LIST_FIELD, army_id),
        entities=(
            lookup.ref(army_id),
            lookup.context_ref(army_id, other),
            lookup.resolve(change.before),
            lookup.resolve(change.after),
            home,
        ),
        attributes=(*transition_attributes(change, transition), *_home_attribute(home)),
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
    home = _home_nation(army_id, lookup)
    attributes: list[tuple[str, Observed]] = [("side", side.value), *_home_attribute(home)]
    state = lookup.state(army_id, side)
    deployment = state.get("deploymentType") if state is not None else None
    if isinstance(deployment, str):
        attributes.append(("deployment_type", deployment))
    if army is not None and army.state_type == MEGAFAUNA_STATE_TYPE:
        attributes.append(("megafauna", True))
    return build.event(
        army_kinds.APPEARED if appeared else army_kinds.DISAPPEARED,
        id_parts=(army_id,),
        sources=sources,
        entities=(
            army,
            lookup.ref_field(army_id, "faction", side),
            lookup.ref_field(army_id, "currentRegion", side),
            home,
        ),
        attributes=attributes,
    )
