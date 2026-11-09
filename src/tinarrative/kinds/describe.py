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
from ..model.values import Observed, Unknown
from .registry import KINDS, kind_of
from .text import attribute_label as _attr
from .text import attribute_text as _text
from .text import entity_of as _entity
from .text import list_changed as _list_changed
from .text import name_of as _name
from .text import plain as _plain
from .text import presence as _presence
from .text import renamed as _renamed
from .text import render_event_value
from .text import subject_label as _subject
from .text import transition_label as _transition


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


def _nation_presence(event: Event) -> str:
    return f"{_subject(event)} {_presence(event)}"


def _statistic_shifted(event: Event) -> str:
    """``<nation> <statistic>[ <key>]: before -> after``; the cause map is evidence for readers, not echoed."""
    label = _text(event, "statistic")
    if not isinstance(event.attribute("key"), Unknown):
        label += f" {_text(event, 'key')}"
    return f"{_subject(event)} {_transition(event, label)}"


def _policy_changed(event: Event) -> str:
    return f"{_subject(event)} {_transition(event, 'policy ' + _text(event, 'policy'))}"


def _band_crossed(event: Event) -> str:
    """``<nation> <statistic>: <band> -> <band> (before -> after)``; the game's own band labels."""
    return f"{_subject(event)} {_bands(event)} ({_attr(event, 'before')} -> {_attr(event, 'after')})"


def _bands(event: Event) -> str:
    return f"{_text(event, 'statistic')}: {_text(event, 'from_band')} -> {_text(event, 'to_band')}"


def _population_changed(event: Event) -> str:
    """``<nation> population <direction>: before -> after (residual <residual>)``; the residual excludes territory."""
    return (
        f"{_subject(event)} population {_text(event, 'direction')}: {_attr(event, 'before')} -> "
        f"{_attr(event, 'after')} (residual {_attr(event, 'residual')})"
    )


def _pcgdp_trend(event: Event) -> str:
    """``<nation> per-capita GDP <boom|slump> at quarter <q>: before -> after``, over the trailing window."""
    return (
        f"{_subject(event)} per-capita GDP {_text(event, 'direction')} at quarter {_attr(event, 'quarter')}: "
        f"{_attr(event, 'before')} -> {_attr(event, 'after')}"
    )


def _space_assets_changed(event: Event) -> str:
    """``<nation> <statistic> <growth|decline>: before -> after``; the territory share is evidence, not echoed."""
    return (
        f"{_subject(event)} {_text(event, 'statistic')} {_text(event, 'direction')}: "
        f"{_attr(event, 'before')} -> {_attr(event, 'after')}"
    )


def _rank_changed(event: Event) -> str:
    """``<nation> <metric> rank: before -> after``; a side without a place is ``unranked``."""

    def rank(name: str) -> str:
        return "unranked" if event.attribute(name) is None else _attr(event, name)

    return f"{_subject(event)} {_text(event, 'metric')} rank: {rank('before_rank')} -> {rank('after_rank')}"


def _refs(event: Event, name: str) -> str:
    """A tuple attribute of references as a comma-separated list of IDs."""
    value = event.attribute(name)
    if not isinstance(value, tuple):
        return render_event_value(value)
    return ", ".join(render_event_value(item) for item in value)


def _regions(event: Event) -> str:
    return _region_count(event.attribute("region_count"))


def _region_count(count: Observed) -> str:
    return f"{render_value(count)} region{'' if count == 1 else 's'}"


def _territory_gained(event: Event) -> str:
    return f"{_subject(event)} gained {_regions(event)} from {_refs(event, 'counterparts')}"


def _territory_lost(event: Event) -> str:
    return f"{_subject(event)} lost {_regions(event)} to {_refs(event, 'counterparts')}"


def _independence(event: Event) -> str:
    releaser = event.attribute("releasing_nation")
    if event.attribute("released") is True and isinstance(releaser, EntityRef):
        return f"{_subject(event)} was released by {releaser.label()}"
    return f"{_subject(event)} became independent of {_refs(event, 'parents')}"


def _unification(event: Event) -> str:
    return f"{_subject(event)} unified with {_refs(event, 'unified')}"


def _annexation(event: Event) -> str:
    return f"{_subject(event)} annexed {_regions(event)} of {_name(_entity(event, EntityDomain.NATION))}"


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
    "region.nation_changed": _plain("nation"),
    "nation.capital_changed": _plain("capital"),
    "nation.relation_changed": _relation_changed,
    "nation.breakaway_parent_changed": _plain("breakaway parent"),
    "nation.regions_changed": _list_changed,
    "nation.breakaways_changed": _list_changed,
    "nation.allies_changed": _list_changed,
    "nation.rivals_changed": _list_changed,
    "nation.executive_change_recorded": _executive_change,
    "nation.appeared": _nation_presence,
    "nation.disappeared": _nation_presence,
    "nation.statistic_shifted": _statistic_shifted,
    "nation.band_crossed": _band_crossed,
    "nation.population_changed": _population_changed,
    "nation.pcgdp_trend": _pcgdp_trend,
    "nation.space_assets_changed": _space_assets_changed,
    "nation.rank_changed": _rank_changed,
    "nation.claims_changed": _claims_changed("claims"),
    "nation.hostile_claims_changed": _claims_changed("hostile claims"),
    "nation.renamed": _renamed,
    "nation.unrest_attempts_changed": _unrest_attempts_changed,
    "nation.new_government_recorded": _new_government_recorded,
    "nation.nuclear_program_changed": _plain("nuclear program"),
    "nation.policy_changed": _policy_changed,
    "campaign.interstate_wars_changed": _list_changed,
    "nation.territory_gained": _territory_gained,
    "nation.territory_lost": _territory_lost,
    "nation.independence": _independence,
    "nation.unification": _unification,
    "nation.annexation": _annexation,
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
