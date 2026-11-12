"""One-line, conservative text for an :class:`Event`: the message catalog renderers reuse.

A line states the literal transition and names entities as ``Name (domain:id)``; it never names a cause, and
literal save strings carried as attributes are not echoed. Exceptions: a rename quotes both names (the name is the
fact), a ``notification.*`` line quotes the game's log template identifier (the game's own statement, so evidence),
and inferred or narrative types name their reading, since that is the claim the event makes and the renderer marks
its status.
"""

from __future__ import annotations

from collections.abc import Callable

from ..diff.render import render_value
from ..model.entities import EntityDomain, EntityRef
from ..model.events import Event, Role
from ..model.values import FrozenMap, Observed, Unknown
from .registry import KINDS, kind_for
from .text import attribute_label as _attr
from .text import attribute_text as _text
from .text import bands as _bands
from .text import entity as _entity
from .text import list_changed as _list_changed
from .text import name as _name
from .text import plain as _plain
from .text import presence as _presence
from .text import refs as _refs
from .text import region_count as _region_count
from .text import regions as _regions
from .text import render_event_value
from .text import subject_label as _subject
from .text import transition_label as _transition

NOTIFICATION_PREFIX = "notification."
"""The types whose names come from the game's log templates."""


def describe_event(event: Event) -> str:
    """Deterministic ASCII text; an event type without a template falls back to the type and its entities.

    The kind's template, else the type's entry in the table not yet migrated to kinds. ``notification.<template>``
    types share one template, since the log template set is open-ended.
    """
    kind = kind_for(event.event_type)
    template = kind.template if kind is not None else _TEMPLATES.get(event.event_type)
    if template is None:
        entities = ", ".join(ref.label() for ref in event.entities)
        return _ascii(f"{event.event_type}: {entities}")
    return _ascii(template(event))


def known_event_types() -> frozenset[str]:
    """Every type a kind declares or the table not yet migrated to kinds describes; ``notification.*`` excluded."""
    return frozenset(event_type for event_type, kind in KINDS.items() if not kind.is_prefix) | frozenset(_TEMPLATES)


def _ascii(text: str) -> str:
    if text.isascii():
        return text
    return "".join(char if char.isascii() else f"\\u{ord(char):04x}" for char in text)


def _controller_changed(event: Event) -> str:
    text = f"{_subject(event)} ({_name(_entity(event, EntityDomain.NATION))}) {_transition(event, 'controller')}"
    recorded = event.attribute("loss_recorded_on")
    if not isinstance(recorded, Unknown):
        text += f"; loss recorded by {_attr(event, 'before')} on {_text(event, 'loss_recorded_on')}"
    return text


def _control_point_presence(event: Event) -> str:
    nation = _name(_entity(event, EntityDomain.NATION))
    faction = _name(_entity(event, EntityDomain.FACTION))
    return f"{_subject(event)} ({nation}, controller {faction}) {_presence(event)}"


def _loss_recorded(event: Event) -> str:
    faction = _name(_entity(event, EntityDomain.FACTION))
    text = f"{faction} records {_subject(event)} as lost on {_text(event, 'recorded_on')}"
    if not isinstance(event.attribute("previous_recorded_on"), Unknown):
        text += f" (previously {_text(event, 'previous_recorded_on')})"
    return text


def _relation_changed(event: Event) -> str:
    pair = " and ".join(ref.label() for ref in event.entities)
    listing = (
        "listed by both" if event.attribute("reciprocal") is True else f"listed by {_attr(event, 'listed_by')} only"
    )
    return f"{pair}: {_text(event, 'relation')} entry {_text(event, 'transition')} ({listing})"


def _executive_change(event: Event) -> str:
    text = (
        f"{_subject(event)} records an executive change dated {_text(event, 'recorded_on')}: "
        f"new executive {_attr(event, 'new_executive')}"
    )
    previous = event.attribute("previous_executive")
    if not isinstance(previous, Unknown):
        text += f" (previously {render_event_value(previous)})"
    return text


def _claims_changed(label: str) -> Callable[[Event], str]:
    """``<nation> <label> list: +[regions] -[regions]``, an empty side left out; an unresolved list as a transition."""

    def describe(event: Event) -> str:
        if not isinstance(event.attribute("transition"), Unknown):
            return f"{_subject(event)} {_transition(event, f'{label} list')}"
        parts = [
            f"{sign}{_attr(event, name)}" for sign, name in (("+", "added"), ("-", "removed")) if event.attribute(name)
        ]
        return f"{_subject(event)} {label} list: {' '.join(parts)}"

    return describe


def _renamed(event: Event) -> str:
    text = f"{_subject(event)} renamed: {_attr(event, 'before')} -> {_attr(event, 'after')}"
    if not isinstance(event.attribute("federation_name_before"), Unknown):
        text += (
            f" (federation name {_attr(event, 'federation_name_before')} -> {_attr(event, 'federation_name_after')})"
        )
    return text


def _unrest_attempts_changed(event: Event) -> str:
    if not isinstance(event.attribute("transition"), Unknown):
        return f"{_subject(event)} {_transition(event, 'faction unrest attempts')}"
    label = f"unrest attempts by {_attr(event, 'faction')}"
    return f"{_subject(event)} {_transition(event, label)}"


def _new_government_recorded(event: Event) -> str:
    if not isinstance(event.attribute("after"), str):
        return f"{_subject(event)} {_transition(event, 'new government date')}"
    text = f"{_subject(event)} records a new government dated {_text(event, 'after')}"
    if isinstance(event.attribute("before"), str):
        text += f" (previously {_text(event, 'before')})"
    return text


def _councilor_field(label: str) -> Callable[[Event], str]:
    def describe(event: Event) -> str:
        return f"{_subject(event)} ({_name(_entity(event, EntityDomain.FACTION))}) {_transition(event, label)}"

    return describe


def _councilor_presence(event: Event) -> str:
    return f"{_subject(event)} (faction {_name(_entity(event, EntityDomain.FACTION))}) {_presence(event)}"


def _side_list(event: Event) -> str:
    nations = ", ".join(ref.label() for ref in event.entities[1:] if ref.entity_id.domain is EntityDomain.NATION)
    return nations or "no nations"


def _war_presence(event: Event) -> str:
    text = f"{_subject(event)} ({_side_list(event)}) {_presence(event)}"
    if not isinstance(event.attribute("started_on"), Unknown):
        text += f"; start date {_text(event, 'started_on')}"
    return text


def _alliance_changed(event: Event) -> str:
    sign = "+" if event.attribute("transition") == "added" else "-"
    return f"{_subject(event)} {_text(event, 'side')} side: {sign}{_attr(event, 'member')}"


def _members_changed(event: Event) -> str:
    if event.attribute("transition") == "unresolved":
        return _list_changed(event)
    sign = "+" if event.attribute("transition") == "added" else "-"
    return f"{_subject(event)} members: {sign}{_attr(event, 'member')}"


def _federation_presence(event: Event) -> str:
    return f"{_subject(event)} (members {_side_list(event)}) {_presence(event)}"


def _nation_control_changed(event: Event) -> str:
    return f"{_subject(event)} {_transition(event, _text(event, 'scope') + ' control changed')}"


def _hab_presence(event: Event) -> str:
    text = _presence_with(EntityDomain.FACTION, "faction")(event)
    if not isinstance(event.attribute("projected_completion"), Unknown):
        text += f"; core projected to arrive {_text(event, 'projected_arrival')}"
        text += f" and complete {_text(event, 'projected_completion')}"
    return text


def _hab_established(event: Event) -> str:
    faction = _name(_entity(event, EntityDomain.FACTION))
    return f"{_subject(event)} ({faction}) became operational at {_attr(event, 'body')}"


def _first_hab_on_body(event: Event) -> str:
    count = event.attribute("hab_count")
    habs = f"{render_value(count)} hab{'' if count == 1 else 's'}"
    first = ", the first of any faction there" if event.attribute("first_of_any_faction") is True else ""
    return f"{_subject(event)} established its first presence on {_attr(event, 'body')} ({habs}{first})"


def _hab_destroyed(event: Event) -> str:
    where = f"(type {_attr(event, 'hab_type')} at {_attr(event, 'body')})"
    if event.attribute("ambiguous") is True:
        return (
            f"{_subject(event)} {where} was destroyed by {_refs(event, 'destroyers')}: one of "
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


def _presence_with(domain: EntityDomain, prefix: str) -> Callable[[Event], str]:
    return lambda event: f"{_subject(event)} ({prefix} {_name(_entity(event, domain))}) {_presence(event)}"


def _destruction_recorded(event: Event) -> str:
    named = f" (hab {_attr(event, 'hab')})" if any(name == "hab" for name, _ in event.attributes) else ""
    return (
        f"{_subject(event)} records a hab destruction dated {_text(event, 'recorded_on')}: "
        f"type {_attr(event, 'hab_type')}{named} at {_attr(event, 'space_body')} by {_attr(event, 'destroyer')}"
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


def _role(event: Event, role: Role) -> str:
    refs = [ref.label() for found, ref in event.roles if found is role]
    return ", ".join(refs) if refs else "null"


def _takeover(event: Event) -> str:
    text = f"{_role(event, Role.ACTOR)} took control of {_role(event, Role.TARGET)}"
    if any(role is Role.LOSER for role, _ in event.roles):
        text += f" from {_role(event, Role.LOSER)}"
    if event.attribute("consolidated") is True:
        text += " and holds every control point"
    return text


def _takeover_wave(event: Event) -> str:
    return (
        f"{_role(event, Role.ACTOR)} took control of {_refs(event, 'nations')} in quick succession "
        f"({_count(event.attribute('count'), 'takeover')})"
    )


def _band_shift(event: Event) -> str:
    return f"{_role(event, Role.ACTOR)} {_bands(event)}"


def _population_collapse(event: Event) -> str:
    return f"{_role(event, Role.ACTOR)} population collapse: {_attr(event, 'before')} -> {_attr(event, 'residual')}"


def _economic_trajectory(event: Event) -> str:
    return (
        f"{_role(event, Role.ACTOR)} per-capita GDP {_text(event, 'direction')}: "
        f"{_attr(event, 'first_value')} -> {_attr(event, 'last_value')}"
    )


def _nuclear_arsenal(event: Event, change: str) -> str:
    return f"{_role(event, Role.ACTOR)} {change}: {_attr(event, 'before')} -> {_attr(event, 'after')} nuclear weapons"


def _diplomatic_realignment(event: Event) -> str:
    def count(name: str) -> int:
        value = event.attribute(name)
        return len(value) if isinstance(value, tuple) else 0

    text = (
        f"{_role(event, Role.ACTOR)} realigned its diplomacy with {_attr(event, 'partner_count')} partners: "
        f"allies +{count('allies_gained')}/-{count('allies_lost')}, "
        f"rivals +{count('rivals_gained')}/-{count('rivals_lost')}"
    )
    if count("reversed_partners"):
        text += f"; reversed with {_attr(event, 'reversed_partners')}"
    if event.attribute("executive") is not None:
        text += f"; executive {_attr(event, 'executive')}"
    return text


def _nuclear_armament(event: Event) -> str:
    return _nuclear_arsenal(event, "armed with nuclear weapons")


def _nuclear_buildup(event: Event) -> str:
    return _nuclear_arsenal(event, "built up its nuclear arsenal")


def _nuclear_disarmament(event: Event) -> str:
    return _nuclear_arsenal(event, "dismantled its nuclear arsenal")


def _army_count(event: Event, change: str) -> str:
    return (
        f"{_role(event, Role.ACTOR)} {change} its standard armies: {_attr(event, 'before')} -> {_attr(event, 'after')}"
    )


def _military_buildup(event: Event) -> str:
    return _army_count(event, "built up")


def _demobilization(event: Event) -> str:
    return _army_count(event, "demobilized")


def _navy_established(event: Event) -> str:
    return f"{_role(event, Role.ACTOR)} established a navy ({_count(event.attribute('navies'), 'naval army')})"


def _space_program_growth(event: Event) -> str:
    return (
        f"{_role(event, Role.ACTOR)} space program grew: boost {_attr(event, 'boost_before')} -> "
        f"{_attr(event, 'boost_after')}, mission control {_attr(event, 'mission_control_before')} -> "
        f"{_attr(event, 'mission_control_after')}"
    )


def _space_defences_established(event: Event) -> str:
    return f"{_role(event, Role.ACTOR)} established space defences ({_region_count(event.attribute('regions'))})"


def _ranking_changed(event: Event) -> str:
    text = f"Top {_attr(event, 'top')} by {_text(event, 'metric')} changed"
    if any(role is Role.BENEFICIARY for role, _ in event.roles):
        text += f": entered {_role(event, Role.BENEFICIARY)}"
    if any(role is Role.LOSER for role, _ in event.roles):
        text += f"; left {_role(event, Role.LOSER)}"
    return text


def _war_arc(event: Event) -> str:
    text = f"{_attr(event, 'war')} between {_role(event, Role.ACTOR)} and {_role(event, Role.TARGET)}"
    regions = event.attribute("regions_transferred")
    if isinstance(regions, tuple) and regions:
        text += f"; {_region_count(len(regions))} changed hands between the sides"
    return text


def _federation_lifecycle(event: Event) -> str:
    changes = event.attribute("member_changes")
    count = len(changes) if isinstance(changes, tuple) else 0
    return (
        f"{_role(event, Role.ACTOR)} members {_attr(event, 'members_initial')} -> {_attr(event, 'members_final')} "
        f"({count} member change{'' if count == 1 else 's'})"
    )


def _expansion(event: Event) -> str:
    regions = _regions(event)
    text = f"{_role(event, Role.ACTOR)} expanded over {_role(event, Role.TARGET)}: {regions}"
    mode = event.attribute("mode")
    return f"{text} ({mode})" if isinstance(mode, str) else text


def _cession(event: Event) -> str:
    return f"{_role(event, Role.ACTOR)} ceded {_regions(event)} to {_role(event, Role.BENEFICIARY)}"


def _merger(event: Event) -> str:
    text = f"{_role(event, Role.ACTOR)} absorbed {_role(event, Role.TARGET)} by unification"
    faction = event.attribute("unifying_faction")
    return f"{text} under {_name(faction)}" if isinstance(faction, EntityRef) else text


def _release(event: Event) -> str:
    if any(role is Role.ACTOR for role, _ in event.roles):
        return f"{_role(event, Role.ACTOR)} released {_role(event, Role.BENEFICIARY)}"
    return f"{_role(event, Role.BENEFICIARY)} was released by one of {_refs(event, 'parents')}"


def _breakaway(event: Event) -> str:
    return f"{_role(event, Role.ACTOR)} broke away from {_role(event, Role.TARGET)}"


def _claims_declared(event: Event) -> str:
    return f"{_role(event, Role.ACTOR)} claimed regions of {_role(event, Role.TARGET)}"


def _count(value: Observed, noun: str) -> str:
    return f"{render_value(value)} {noun}{'' if value == 1 else 's'}"


def _space_campaign(event: Event) -> str:
    kind = event.attribute("victim_kind")
    target = f"the aliens ({_role(event, Role.TARGET)})" if kind == "alien" else _role(event, Role.TARGET)
    text = f"{_role(event, Role.ACTOR)} fought {target} over {_count(event.attribute('battles'), 'recorded outcome')}"
    losses = [
        _count(count, label)
        for name, label in (("habs_lost", "hab"), ("fleets_lost", "fleet"))
        if (count := event.attribute(name))
    ]
    if losses:
        text += f", which lost {' and '.join(losses)}"
    won, lost = event.attribute("combats_won"), event.attribute("combats_lost")
    if won or lost:
        text += f"; recorded combats won {render_value(won)}, lost {render_value(lost)}"
    bodies = _refs(event, "bodies")
    if event.attribute("bodies"):
        text += f"; habs lost at {bodies}"
    return text


def _colonisation_wave(event: Event) -> str:
    return (
        f"{_role(event, Role.ACTOR)} reached {_refs(event, 'bodies')} in quick succession "
        f"({_count(event.attribute('hab_count'), 'hab')})"
    )


def _first_milestone(event: Event) -> str:
    return f"{_role(event, Role.ACTOR)} recorded the campaign milestone {_text(event, 'milestone')}"


def _fleet_buildup(event: Event) -> str:
    return (
        f"{_role(event, Role.ACTOR)} put {_count(event.attribute('count'), 'ship')} of hull "
        f"{_text(event, 'hull')} into service"
    )


def _technology_milestone(event: Event) -> str:
    who = f"{_role(event, Role.ACTOR)} completed" if any(r is Role.ACTOR for r, _ in event.roles) else "Completed"
    return f"{who} {_text(event, 'template')}: {_text(event, 'rationale')}"


_TEMPLATES: dict[str, Callable[[Event], str]] = {
    # The types not yet migrated to a kind.
    "nation.federation_changed": _plain("federation"),
    "nation.wars_changed": _list_changed,
    "war.appeared": _war_presence,
    "war.disappeared": _war_presence,
    "war.alliance_changed": _alliance_changed,
    "war.attacker_changed": _plain("attacker"),
    "war.defender_changed": _plain("defender"),
    "war.last_fighting_changed": _plain("date of last fighting"),
    "war.attacking_alliance_changed": _list_changed,
    "war.defending_alliance_changed": _list_changed,
    "federation.appeared": _federation_presence,
    "federation.disappeared": _federation_presence,
    "federation.members_changed": _members_changed,
    "federation.renamed": _renamed,
    "faction.takeover": _takeover,
    "faction.takeover_wave": _takeover_wave,
    "war.arc": _war_arc,
    "federation.lifecycle": _federation_lifecycle,
    "nation.expansion": _expansion,
    "nation.cession": _cession,
    "nation.merger": _merger,
    "nation.release": _release,
    "nation.breakaway": _breakaway,
    "nation.claims_declared": _claims_declared,
    "nation.unrest_shift": _band_shift,
    "nation.government_shift": _band_shift,
    "nation.education_shift": _band_shift,
    "nation.cohesion_shift": _band_shift,
    "nation.inequality_shift": _band_shift,
    "nation.miltech_shift": _band_shift,
    "nation.population_collapse": _population_collapse,
    "nation.economic_trajectory": _economic_trajectory,
    "nation.diplomatic_realignment": _diplomatic_realignment,
    "nation.nuclear_armament": _nuclear_armament,
    "nation.nuclear_buildup": _nuclear_buildup,
    "nation.nuclear_disarmament": _nuclear_disarmament,
    "nation.military_buildup": _military_buildup,
    "nation.demobilization": _demobilization,
    "nation.navy_established": _navy_established,
    "nation.space_program_growth": _space_program_growth,
    "nation.space_defences_established": _space_defences_established,
    "world.ranking_changed": _ranking_changed,
    "faction.space_campaign": _space_campaign,
    "faction.colonisation_wave": _colonisation_wave,
    "campaign.first_milestone": _first_milestone,
    "faction.fleet_buildup": _fleet_buildup,
    "technology.milestone": _technology_milestone,
}
