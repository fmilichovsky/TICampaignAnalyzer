"""Interstate war events: presence, the two alliances, the leading nations, last fighting.

Each side's nations list every opponent in their ``wars``; those entries and the global ``interstateWars`` list are
cited as corroboration, and only unexplained entries are reported on their own. Nothing here says a war was declared,
won or lost: that is reconstruction.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple

from ...kinds import campaign as campaign_kinds
from ...model.changes import ChangeKind, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId, EntityRef
from ...model.events import Event, EventSource, SourceRole
from ...model.kinds import EventKind
from ...model.records import ItemEntry
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed
from ..campaign.global_values import INTERSTATE_WARS
from ..common import (
    EventBuilder,
    Lookup,
    MembershipLedger,
    Side,
    Transition,
    confidence_for,
    list_changed_event,
    primary,
    value_transition_event,
)
from .nations import relation_events

APPEARED = "war.appeared"
DISAPPEARED = "war.disappeared"
ALLIANCE_CHANGED = "war.alliance_changed"
ATTACKER_CHANGED = "war.attacker_changed"
DEFENDER_CHANGED = "war.defender_changed"
LAST_FIGHTING_CHANGED = "war.last_fighting_changed"
WARS_LIST_CHANGED = "nation.wars_changed"

ATTACKING = "_attackingAlliance"
DEFENDING = "_defendingAlliance"


class WarSide(NamedTuple):
    alliance: str
    label: str
    leader: str


ATTACKERS = WarSide(ATTACKING, "attacking", "attacker")
DEFENDERS = WarSide(DEFENDING, "defending", "defender")
SIDES = ((ATTACKERS, DEFENDERS), (DEFENDERS, ATTACKERS))
"""Each side of a war with its opponents."""
LEFTOVER_TYPES: Mapping[str, EventKind | str] = {
    ATTACKING: "war.attacking_alliance_changed",
    DEFENDING: "war.defending_alliance_changed",
    "wars": WARS_LIST_CHANGED,
    INTERSTATE_WARS: campaign_kinds.INTERSTATE_WARS_CHANGED,
}
HANDLED_LISTS = (
    (EntityDomain.WAR, ATTACKING),
    (EntityDomain.WAR, DEFENDING),
    (EntityDomain.NATION, "wars"),
    (EntityDomain.GLOBAL_VALUES, INTERSTATE_WARS),
)
VALUE_FIELDS = (("attacker", ATTACKER_CHANGED), ("defender", DEFENDER_CHANGED))
START_DATE = "startDate"
LAST_FIGHTING = "dateOfLastFighting"


class WarAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        ledger = MembershipLedger(index, HANDLED_LISTS)
        build = EventBuilder(before, after, lookup)
        events: list[Event] = []

        global_values = tuple(change.entity_id for change in index.fields(EntityDomain.GLOBAL_VALUES, INTERSTATE_WARS))
        for change in index.presence(EntityDomain.WAR):
            events.append(_presence(change, lookup, ledger, build, global_values))
        for own_side, opponents in SIDES:
            for war_id, member, transition in ledger.pending(own_side.alliance):
                events.append(_alliance_changed(war_id, own_side, opponents, member, transition, lookup, ledger, build))
        for field_name, event_type in VALUE_FIELDS:
            for change in index.fields(EntityDomain.WAR, field_name):
                event = value_transition_event(event_type, change, lookup, build)
                if event is not None:
                    events.append(event)
        for change in index.fields(EntityDomain.WAR, LAST_FIGHTING):
            event = value_transition_event(LAST_FIGHTING_CHANGED, change, lookup, build, recorded_on=change.after)
            if event is not None:
                events.append(event)
        events.extend(relation_events("wars", lookup, ledger, build))
        for change, leftover, transition in ledger.leftovers():
            assert change.field is not None
            events.append(list_changed_event(LEFTOVER_TYPES[change.field], change, leftover, transition, lookup, build))
        return events


def side_members(lookup: Lookup, war_id: EntityId, war_side: WarSide, side: Side) -> list[EntityId]:
    """The nations of one side of a war on one snapshot: its alliance list plus its leading nation, deduplicated."""
    state = lookup.state(war_id, side)
    if state is None:
        return []
    values: list[Observed] = []
    alliance = state.get(war_side.alliance)
    if isinstance(alliance, tuple):
        values.extend(alliance)
    values.append(state.get(war_side.leader))
    members: list[EntityId] = []
    for value in values:
        if isinstance(value, EntityRef) and value.entity_id not in members:
            members.append(value.entity_id)
    return members


def _war_pairs(
    ledger: MembershipLedger, nations: list[EntityId], opponents: list[EntityId], transition: Transition
) -> list[EventSource]:
    """Claim, as corroboration, both nations' ``wars`` entries for every pair across the two sides."""
    sources: list[EventSource] = []
    for nation in nations:
        for opponent in opponents:
            for owner, member in ((nation, opponent), (opponent, nation)):
                cited = ledger.claim(owner, "wars", member, transition, SourceRole.CORROBORATING)
                if cited is not None:
                    sources.append(cited)
    return sources


def _start_date(lookup: Lookup, change: StateChange, war_id: EntityId) -> tuple[Observed, EventSource | None]:
    """The literal ``startDate`` record of an appeared war and a source pointing at it, if present."""
    record_set = lookup.record_set(war_id, START_DATE, Side.AFTER)
    if record_set is None or not isinstance(record_set.entries, tuple) or len(record_set.entries) != 1:
        return None, None
    entry = record_set.entries[0]
    if not isinstance(entry, ItemEntry):
        return None, None
    return entry.value, EventSource(change, SourceRole.PRIMARY, START_DATE, record_set.entry_location(entry))


def _presence(
    change: StateChange,
    lookup: Lookup,
    ledger: MembershipLedger,
    build: EventBuilder,
    global_values: tuple[EntityId | None, ...],
) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    war_id = change.entity_id
    assert war_id is not None
    side = Side.AFTER if appeared else Side.BEFORE
    attackers = side_members(lookup, war_id, ATTACKERS, side)
    defenders = side_members(lookup, war_id, DEFENDERS, side)
    sources = [primary(change)]
    attributes: list[tuple[str, Observed]] = [("side", side.value)]
    started_on: Observed = None
    if appeared:
        started_on, start_source = _start_date(lookup, change, war_id)
        if start_source is not None:
            sources.append(start_source)
            attributes.append(("started_on", started_on))
    transition = Transition.ADDED if appeared else Transition.REMOVED
    for owner in global_values:
        cited = ledger.claim(owner, INTERSTATE_WARS, war_id, transition, SourceRole.CORROBORATING) if owner else None
        if cited is not None:
            sources.append(cited)
    sources.extend(_war_pairs(ledger, attackers, defenders, transition))
    return build.event(
        APPEARED if appeared else DISAPPEARED,
        id_parts=(war_id,),
        sources=sources,
        entities=(lookup.ref(war_id), *(lookup.ref(nation) for nation in attackers + defenders)),
        attributes=attributes,
        recorded_on=started_on,
    )


def _alliance_changed(
    war_id: EntityId,
    own_side: WarSide,
    opponents: WarSide,
    member: EntityRef,
    transition: Transition,
    lookup: Lookup,
    ledger: MembershipLedger,
    build: EventBuilder,
) -> Event:
    """A nation entered or left one side of a war that is present on both snapshots."""
    own = ledger.claim(war_id, own_side.alliance, member.entity_id, transition, SourceRole.PRIMARY)
    assert own is not None  # pending members are claimable
    side = Side.AFTER if transition is Transition.ADDED else Side.BEFORE
    opposing = side_members(lookup, war_id, opponents, side)
    return build.event(
        ALLIANCE_CHANGED,
        id_parts=(war_id, own_side.label, member.entity_id, transition.value),
        sources=[own, *_war_pairs(ledger, [member.entity_id], opposing, transition)],
        entities=(lookup.ref(war_id), lookup.resolve(member)),
        attributes=(("side", own_side.label), ("member", member), ("transition", transition.value)),
        confidence=confidence_for(transition),
    )
