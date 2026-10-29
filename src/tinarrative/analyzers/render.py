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
        entities = ", ".join(ref.label() for ref in event.entities)
        return _ascii(f"{event.event_type}: {entities}")
    return _ascii(template(event))


def _ascii(text: str) -> str:
    if text.isascii():
        return text
    return "".join(char if char.isascii() else f"\\u{ord(char):04x}" for char in text)


def _subject(event: Event) -> str:
    return event.entities[0].label() if event.entities else event.id


def _entity(event: Event, domain: EntityDomain, skip: int = 0) -> EntityRef | None:
    matches = [ref for ref in event.entities[1:] if ref.entity_id.domain is domain]
    return matches[skip] if len(matches) > skip else None


def _name(ref: EntityRef | None) -> str:
    return ref.label() if ref is not None else "null"


def render_event_value(value: Observed) -> str:
    """Like :func:`render_value`, but a reference reads as ``Name (domain:id)``, also inside a list."""
    if isinstance(value, EntityRef):
        return value.label()
    if isinstance(value, tuple):
        return "[" + ", ".join(render_event_value(item) for item in value) + "]"
    return render_value(value)


def _attr(event: Event, name: str) -> str:
    return render_event_value(event.attribute(name))


def _text(event: Event, name: str) -> str:
    """A date, relation name or transition label as plain text; anything else like a value."""
    value = event.attribute(name)
    return value if isinstance(value, str) else render_event_value(value)


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


def _project_completed(event: Event) -> str:
    return f"{_subject(event)} lists project {_attr(event, 'project')} as finished"


def _finished_projects_changed(event: Event) -> str:
    if isinstance(event.attribute("member"), Unknown):
        return f"{_subject(event)} {_transition(event, 'finished project list')}"
    return f"{_subject(event)} finished project list: -{_attr(event, 'member')}"


def _councilor_field(label: str) -> Callable[[Event], str]:
    def describe(event: Event) -> str:
        return f"{_subject(event)} ({_name(_entity(event, EntityDomain.FACTION))}) {_transition(event, label)}"

    return describe


def _councilor_presence(event: Event) -> str:
    return f"{_subject(event)} (faction {_name(_entity(event, EntityDomain.FACTION))}) {_presence(event)}"


def _plain(label: str) -> Callable[[Event], str]:
    return lambda event: f"{_subject(event)} {_transition(event, label)}"


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


def _nation_control_changed(event: Event) -> str:
    return f"{_subject(event)} {_transition(event, _text(event, 'scope') + ' control changed')}"


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


def _transaction_recorded(event: Event) -> str:
    """The label is a mission or operation template name read from the ledger, never a reading of what it did."""
    return (
        f"{_subject(event)} ledger records a {_text(event, 'label')} charge: "
        f"{_attr(event, 'amount')} {_text(event, 'resource')} (dated {_text(event, 'recorded_on')})"
    )


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
    return render_event_value(subject)


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
    before = render_event_value(before_subject)
    return (
        f"{_subject(event)} entry {_text(event, 'template')} dated {_text(event, 'logged_on')} changed: "
        f"subject {before} -> {_notification_subject(event)}, "
        f"outcome {_attr(event, 'before_outcome')} -> {_attr(event, 'outcome')}"
    )


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
    "nation.statistic_shifted": _statistic_shifted,
    "nation.band_crossed": _band_crossed,
    "nation.population_changed": _population_changed,
    "nation.pcgdp_trend": _pcgdp_trend,
    "nation.space_assets_changed": _space_assets_changed,
    "nation.rank_changed": _rank_changed,
    "nation.claims_changed": _claims_changed("claims"),
    "nation.hostile_claims_changed": _claims_changed("hostile claims"),
    "nation.renamed": _renamed,
    "federation.renamed": _renamed,
    "nation.unrest_attempts_changed": _unrest_attempts_changed,
    "nation.new_government_recorded": _new_government_recorded,
    "nation.nuclear_program_changed": _plain("nuclear program"),
    "nation.policy_changed": _policy_changed,
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
    "faction.transaction_recorded": _transaction_recorded,
    "technology.completed": _technology_completed,
    "technology.finished_changed": _plain("finished"),
    "technology.appeared": _technology_presence,
    "technology.disappeared": _technology_presence,
    "research.finished_techs_changed": _list_changed,
    "faction.project_completed": _project_completed,
    "faction.finished_project_names_changed": _finished_projects_changed,
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
    "nation.territory_gained": _territory_gained,
    "nation.territory_lost": _territory_lost,
    "nation.independence": _independence,
    "nation.unification": _unification,
    "nation.annexation": _annexation,
    "faction.nation_control_changed": _nation_control_changed,
    "faction.first_hab_on_body": _first_hab_on_body,
    "hab.destroyed": _hab_destroyed,
    "faction.battle_outcome": _battle_outcome,
    "faction.takeover": _takeover,
    "war.arc": _war_arc,
    "federation.lifecycle": _federation_lifecycle,
    "nation.expansion": _expansion,
    "nation.cession": _cession,
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
