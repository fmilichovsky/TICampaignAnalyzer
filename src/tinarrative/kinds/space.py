"""Fleets, ships, habs and the space battle log: literal transitions, presence and the faction's records."""

from __future__ import annotations

from ..diff.render import render_value
from ..model.entities import EntityDomain
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole
from ..model.values import FrozenMap, Unknown
from .text import (
    TRANSITION,
    attribute_label,
    attribute_text,
    count_label,
    entity,
    list_changed,
    name,
    plain,
    presence_with,
    refs,
    render_event_value,
    role_label,
    subject_label,
    with_context,
)

FACTION = EntityDomain.FACTION
FLEET = EntityDomain.FLEET
PRESENCE = frozenset({"side"})
LIST = frozenset({"transition"})
LIST_OPTIONAL = frozenset({"member", "before", "after"})
"""A list event carries a member, or, for a list unresolved on one side, the literal transition."""
BOOKKEEPING = EvidenceRole.BOOKKEEPING


def _hab_presence(event: Event) -> str:
    text = presence_with(FACTION, "faction")(event)
    if not isinstance(event.attribute("projected_completion"), Unknown):
        text += f"; core projected to arrive {attribute_text(event, 'projected_arrival')}"
        text += f" and complete {attribute_text(event, 'projected_completion')}"
    return text


def _destruction_recorded(event: Event) -> str:
    named = f" (hab {attribute_label(event, 'hab')})" if any(name == "hab" for name, _ in event.attributes) else ""
    return (
        f"{subject_label(event)} records a hab destruction dated {attribute_text(event, 'recorded_on')}: "
        f"type {attribute_label(event, 'hab_type')}{named} at {attribute_label(event, 'space_body')} "
        f"by {attribute_label(event, 'destroyer')}"
    )


def _combat_sides(event: Event) -> str:
    """``A (faction:15) (3 ships) vs B (faction:16) (2 ships)``; the unknown value when the sides are.

    Hull class names stay in the ``sides`` attribute: they are game identifiers such as ``Battleship``, which
    would read as a claim the line does not make.
    """
    sides = event.attribute("sides")
    if not isinstance(sides, tuple):
        return render_value(sides)
    parts: list[str] = []
    for side in sides:
        if not (isinstance(side, tuple) and len(side) == 2 and isinstance(side[1], FrozenMap)):
            parts.append(render_value(side))
            continue
        ships = sum(count for _, count in side[1].items if isinstance(count, int))
        parts.append(f"{render_event_value(side[0])} ({ships} {'ship' if ships == 1 else 'ships'})")
    return " vs ".join(parts) if parts else "no sides"


def _combat_line(event: Event, verb: str) -> str:
    recorded_on = event.attribute("recorded_on")
    dated = "undated" if recorded_on is None else f"dated {attribute_text(event, 'recorded_on')}"
    return (
        f"{subject_label(event)} {verb} a combat entry ({dated}): {_combat_sides(event)}; "
        f"winner {attribute_label(event, 'winner')}, hab faction {attribute_label(event, 'hab_faction')}, "
        f"attacks {attribute_label(event, 'attack_count')}"
    )


def _combat_recorded(event: Event) -> str:
    return _combat_line(event, "records")


def _combat_entry_removed(event: Event) -> str:
    return _combat_line(event, "no longer lists")


def _hab_established(event: Event) -> str:
    faction = name(entity(event, EntityDomain.FACTION))
    return f"{subject_label(event)} ({faction}) became operational at {attribute_label(event, 'body')}"


def _first_hab_on_body(event: Event) -> str:
    count = event.attribute("hab_count")
    habs = f"{render_value(count)} hab{'' if count == 1 else 's'}"
    first = ", the first of any faction there" if event.attribute("first_of_any_faction") is True else ""
    return f"{subject_label(event)} established its first presence on {attribute_label(event, 'body')} ({habs}{first})"


def _hab_destroyed(event: Event) -> str:
    where = f"(type {attribute_label(event, 'hab_type')} at {attribute_label(event, 'body')})"
    if event.attribute("ambiguous") is True:
        return (
            f"{subject_label(event)} {where} was destroyed by {refs(event, 'destroyers')}: one of "
            f"{attribute_label(event, 'candidates')} recorded destructions for "
            f"{attribute_label(event, 'vanished')} vanished habs"
        )
    return (
        f"{subject_label(event)} {where} was destroyed by {attribute_label(event, 'destroyer')} "
        f"on {attribute_text(event, 'recorded_on')}"
    )


def _battle_outcome(event: Event) -> str:
    kills = attribute_label(event, "kill_count")
    text = f"{subject_label(event)} inflicted {kills} kills on {attribute_label(event, 'victim')}"
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


# --- Fleets ----------------------------------------------------------------------------------------------

FLEET_FACTION_CHANGED = EventKind(
    "fleet.faction_changed", plain("faction"), Significance.MAJOR, BOOKKEEPING, required=TRANSITION
)
FLEET_DOCKED_LOCATION_CHANGED = EventKind(
    "fleet.docked_location_changed",
    with_context("docked location", FACTION),
    Significance.MINOR,
    BOOKKEEPING,
    required=TRANSITION,
)
FLEET_ORBIT_CHANGED = EventKind(
    "fleet.orbit_changed", with_context("orbit", FACTION), Significance.MINOR, BOOKKEEPING, required=TRANSITION
)
FLEET_BARYCENTER_CHANGED = EventKind(
    "fleet.barycenter_changed",
    with_context("barycenter", FACTION),
    Significance.MINOR,
    BOOKKEEPING,
    required=TRANSITION,
)
FLEET_PARENT_FLEET_CHANGED = EventKind(
    "fleet.parent_fleet_changed",
    with_context("parent fleet", FACTION),
    Significance.MINOR,
    BOOKKEEPING,
    required=TRANSITION,
)
FLEET_IN_COMBAT_CHANGED = EventKind(
    "fleet.in_combat_changed",
    with_context("in-combat flag", FACTION),
    Significance.MINOR,
    BOOKKEEPING,
    required=TRANSITION,
)
FLEET_APPEARED = EventKind(
    "fleet.appeared", presence_with(FACTION, "faction"), Significance.MINOR, BOOKKEEPING, required=PRESENCE
)
FLEET_DISAPPEARED = EventKind(
    "fleet.disappeared", presence_with(FACTION, "faction"), Significance.MINOR, BOOKKEEPING, required=PRESENCE
)
FACTION_FLEETS_CHANGED = EventKind(
    "faction.fleets_changed",
    list_changed,
    Significance.TRIVIAL,
    BOOKKEEPING,
    required=LIST,
    optional=LIST_OPTIONAL,
)
HAB_DOCKED_FLEETS_CHANGED = EventKind(
    "hab.docked_fleets_changed",
    list_changed,
    Significance.TRIVIAL,
    BOOKKEEPING,
    required=LIST,
    optional=LIST_OPTIONAL,
)

# --- Ships -----------------------------------------------------------------------------------------------

SHIP_FLEET_CHANGED = EventKind(
    "ship.fleet_changed", plain("fleet"), Significance.TRIVIAL, BOOKKEEPING, required=TRANSITION
)
SHIP_LAST_REFIT_DATE_CHANGED = EventKind(
    "ship.last_refit_date_changed",
    with_context("last refit date", FLEET, "fleet "),
    Significance.TRIVIAL,
    BOOKKEEPING,
    required=TRANSITION,
)
SHIP_APPEARED = EventKind(
    "ship.appeared",
    presence_with(FLEET, "fleet"),
    Significance.MINOR,
    BOOKKEEPING,
    required=PRESENCE,
    optional=frozenset({"hull"}),
)
SHIP_DISAPPEARED = EventKind(
    "ship.disappeared",
    presence_with(FLEET, "fleet"),
    Significance.MINOR,
    BOOKKEEPING,
    required=PRESENCE,
    optional=frozenset({"hull"}),
)
FLEET_SHIPS_CHANGED = EventKind(
    "fleet.ships_changed",
    list_changed,
    Significance.TRIVIAL,
    BOOKKEEPING,
    required=LIST,
    optional=LIST_OPTIONAL,
)

# --- Habs ------------------------------------------------------------------------------------------------

HAB_FACTION_CHANGED = EventKind(
    "hab.faction_changed", plain("faction"), Significance.MAJOR, BOOKKEEPING, required=TRANSITION
)
HAB_TYPE_CHANGED = EventKind(
    "hab.type_changed", with_context("type", FACTION), Significance.MINOR, BOOKKEEPING, required=TRANSITION
)
HAB_TIER_CHANGED = EventKind(
    "hab.tier_changed", with_context("tier", FACTION), Significance.MINOR, BOOKKEEPING, required=TRANSITION
)
HAB_IN_COMBAT_CHANGED = EventKind(
    "hab.in_combat_changed",
    with_context("in-combat flag", FACTION),
    Significance.MINOR,
    BOOKKEEPING,
    required=TRANSITION,
)
HAB_UNDER_ASSAULT_CHANGED = EventKind(
    "hab.under_assault_changed",
    with_context("under-assault flag", FACTION),
    Significance.MINOR,
    BOOKKEEPING,
    required=TRANSITION,
)
HAB_UNDER_BOMBARDMENT_CHANGED = EventKind(
    "hab.under_bombardment_changed",
    with_context("under-bombardment flag", FACTION),
    Significance.MINOR,
    BOOKKEEPING,
    required=TRANSITION,
)
HAB_CORE_COMPLETED_CHANGED = EventKind(
    "hab.core_completed_changed",
    with_context("core-completed flag", FACTION),
    Significance.MINOR,
    BOOKKEEPING,
    required=TRANSITION,
)
# A hab appears at launch; it is founded when its core completes (``hab.established``).
HAB_APPEARED = EventKind(
    "hab.appeared",
    _hab_presence,
    Significance.MINOR,
    BOOKKEEPING,
    required=PRESENCE,
    optional=frozenset({"core_completed", "projected_arrival", "projected_completion"}),
)
HAB_DISAPPEARED = EventKind(
    "hab.disappeared", presence_with(FACTION, "faction"), Significance.MAJOR, BOOKKEEPING, required=PRESENCE
)
HAB_DESTRUCTION_RECORDED = EventKind(
    "faction.hab_destruction_recorded",
    _destruction_recorded,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"hab_type", "space_body", "destroyer", "recorded_on"}),
    optional=frozenset({"hab", "owner"}),
)

# --- Combat log ------------------------------------------------------------------------------------------

COMBAT_ENTRY = frozenset({"sides", "winner", "hab_faction", "attack_count", "surprising", "recorded_on"})
COMBAT_RECORDED = EventKind(
    "faction.combat_recorded", _combat_recorded, Significance.MAJOR, EvidenceRole.EVIDENCE, required=COMBAT_ENTRY
)
COMBAT_ENTRY_REMOVED = EventKind(
    "faction.combat_entry_removed", _combat_entry_removed, Significance.TRIVIAL, BOOKKEEPING, required=COMBAT_ENTRY
)

# --- Inferred readings ---------------------------------------------------------------------------------------

HAB_ESTABLISHED = EventKind(
    "hab.established",
    _hab_established,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"faction", "body"}),
)
FIRST_HAB_ON_BODY = EventKind(
    "faction.first_hab_on_body",
    _first_hab_on_body,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"body", "habs", "hab_count", "first_of_any_faction", "milestones"}),
)
HAB_DESTROYED = EventKind(
    "hab.destroyed",
    _hab_destroyed,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"hab_type", "body", "signals", "ambiguous"}),
    optional=frozenset({"destroyer", "recorded_on", "destroyers", "recorded_dates", "candidates", "vanished"}),
)
BATTLE_OUTCOME = EventKind(
    "faction.battle_outcome",
    _battle_outcome,
    Significance.MAJOR,
    EvidenceRole.EVIDENCE,
    required=frozenset(
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

KINDS = (
    FLEET_FACTION_CHANGED,
    FLEET_DOCKED_LOCATION_CHANGED,
    FLEET_ORBIT_CHANGED,
    FLEET_BARYCENTER_CHANGED,
    FLEET_PARENT_FLEET_CHANGED,
    FLEET_IN_COMBAT_CHANGED,
    FLEET_APPEARED,
    FLEET_DISAPPEARED,
    FACTION_FLEETS_CHANGED,
    HAB_DOCKED_FLEETS_CHANGED,
    SHIP_FLEET_CHANGED,
    SHIP_LAST_REFIT_DATE_CHANGED,
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
    HAB_DESTRUCTION_RECORDED,
    COMBAT_RECORDED,
    COMBAT_ENTRY_REMOVED,
    HAB_ESTABLISHED,
    FIRST_HAB_ON_BODY,
    HAB_DESTROYED,
    BATTLE_OUTCOME,
)


# --- Narrative events ----------------------------------------------------------------------------------------------


def _space_campaign(event: Event) -> str:
    kind = event.attribute("victim_kind")
    target = f"the aliens ({role_label(event, Role.TARGET)})" if kind == "alien" else role_label(event, Role.TARGET)
    text = (
        f"{role_label(event, Role.ACTOR)} fought {target} over "
        f"{count_label(event.attribute('battles'), 'recorded outcome')}"
    )
    losses = [
        count_label(count, label)
        for name, label in (("habs_lost", "hab"), ("fleets_lost", "fleet"))
        if (count := event.attribute(name))
    ]
    if losses:
        text += f", which lost {' and '.join(losses)}"
    won, lost = event.attribute("combats_won"), event.attribute("combats_lost")
    if won or lost:
        text += f"; recorded combats won {render_value(won)}, lost {render_value(lost)}"
    if event.attribute("bodies"):
        text += f"; habs lost at {refs(event, 'bodies')}"
    return text


def _colonisation_wave(event: Event) -> str:
    return (
        f"{role_label(event, Role.ACTOR)} reached {refs(event, 'bodies')} in quick succession "
        f"({count_label(event.attribute('hab_count'), 'hab')})"
    )


def _fleet_buildup(event: Event) -> str:
    return (
        f"{role_label(event, Role.ACTOR)} put {count_label(event.attribute('count'), 'ship')} of hull "
        f"{attribute_text(event, 'hull')} into service"
    )


SPACE_CAMPAIGN = EventKind(
    "faction.space_campaign",
    _space_campaign,
    None,
    EvidenceRole.BOOKKEEPING,
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
    optional=frozenset({"mirror"}),
)
COLONISATION_WAVE = EventKind(
    "faction.colonisation_wave",
    _colonisation_wave,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"bodies", "hab_count", "first_of_any_faction"}),
)
FLEET_BUILDUP = EventKind(
    "faction.fleet_buildup",
    _fleet_buildup,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"hull", "count"}),
)

NARRATIVE_KINDS = (SPACE_CAMPAIGN, COLONISATION_WAVE, FLEET_BUILDUP)
