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
from ..model.values import Observed
from .registry import KINDS, kind_of
from .text import attribute_label as _attr
from .text import attribute_text as _text
from .text import bands as _bands
from .text import entity_of as _entity
from .text import name_of as _name
from .text import refs as _refs
from .text import region_count as _region_count
from .text import regions as _regions
from .text import subject_label as _subject


def describe_event(event: Event) -> str:
    """Deterministic ASCII text; an event type without a template falls back to the type and its entities.

    The kind's template, else the type's entry in the table not yet migrated to kinds. ``notification.<template>``
    types share the one prefix kind, since the log template set is open-ended.
    """
    kind = kind_of(event.event_type)
    template = kind.template if kind is not None else _TEMPLATES.get(event.event_type)
    if template is None:
        entities = ", ".join(ref.label() for ref in event.entities)
        return _ascii(f"{event.event_type}: {entities}")
    return _ascii(template(event))


def known_event_types() -> frozenset[str]:
    """Every type a kind declares or the table not yet migrated to kinds describes; ``notification.*`` excluded."""
    return frozenset(event_type for event_type, kind in KINDS.items() if not kind.prefix) | frozenset(_TEMPLATES)


def _ascii(text: str) -> str:
    if text.isascii():
        return text
    return "".join(char if char.isascii() else f"\\u{ord(char):04x}" for char in text)


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
    "hab.established": _hab_established,
    "faction.first_hab_on_body": _first_hab_on_body,
    "hab.destroyed": _hab_destroyed,
    "faction.battle_outcome": _battle_outcome,
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
