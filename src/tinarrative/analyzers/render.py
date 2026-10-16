"""One-line, conservative text for an :class:`Event`.

This is the message catalog: the wording per event type that a renderer may reuse. It describes the
literal transition and names the entities; it never names a cause. A literal save value that an event
carries as an attribute (for example a recorded cause string) is deliberately not echoed here. The exception is
the game's notification log: a ``notification.*`` line quotes the log template identifier, which is the game's
own statement of what happened, so its wording is evidence, not inference (the summary text is still not echoed).
"""

from __future__ import annotations

from collections.abc import Callable

from ..diff.render import render_value
from ..model.entities import EntityDomain, EntityRef
from ..model.events import Event
from ..model.values import FrozenMap, Unknown
from .campaign.notifications import PREFIX as NOTIFICATION_PREFIX

ABSENT = "is absent from the after snapshot"
PRESENT = "is present only in the after snapshot"


def describe_event(event: Event) -> str:
    """Deterministic ASCII text; an event type without a template falls back to the type and its entities.

    ``notification.<template>`` types share one template, since the log template set is open-ended.
    """
    template = _TEMPLATES.get(event.event_type)
    if template is None and event.event_type.startswith(NOTIFICATION_PREFIX):
        template = _notification_logged
    if template is None:
        entities = ", ".join(str(ref.entity_id) for ref in event.entities)
        return _ascii(f"{event.event_type}: {entities}")
    return _ascii(template(event))


def _ascii(text: str) -> str:
    if text.isascii():
        return text
    return "".join(char if char.isascii() else f"\\u{ord(char):04x}" for char in text)


def _subject(event: Event) -> str:
    return str(event.entities[0].entity_id) if event.entities else event.id


def _entity(event: Event, domain: EntityDomain, skip: int = 0) -> EntityRef | None:
    matches = [ref for ref in event.entities[1:] if ref.entity_id.domain is domain]
    return matches[skip] if len(matches) > skip else None


def _name(ref: EntityRef | None) -> str:
    return str(ref.entity_id) if ref is not None else "null"


def _attr(event: Event, name: str) -> str:
    return render_value(event.attribute(name))


def _text(event: Event, name: str) -> str:
    """A date, relation name or transition label as plain text; anything else like a value."""
    value = event.attribute(name)
    return value if isinstance(value, str) else render_value(value)


def _transition(event: Event, label: str) -> str:
    return f"{label}: {_attr(event, 'before')} -> {_attr(event, 'after')}"


def _presence(event: Event) -> str:
    return PRESENT if event.attribute("side") == "after" else ABSENT


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


def _list_changed(event: Event) -> str:
    field = event.sources[0].change.field if event.sources else "list"
    transition = event.attribute("transition")
    if transition == "unresolved":
        return f"{_subject(event)} {_transition(event, f'{field} list')}"
    sign = "+" if transition == "added" else "-"
    return f"{_subject(event)} {field} list: {sign}{_attr(event, 'member')}"


def _relation_changed(event: Event) -> str:
    pair = " and ".join(str(ref.entity_id) for ref in event.entities)
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
        text += f" (previously {render_value(previous)})"
    return text


def _councilor_field(label: str) -> Callable[[Event], str]:
    def describe(event: Event) -> str:
        return f"{_subject(event)} ({_name(_entity(event, EntityDomain.FACTION))}) {_transition(event, label)}"

    return describe


def _councilor_presence(event: Event) -> str:
    return f"{_subject(event)} (faction {_name(_entity(event, EntityDomain.FACTION))}) {_presence(event)}"


def _plain(label: str) -> Callable[[Event], str]:
    return lambda event: f"{_subject(event)} {_transition(event, label)}"


def _side_list(event: Event) -> str:
    nations = ", ".join(str(ref.entity_id) for ref in event.entities[1:] if ref.entity_id.domain is EntityDomain.NATION)
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


def _nation_presence(event: Event) -> str:
    return f"{_subject(event)} {_presence(event)}"


def _with_context(label: str, domain: EntityDomain, prefix: str = "") -> Callable[[Event], str]:
    """``<subject> (<prefix><context>) <label>: before -> after`` with the first ``domain`` entity as context."""

    def describe(event: Event) -> str:
        return f"{_subject(event)} ({prefix}{_name(_entity(event, domain))}) {_transition(event, label)}"

    return describe


def _presence_with(domain: EntityDomain, prefix: str) -> Callable[[Event], str]:
    return lambda event: f"{_subject(event)} ({prefix} {_name(_entity(event, domain))}) {_presence(event)}"


def _army_presence(event: Event) -> str:
    faction = _name(_entity(event, EntityDomain.FACTION))
    region = _name(_entity(event, EntityDomain.REGION))
    text = f"{_subject(event)} (faction {faction}, region {region}) {_presence(event)}"
    return text + " (megafauna)" if event.attribute("megafauna") is True else text


def _crashdown_changed(event: Event) -> str:
    if event.sources and event.sources[0].change.field == "crashdownTime":
        return f"{_subject(event)} {_transition(event, 'crashdown time')}"
    text = f"{_subject(event)} {_transition(event, 'crashdown present')}"
    if not isinstance(event.attribute("crashdown_time"), Unknown):
        text += f"; crashdown time {_text(event, 'crashdown_time')}"
    return text


def _destruction_recorded(event: Event) -> str:
    return (
        f"{_subject(event)} records a hab destruction dated {_text(event, 'recorded_on')}: "
        f"type {_attr(event, 'hab_type')} at {_attr(event, 'space_body')} by {_attr(event, 'destroyer')}"
    )


def _combat_sides(event: Event) -> str:
    """``faction:15 (3 ships) vs faction:16 (2 ships)``; the unknown value when the sides are.

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
        parts.append(f"{render_value(side[0])} ({ships} {'ship' if ships == 1 else 'ships'})")
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


def _technology_completed(event: Event) -> str:
    text = f"{_subject(event)} is listed as finished"
    if event.attribute("side") == "after":
        text += " (no earlier research state)"
    return text


def _technology_presence(event: Event) -> str:
    return f"{_subject(event)} (finished {_attr(event, 'finished')}) {_presence(event)}"


def _global_values_presence(event: Event) -> str:
    return f"{_subject(event)} {_presence(event)}"


def _milestone_recorded(event: Event) -> str:
    return f"{_subject(event)} records global milestone {_text(event, 'milestone')} for {_attr(event, 'faction')}"


def _milestone_changed(event: Event) -> str:
    label = f"global milestone {_text(event, 'milestone')} faction"
    return f"{_subject(event)} {_transition(event, label)}"


def _sea_level_rise(event: Event) -> str:
    return f"{_subject(event)} sea level rise {_attr(event, 'stage')} flag set"


def _narrative_event_triggered(event: Event) -> str:
    name = _text(event, "narrative_event")
    if event.attribute("scope") == "target":
        return f"{_subject(event)} lists narrative event {name} as triggered for {_attr(event, 'targets')}"
    return f"{_subject(event)} lists narrative event {name} as triggered once per campaign"


def _global_value_changed(event: Event) -> str:
    field = _text(event, "field")
    if isinstance(event.attribute("transition"), Unknown):
        return (
            f"{_subject(event)} {field} records changed: {_attr(event, 'added')} added, "
            f"{_attr(event, 'removed')} removed, {_attr(event, 'changed')} changed"
        )
    return f"{_subject(event)} {_transition(event, field)}"


def _notification_subject(event: Event) -> str:
    """The resolved subject, ``null`` for none, or the literal unresolved value; never the summary text."""
    subject = event.attribute("subject")
    return str(subject.entity_id) if isinstance(subject, EntityRef) else render_value(subject)


def _notification_logged(event: Event) -> str:
    date = event.date if isinstance(event.date, str) else render_value(event.date)
    return f"{_subject(event)} logs {_text(event, 'template')} dated {date} about {_notification_subject(event)}"


def _notification_removed(event: Event) -> str:
    return (
        f"{_subject(event)} no longer lists {_text(event, 'template')} dated {_text(event, 'logged_on')}"
        f" about {_notification_subject(event)}"
    )


def _notification_changed(event: Event) -> str:
    before_subject = event.attribute("before_subject")
    before = str(before_subject.entity_id) if isinstance(before_subject, EntityRef) else render_value(before_subject)
    return (
        f"{_subject(event)} entry {_text(event, 'template')} dated {_text(event, 'logged_on')} changed: "
        f"subject {before} -> {_notification_subject(event)}, "
        f"outcome {_attr(event, 'before_outcome')} -> {_attr(event, 'outcome')}"
    )


_TEMPLATES: dict[str, Callable[[Event], str]] = {
    "control_point.controller_changed": _controller_changed,
    "control_point.nation_changed": _plain("nation"),
    "control_point.appeared": _control_point_presence,
    "control_point.disappeared": _control_point_presence,
    "control_point.loss_recorded": _loss_recorded,
    "faction.control_points_changed": _list_changed,
    "nation.control_points_changed": _list_changed,
    "region.nation_changed": _plain("nation"),
    "nation.capital_changed": _plain("capital"),
    "nation.relation_changed": _relation_changed,
    "nation.federation_changed": _plain("federation"),
    "nation.breakaway_parent_changed": _plain("breakaway parent"),
    "nation.regions_changed": _list_changed,
    "nation.breakaways_changed": _list_changed,
    "nation.allies_changed": _list_changed,
    "nation.rivals_changed": _list_changed,
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
    "nation.executive_change_recorded": _executive_change,
    "nation.appeared": _nation_presence,
    "nation.disappeared": _nation_presence,
    "councilor.faction_changed": _plain("faction"),
    "councilor.status_changed": _councilor_field("status"),
    "councilor.location_changed": _councilor_field("location"),
    "councilor.detaining_faction_changed": _councilor_field("detaining faction"),
    "councilor.appeared": _councilor_presence,
    "councilor.disappeared": _councilor_presence,
    "faction.councilors_changed": _list_changed,
    "organization.appeared": _presence_with(EntityDomain.REGION, "home region"),
    "organization.disappeared": _presence_with(EntityDomain.REGION, "home region"),
    "organization.assigned_councilor_changed": _plain("assigned councilor"),
    "organization.faction_orbit_changed": _plain("faction orbit"),
    "councilor.orgs_changed": _list_changed,
    "faction.unassigned_orgs_changed": _list_changed,
    "army.region_changed": _with_context("region", EntityDomain.FACTION),
    "army.faction_changed": _with_context("faction", EntityDomain.REGION, "in "),
    "army.destroyed_changed": _with_context("destroyed flag", EntityDomain.FACTION),
    "army.strength_changed": _with_context("strength", EntityDomain.FACTION),
    "army.type_changed": _with_context("type", EntityDomain.FACTION),
    "army.deployment_type_changed": _with_context("deployment type", EntityDomain.FACTION),
    "army.home_region_changed": _with_context("home region", EntityDomain.FACTION),
    "army.appeared": _army_presence,
    "army.disappeared": _army_presence,
    "region.crashdown_changed": _crashdown_changed,
    "region.landing_changed": _plain("landing present"),
    "region.alien_facility_changed": _plain("alien facility built"),
    "region.xenoforming_changed": _plain("xenoforming level"),
    "faction.armies_changed": _list_changed,
    "nation.armies_changed": _list_changed,
    "region.armies_changed": _list_changed,
    "fleet.faction_changed": _plain("faction"),
    "fleet.docked_location_changed": _with_context("docked location", EntityDomain.FACTION),
    "fleet.orbit_changed": _with_context("orbit", EntityDomain.FACTION),
    "fleet.barycenter_changed": _with_context("barycenter", EntityDomain.FACTION),
    "fleet.parent_fleet_changed": _with_context("parent fleet", EntityDomain.FACTION),
    "fleet.in_combat_changed": _with_context("in-combat flag", EntityDomain.FACTION),
    "fleet.appeared": _presence_with(EntityDomain.FACTION, "faction"),
    "fleet.disappeared": _presence_with(EntityDomain.FACTION, "faction"),
    "faction.fleets_changed": _list_changed,
    "hab.docked_fleets_changed": _list_changed,
    "ship.fleet_changed": _plain("fleet"),
    "ship.last_refit_date_changed": _with_context("last refit date", EntityDomain.FLEET, "fleet "),
    "ship.appeared": _presence_with(EntityDomain.FLEET, "fleet"),
    "ship.disappeared": _presence_with(EntityDomain.FLEET, "fleet"),
    "fleet.ships_changed": _list_changed,
    "hab.faction_changed": _plain("faction"),
    "hab.type_changed": _with_context("type", EntityDomain.FACTION),
    "hab.tier_changed": _with_context("tier", EntityDomain.FACTION),
    "hab.in_combat_changed": _with_context("in-combat flag", EntityDomain.FACTION),
    "hab.under_assault_changed": _with_context("under-assault flag", EntityDomain.FACTION),
    "hab.under_bombardment_changed": _with_context("under-bombardment flag", EntityDomain.FACTION),
    "hab.core_completed_changed": _with_context("core-completed flag", EntityDomain.FACTION),
    "hab.appeared": _presence_with(EntityDomain.FACTION, "faction"),
    "hab.disappeared": _presence_with(EntityDomain.FACTION, "faction"),
    "faction.hab_destruction_recorded": _destruction_recorded,
    "faction.combat_recorded": _combat_recorded,
    "faction.combat_entry_removed": _combat_entry_removed,
    "technology.completed": _technology_completed,
    "technology.finished_changed": _plain("finished"),
    "technology.appeared": _technology_presence,
    "technology.disappeared": _technology_presence,
    "research.finished_techs_changed": _list_changed,
    "campaign.global_values_appeared": _global_values_presence,
    "campaign.global_values_disappeared": _global_values_presence,
    "campaign.global_milestone_recorded": _milestone_recorded,
    "campaign.global_milestone_changed": _milestone_changed,
    "campaign.nuclear_strikes_changed": _plain("nuclear strikes"),
    "campaign.sea_level_rise_triggered": _sea_level_rise,
    "campaign.narrative_event_triggered": _narrative_event_triggered,
    "campaign.global_value_changed": _global_value_changed,
    "campaign.interstate_wars_changed": _list_changed,
    "notification.queue_appeared": _global_values_presence,
    "notification.queue_disappeared": _global_values_presence,
    "notification.queue_value_changed": _global_value_changed,
    "notification.entry_removed": _notification_removed,
    "notification.entry_changed": _notification_changed,
}
