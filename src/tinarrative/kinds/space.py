"""Fleets, habs, ships and space-combat events, and the campaigns, colonisation waves and fleet buildups told from
them."""

from __future__ import annotations

from ..diff.render import render_value
from ..model.entities import EntityDomain
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole, Stake
from ..model.values import FrozenMap, Unknown
from .narrative import count as _count
from .narrative import narrative_kind, role
from .text import (
    attribute_label as _attr,
)
from .text import (
    attribute_text as _text,
)
from .text import (
    contextual,
    list_changed,
    plain,
    render_event_value,
)
from .text import (
    refs as _refs,
)
from .text import (
    subject_label as _subject,
)


def _presence(event: Event, domain: EntityDomain, label: str) -> str:
    ref = next((ref for ref in event.entities[1:] if ref.entity_id.domain is domain), None)
    status = (
        "is present only in the after snapshot"
        if event.attribute("side") == "after"
        else "is absent from the after snapshot"
    )
    return f"{_subject(event)} ({label} {ref.label() if ref is not None else 'null'}) {status}"


def _hab_presence(event: Event) -> str:
    text = _presence(event, EntityDomain.FACTION, "faction")
    if not isinstance(event.attribute("projected_completion"), Unknown):
        text += f"; core projected to arrive {_text(event, 'projected_arrival')}"
        text += f" and complete {_text(event, 'projected_completion')}"
    return text


def _hab_established(event: Event) -> str:
    faction = next((ref for ref in event.entities[1:] if ref.entity_id.domain is EntityDomain.FACTION), None)
    label = faction.label() if faction is not None else "null"
    return f"{_subject(event)} ({label}) became operational at {_attr(event, 'body')}"


def _first_hab_on_body(event: Event) -> str:
    count = event.attribute("hab_count")
    habs = f"{render_value(count)} hab{'' if count == 1 else 's'}"
    first = ", the first of any faction there" if event.attribute("first_of_any_faction") is True else ""
    return f"{_subject(event)} established its first presence on {_attr(event, 'body')} ({habs}{first})"


def _hab_destroyed(event: Event) -> str:
    where = f"(type {_attr(event, 'hab_type')} at {_attr(event, 'body')})"
    if event.attribute("ambiguous") is True:
        destroyers = event.attribute("destroyers")
        names = (
            ", ".join(render_event_value(ref) for ref in destroyers)
            if isinstance(destroyers, tuple)
            else render_event_value(destroyers)
        )
        return (
            f"{_subject(event)} {where} was destroyed by {names}: one of "
            f"{_attr(event, 'candidates')} recorded destructions for {_attr(event, 'vanished')} vanished habs"
        )
    return f"{_subject(event)} {where} was destroyed by {_attr(event, 'destroyer')} on {_text(event, 'recorded_on')}"


def _battle_outcome(event: Event) -> str:
    text = f"{_subject(event)} inflicted {_attr(event, 'kill_count')} kills on {_attr(event, 'victim')}"
    losses = [
        f"{render_value(count)} {label}{'' if count == 1 else 's'}"
        for name, label in (("habs_lost", "hab"), ("fleets_lost", "fleet"))
        if (count := event.attribute(name))
    ]
    if losses:
        text += f", which lost {' and '.join(losses)}"
    won, lost = event.attribute("combats_won"), event.attribute("combats_lost")
    if won or lost:
        text += f"; recorded combats won {render_value(won)}, lost {render_value(lost)}"
    return text


def _destruction_recorded(event: Event) -> str:
    named = f" (hab {_attr(event, 'hab')})" if any(name == "hab" for name, _ in event.attributes) else ""
    return (
        f"{_subject(event)} records a hab destruction dated {_text(event, 'recorded_on')}: "
        f"type {_attr(event, 'hab_type')}{named} at {_attr(event, 'space_body')} by {_attr(event, 'destroyer')}"
    )


def _combat_sides(event: Event) -> str:
    sides = event.attribute("sides")
    if not isinstance(sides, tuple):
        return render_event_value(sides)
    parts: list[str] = []
    for side in sides:
        if not (isinstance(side, tuple) and len(side) == 2 and isinstance(side[1], FrozenMap)):
            parts.append(render_event_value(side))
            continue
        ships = sum(count for _, count in side[1].items if isinstance(count, int))
        parts.append(f"{render_event_value(side[0])} ({ships} {'ship' if ships == 1 else 'ships'})")
    return " vs ".join(parts) if parts else "no sides"


def _combat_line(event: Event, verb: str) -> str:
    recorded_on = event.attribute("recorded_on")
    dated = "undated" if recorded_on is None else f"dated {_text(event, 'recorded_on')}"
    return (
        f"{_subject(event)} {verb} a combat entry ({dated}): {_combat_sides(event)}; "
        f"winner {_attr(event, 'winner')}, hab faction {_attr(event, 'hab_faction')}, "
        f"attacks {_attr(event, 'attack_count')}"
    )


def _combat_recorded(event: Event) -> str:
    return _combat_line(event, "records")


def _combat_entry_removed(event: Event) -> str:
    return _combat_line(event, "no longer lists")


TRANSITION = frozenset({"transition", "before", "after"})
_LIST_OPTIONAL = frozenset({"member", "before", "after"})

FLEET_FACTION_CHANGED = EventKind(
    "fleet.faction_changed",
    plain("faction"),
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    stake=Stake.FLEET,
)
FLEET_DOCKED_LOCATION_CHANGED = EventKind(
    "fleet.docked_location_changed",
    contextual("docked location", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
)
FLEET_ORBIT_CHANGED = EventKind(
    "fleet.orbit_changed",
    contextual("orbit", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
)
FLEET_BARYCENTER_CHANGED = EventKind(
    "fleet.barycenter_changed",
    contextual("barycenter", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
)
FLEET_PARENT_CHANGED = EventKind(
    "fleet.parent_fleet_changed",
    contextual("parent fleet", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
)
FLEET_IN_COMBAT_CHANGED = EventKind(
    "fleet.in_combat_changed",
    contextual("in-combat flag", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
)
FLEET_APPEARED = EventKind(
    "fleet.appeared",
    lambda event: _presence(event, EntityDomain.FACTION, "faction"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    frozenset({"side"}),
)
FLEET_DISAPPEARED = EventKind(
    "fleet.disappeared",
    lambda event: _presence(event, EntityDomain.FACTION, "faction"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    frozenset({"side"}),
)
FACTION_FLEETS_CHANGED = EventKind(
    "faction.fleets_changed",
    list_changed,
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    frozenset({"transition"}),
    _LIST_OPTIONAL,
)
HAB_DOCKED_FLEETS_CHANGED = EventKind(
    "hab.docked_fleets_changed",
    list_changed,
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    frozenset({"transition"}),
    _LIST_OPTIONAL,
)
SHIP_FLEET_CHANGED = EventKind(
    "ship.fleet_changed", plain("fleet"), Significance.TRIVIAL, EvidenceRole.BOOKKEEPING, TRANSITION
)
SHIP_LAST_REFIT_CHANGED = EventKind(
    "ship.last_refit_date_changed",
    contextual("last refit date", EntityDomain.FLEET, "fleet "),
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
)
SHIP_APPEARED = EventKind(
    "ship.appeared",
    lambda event: _presence(event, EntityDomain.FLEET, "fleet"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    frozenset({"side"}),
    frozenset({"hull"}),
)
SHIP_DISAPPEARED = EventKind(
    "ship.disappeared",
    lambda event: _presence(event, EntityDomain.FLEET, "fleet"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    frozenset({"side"}),
    frozenset({"hull"}),
)
FLEET_SHIPS_CHANGED = EventKind(
    "fleet.ships_changed",
    list_changed,
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    frozenset({"transition"}),
    _LIST_OPTIONAL,
)

HAB_FACTION_CHANGED = EventKind(
    "hab.faction_changed",
    plain("faction"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    stake=Stake.HAB,
)
HAB_TYPE_CHANGED = EventKind(
    "hab.type_changed",
    contextual("type", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
)
HAB_TIER_CHANGED = EventKind(
    "hab.tier_changed",
    contextual("tier", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
)
HAB_IN_COMBAT_CHANGED = EventKind(
    "hab.in_combat_changed",
    contextual("in-combat flag", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
)
HAB_UNDER_ASSAULT_CHANGED = EventKind(
    "hab.under_assault_changed",
    contextual("under-assault flag", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
)
HAB_UNDER_BOMBARDMENT_CHANGED = EventKind(
    "hab.under_bombardment_changed",
    contextual("under-bombardment flag", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
)
HAB_CORE_COMPLETED_CHANGED = EventKind(
    "hab.core_completed_changed",
    contextual("core-completed flag", EntityDomain.FACTION),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
)
HAB_APPEARED = EventKind(
    "hab.appeared",
    _hab_presence,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    frozenset({"side"}),
    frozenset({"core_completed", "projected_arrival", "projected_completion"}),
    stake=Stake.HAB,
)
HAB_DISAPPEARED = EventKind(
    "hab.disappeared",
    lambda event: _presence(event, EntityDomain.FACTION, "faction"),
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
    frozenset({"side"}),
)
FACTION_HAB_DESTRUCTION_RECORDED = EventKind(
    "faction.hab_destruction_recorded",
    _destruction_recorded,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    frozenset({"hab_type", "space_body", "destroyer", "recorded_on"}),
    frozenset({"hab", "owner"}),
)
FACTION_COMBAT_RECORDED = EventKind(
    "faction.combat_recorded",
    _combat_recorded,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    frozenset({"sides", "winner", "hab_faction", "attack_count", "surprising", "recorded_on"}),
    stake=Stake.COMBAT,
)
FACTION_COMBAT_ENTRY_REMOVED = EventKind(
    "faction.combat_entry_removed",
    _combat_entry_removed,
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    frozenset({"sides", "winner", "hab_faction", "attack_count", "surprising", "recorded_on"}),
)

HAB_ESTABLISHED = EventKind(
    "hab.established", _hab_established, Significance.MAJOR, EvidenceRole.EVIDENCE, frozenset({"faction", "body"})
)
FACTION_FIRST_HAB_ON_BODY = EventKind(
    "faction.first_hab_on_body",
    _first_hab_on_body,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    frozenset({"body", "habs", "hab_count", "first_of_any_faction", "milestones"}),
    stake=Stake.HAB,
)
HAB_DESTROYED = EventKind(
    "hab.destroyed",
    _hab_destroyed,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    frozenset({"hab_type", "body", "signals", "ambiguous"}),
    frozenset({"destroyer", "recorded_on", "destroyers", "recorded_dates", "candidates", "vanished"}),
    stake=Stake.HAB,
)
# TODO(#303): not scaled until the attribution problems of combat and destruction records are settled.
FACTION_BATTLE_OUTCOME = EventKind(
    "faction.battle_outcome",
    _battle_outcome,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    frozenset(
        {
            "victim",
            "kill_count",
            "habs_lost",
            "fleets_lost",
            "destruction_entries",
            "combats_won",
            "combats_lost",
            "battle_dates",
            "signals",
        }
    ),
)


def _space_campaign(event: Event) -> str:
    target = role(event, Role.TARGET)
    if event.attribute("victim_kind") == "alien":
        target = f"the aliens ({target})"
    text = f"{role(event, Role.ACTOR)} fought {target} over {_count(event.attribute('battles'), 'recorded outcome')}"
    losses = [
        _count(lost, label)
        for key, label in (("habs_lost", "hab"), ("fleets_lost", "fleet"))
        if (lost := event.attribute(key))
    ]
    if losses:
        text += f", which lost {' and '.join(losses)}"
    won, lost = event.attribute("combats_won"), event.attribute("combats_lost")
    if won or lost:
        text += f"; recorded combats won {render_value(won)}, lost {render_value(lost)}"
    if event.attribute("bodies"):
        text += f"; habs lost at {_refs(event, 'bodies')}"
    return text


def _colonisation_wave(event: Event) -> str:
    return (
        f"{role(event, Role.ACTOR)} reached {_refs(event, 'bodies')} in quick succession "
        f"({_count(event.attribute('hab_count'), 'hab')})"
    )


def _fleet_buildup(event: Event) -> str:
    return (
        f"{role(event, Role.ACTOR)} put {_count(event.attribute('count'), 'ship')} of hull "
        f"{_text(event, 'hull')} into service"
    )


SPACE_CAMPAIGN = narrative_kind(
    "faction.space_campaign",
    _space_campaign,
    required=frozenset(
        {
            "victim_kind",
            "battles",
            "habs_lost",
            "fleets_lost",
            "combats_won",
            "combats_lost",
            "bodies",
            "span_from",
            "span_to",
        }
    ),
    # The campaign of the opposite pair telling the same combats.
    optional=frozenset({"mirror"}),
    base=Significance.MAJOR,
)
COLONISATION_WAVE = narrative_kind(
    "faction.colonisation_wave",
    _colonisation_wave,
    required=frozenset({"bodies", "hab_count", "first_of_any_faction"}),
    base=Significance.MAJOR,
    stake=Stake.COLONY,
)
FLEET_BUILDUP = narrative_kind(
    "faction.fleet_buildup",
    _fleet_buildup,
    required=frozenset({"hull", "count"}),
    base=Significance.MINOR,
    stake=Stake.NEW_SHIPS,
)

KINDS = (
    FLEET_FACTION_CHANGED,
    FLEET_DOCKED_LOCATION_CHANGED,
    FLEET_ORBIT_CHANGED,
    FLEET_BARYCENTER_CHANGED,
    FLEET_PARENT_CHANGED,
    FLEET_IN_COMBAT_CHANGED,
    FLEET_APPEARED,
    FLEET_DISAPPEARED,
    FACTION_FLEETS_CHANGED,
    HAB_DOCKED_FLEETS_CHANGED,
    SHIP_FLEET_CHANGED,
    SHIP_LAST_REFIT_CHANGED,
    SHIP_APPEARED,
    SHIP_DISAPPEARED,
    FLEET_SHIPS_CHANGED,
    HAB_FACTION_CHANGED,
    HAB_TYPE_CHANGED,
    HAB_TIER_CHANGED,
    HAB_IN_COMBAT_CHANGED,
    HAB_UNDER_ASSAULT_CHANGED,
    HAB_UNDER_BOMBARDMENT_CHANGED,
    HAB_CORE_COMPLETED_CHANGED,
    HAB_APPEARED,
    HAB_DISAPPEARED,
    FACTION_HAB_DESTRUCTION_RECORDED,
    FACTION_COMBAT_RECORDED,
    FACTION_COMBAT_ENTRY_REMOVED,
    HAB_ESTABLISHED,
    FACTION_FIRST_HAB_ON_BODY,
    HAB_DESTROYED,
    FACTION_BATTLE_OUTCOME,
    SPACE_CAMPAIGN,
    COLONISATION_WAVE,
    FLEET_BUILDUP,
)
