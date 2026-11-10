"""Ship transitions: the fleet it belongs to, the literal refit date, presence.

Ships keep their IDs across fleet merges, so ``fleet`` is the continuity evidence the fleet ID cannot give. A presence
event carries the design's ``hull`` (matched ``templateName`` to ``dataName`` in the fleet faction's
``shipDesigns``); the design name itself is player content and is never carried.
"""

from __future__ import annotations

from ...kinds.space import (
    FLEET_SHIPS_CHANGED,
    SHIP_APPEARED,
    SHIP_DISAPPEARED,
    SHIP_FLEET_CHANGED,
    SHIP_LAST_REFIT_CHANGED,
)
from ...model.changes import ChangeKind, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId
from ...model.events import Event, SourceRole
from ...model.snapshot import SaveSnapshot
from ...model.values import FrozenMap, Observed
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

FLEET_CHANGED = SHIP_FLEET_CHANGED.event_type
LAST_REFIT_DATE_CHANGED = SHIP_LAST_REFIT_CHANGED.event_type
APPEARED = SHIP_APPEARED.event_type
DISAPPEARED = SHIP_DISAPPEARED.event_type
FLEET_LIST_CHANGED = FLEET_SHIPS_CHANGED.event_type

HANDLED_LISTS = ((EntityDomain.FLEET, "ships"),)
VALUE_FIELDS = (("lastRefitDate", SHIP_LAST_REFIT_CHANGED),)


class ShipAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        ledger = MembershipLedger(index, HANDLED_LISTS)
        build = EventBuilder(before, after, lookup)
        events: list[Event] = []

        for change in index.fields(EntityDomain.SHIP, "fleet"):
            transition = classify(change.before, change.after)
            if transition is None or change.entity_id is None:
                continue
            ship_id = change.entity_id
            events.append(
                build.event(
                    SHIP_FLEET_CHANGED,
                    id_parts=(ship_id,),
                    sources=mirrored_sources(change, ledger, "ships", ship_id),
                    entities=(lookup.ref(ship_id), lookup.resolve(change.before), lookup.resolve(change.after)),
                    attributes=transition_attributes(change, transition),
                    confidence=confidence_for(transition),
                )
            )
        for field_name, event_type in VALUE_FIELDS:
            for change in index.fields(EntityDomain.SHIP, field_name):
                assert change.entity_id is not None
                fleet = lookup.context_ref(change.entity_id, "fleet")
                event = value_transition_event(event_type, change, lookup, build, context=(fleet,))
                if event is not None:
                    events.append(event)
        for change in index.presence(EntityDomain.SHIP):
            events.append(_presence(change, lookup, ledger, build))
        for change, member, transition in ledger.leftovers():
            events.append(list_changed_event(FLEET_SHIPS_CHANGED, change, member, transition, lookup, build))
        return events


def _presence(change: StateChange, lookup: Lookup, ledger: MembershipLedger, build: EventBuilder) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    side = Side.AFTER if appeared else Side.BEFORE
    ship_id = change.entity_id
    assert ship_id is not None
    sources = [primary(change)]
    fleet = lookup.ref_field(ship_id, "fleet", side)
    owner = lookup.ref_field(fleet.entity_id, "faction", side) if fleet is not None else None
    if fleet is not None:
        membership = Transition.ADDED if appeared else Transition.REMOVED
        cited = ledger.claim(fleet.entity_id, "ships", ship_id, membership, SourceRole.CORROBORATING)
        if cited is not None:
            sources.append(cited)
    return build.event(
        SHIP_APPEARED if appeared else SHIP_DISAPPEARED,
        id_parts=(ship_id,),
        sources=sources,
        entities=(lookup.ref(ship_id), fleet, owner),
        attributes=(("side", side.value), *_hull(ship_id, fleet.entity_id if fleet else None, lookup, side)),
    )


def _hull(ship_id: EntityId, fleet_id: EntityId | None, lookup: Lookup, side: Side) -> tuple[tuple[str, Observed], ...]:
    """The ``hullName`` of the ship's design in its fleet faction's ``shipDesigns``; nothing when any step fails."""
    ship = lookup.state(ship_id, side)
    template = ship.get("templateName") if ship is not None else None
    faction = lookup.ref_field(fleet_id, "faction", side) if fleet_id is not None else None
    faction_state = lookup.state(faction.entity_id, side) if faction is not None else None
    designs = faction_state.get("shipDesigns") if faction_state is not None else None
    if not isinstance(template, str) or not isinstance(designs, FrozenMap):
        return ()
    design = dict(designs.items).get(template)
    hull = dict(design.items).get("hullName") if isinstance(design, FrozenMap) else None
    return (("hull", hull),) if isinstance(hull, str) else ()
