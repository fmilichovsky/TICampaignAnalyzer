"""Fleets, habs, ships and space-combat events, and the campaigns, colonisation waves and fleet buildups told from
them."""

from __future__ import annotations

from ..diff.render import render_value
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole, Scaling, ShareOf, Template
from ..model.values import FrozenMap, Observed, Unknown
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
    transition_label,
)
from .text import (
    refs as _refs,
)
from .text import (
    subject_label as _subject,
)


def _context(event: Event, domain: EntityDomain) -> str | None:
    ref = next((ref for ref in event.entities[1:] if ref.entity_id.domain is domain), None)
    return ref.label() if ref is not None else None


def _presence(event: Event, domain: EntityDomain, label: str) -> str:
    """``<subject> appeared (<label> <context>)``; a missing context is left out."""
    verb = "appeared" if event.attribute("side") == "after" else "disappeared"
    context = _context(event, domain)
    return f"{_subject(event)} {verb}" + (f" ({label} {context})" if context is not None else "")


def _ship_presence(event: Event) -> str:
    """``<ship> appeared in fleet <fleet>`` or ``<ship> disappeared from fleet <fleet>``."""
    after = event.attribute("side") == "after"
    fleet = _context(event, EntityDomain.FLEET)
    where = "" if fleet is None else f" {'in' if after else 'from'} fleet {fleet}"
    return f"{_subject(event)} {'appeared' if after else 'disappeared'}{where}"


def _trailing(label: str, domain: EntityDomain, prefix: str = "faction ") -> Template:
    """``<subject> <label>: before -> after (<prefix><context>)``: the transition leads, the owner trails."""

    def describe(event: Event) -> str:
        text = f"{_subject(event)} {transition_label(event, label)}"
        context = _context(event, domain)
        return text if context is None else f"{text} ({prefix}{context})"

    return describe


def _hab_presence(event: Event) -> str:
    text = _presence(event, EntityDomain.FACTION, "faction")
    if not isinstance(event.attribute("projected_completion"), Unknown):
        text += f"; core projected to arrive {_text(event, 'projected_arrival')}"
        text += f" and complete {_text(event, 'projected_completion')}"
    return text


def _hab_established(event: Event) -> str:
    faction = _context(event, EntityDomain.FACTION)
    owner = "" if faction is None else f" (faction {faction})"
    return f"{_subject(event)} became operational at {_attr(event, 'body')}{owner}"


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
            f"{_subject(event)} was destroyed by {names} {where}: one of "
            f"{_attr(event, 'candidates')} recorded destructions for {_attr(event, 'vanished')} vanished habs"
        )
    by = "" if event.attribute("destroyer") is None else f" by {_attr(event, 'destroyer')}"
    dates = event.attribute("recorded_dates")
    if isinstance(dates, tuple) and len(set(dates)) > 1 and all(isinstance(date, str) for date in dates):
        on = f" between {dates[0]} and {dates[-1]}"
    else:
        on = "" if event.attribute("recorded_on") is None else f" on {_text(event, 'recorded_on')}"
    return f"{_subject(event)} was destroyed{by}{on} {where}"


def _space_losses(event: Event) -> str:
    parts = [
        _count(count, label)
        for name, label in (("ships_lost", "ship"), ("habs_lost", "hab"))
        if (count := event.attribute(name))
    ]
    return f"{_subject(event)} destroyed {' and '.join(parts)} of {_attr(event, 'victim')}"


def _destruction_recorded(event: Event) -> str:
    hab = next((value for name, value in event.attributes if name == "hab"), None)
    what = "hab" if hab is None else _attr(event, "hab")
    destroyer = event.attribute("destroyer")
    by = "" if destroyer is None else f" by {_attr(event, 'destroyer')}"
    return (
        f"{what} destroyed{by} at {_attr(event, 'space_body')} "
        f"(type {_attr(event, 'hab_type')}, dated {_text(event, 'recorded_on')}, recorded by {_subject(event)})"
    )


def _combat_side(side: object) -> tuple[EntityId | None, str]:
    """The faction id (when it is a resolved reference) and ``<faction> (<n> ships)`` of one side."""
    if not (isinstance(side, tuple) and len(side) == 2 and isinstance(side[1], FrozenMap)):
        return None, render_event_value(side)  # type: ignore[arg-type]
    ships = sum(count for _, count in side[1].items if isinstance(count, int))
    ref = side[0]
    entity_id = ref.entity_id if isinstance(ref, EntityRef) else None
    return entity_id, f"{render_event_value(ref)} ({ships} {'ship' if ships == 1 else 'ships'})"


def _combat_head(event: Event) -> str:
    """``<side> wins|loses against <others>``, from the recording faction's side when it is one."""
    sides = event.attribute("sides")
    winner = event.attribute("winner")
    if not isinstance(sides, tuple) or not sides:
        text = "no sides" if isinstance(sides, tuple) else render_event_value(sides)
        return text if winner is None else f"{text}; winner {render_event_value(winner)}"
    parsed = [_combat_side(side) for side in sides]
    winner_id = winner.entity_id if isinstance(winner, EntityRef) else None
    ids = [entity_id for entity_id, _ in parsed]
    subject_id = event.entities[0].entity_id if event.entities else None
    decided = winner_id is not None and winner_id in ids
    if decided and subject_id in ids:
        lead = ids.index(subject_id)
        verb = "wins" if winner_id == subject_id else "loses"
    elif decided:
        lead = ids.index(winner_id)
        verb = "wins"
    else:
        lead, verb = 0, None
    others = " and ".join(text for index, (_, text) in enumerate(parsed) if index != lead)
    if verb is None:
        text = " vs ".join(text for _, text in parsed)
        return text if winner is None else f"{text}; winner {render_event_value(winner)}"
    return f"{parsed[lead][1]} {verb}" + (f" against {others}" if others else "")


def _combat_line(event: Event, prefix: str) -> str:
    recorded_on = event.attribute("recorded_on")
    dated = "undated" if recorded_on is None else f"dated {_text(event, 'recorded_on')}"
    hab_faction = event.attribute("hab_faction")
    text = f"{prefix}{_combat_head(event)}"
    if event.entities and not _combat_head_names_subject(event):
        text += f"; recorded by {_subject(event)}"
    if hab_faction is not None:
        text += f"; hab faction {_attr(event, 'hab_faction')}"
    return f"{text}; attacks {_attr(event, 'attack_count')} ({dated})"


def _combat_head_names_subject(event: Event) -> bool:
    sides = event.attribute("sides")
    subject_id = event.entities[0].entity_id
    return isinstance(sides, tuple) and any(_combat_side(side)[0] == subject_id for side in sides)


def _combat_recorded(event: Event) -> str:
    return _combat_line(event, "")


def _combat_entry_removed(event: Event) -> str:
    return _combat_line(event, "entry removed: ")


TRANSITION = frozenset({"transition", "before", "after"})
_LIST_OPTIONAL = frozenset({"member", "before", "after"})

FLEET_FACTION_CHANGED = EventKind(
    "fleet.faction_changed",
    plain("faction"),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    share=ShareOf.FLEET,
    scaling=Scaling.FLEET,
    base=Significance.MAJOR,
)
FLEET_DOCKED_LOCATION_CHANGED = EventKind(
    "fleet.docked_location_changed",
    _trailing("docked location", EntityDomain.FACTION),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    base=Significance.TRIVIAL,
)
FLEET_ORBIT_CHANGED = EventKind(
    "fleet.orbit_changed",
    _trailing("orbit", EntityDomain.FACTION),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    base=Significance.TRIVIAL,
)
FLEET_BARYCENTER_CHANGED = EventKind(
    "fleet.barycenter_changed",
    _trailing("barycenter", EntityDomain.FACTION),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    base=Significance.TRIVIAL,
)
FLEET_PARENT_CHANGED = EventKind(
    "fleet.parent_fleet_changed",
    _trailing("parent fleet", EntityDomain.FACTION),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    base=Significance.TRIVIAL,
)
FLEET_IN_COMBAT_CHANGED = EventKind(
    "fleet.in_combat_changed",
    _trailing("in-combat flag", EntityDomain.FACTION),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    base=Significance.TRIVIAL,
)
FLEET_APPEARED = EventKind(
    "fleet.appeared",
    lambda event: _presence(event, EntityDomain.FACTION, "faction"),
    EvidenceRole.BOOKKEEPING,
    frozenset({"side"}),
    base=Significance.TRIVIAL,
)
FLEET_DISAPPEARED = EventKind(
    "fleet.disappeared",
    lambda event: _presence(event, EntityDomain.FACTION, "faction"),
    EvidenceRole.BOOKKEEPING,
    frozenset({"side"}),
    base=Significance.TRIVIAL,
)
FACTION_FLEETS_CHANGED = EventKind(
    "faction.fleets_changed",
    list_changed,
    EvidenceRole.BOOKKEEPING,
    frozenset({"transition"}),
    _LIST_OPTIONAL,
    base=Significance.TRIVIAL,
)
HAB_DOCKED_FLEETS_CHANGED = EventKind(
    "hab.docked_fleets_changed",
    list_changed,
    EvidenceRole.BOOKKEEPING,
    frozenset({"transition"}),
    _LIST_OPTIONAL,
    base=Significance.TRIVIAL,
)
SHIP_FLEET_CHANGED = EventKind(
    "ship.fleet_changed", plain("fleet"), EvidenceRole.BOOKKEEPING, TRANSITION, base=Significance.TRIVIAL
)
SHIP_LAST_REFIT_CHANGED = EventKind(
    "ship.last_refit_date_changed",
    contextual("last refit date", EntityDomain.FLEET, "fleet "),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    base=Significance.TRIVIAL,
)
SHIP_APPEARED = EventKind(
    "ship.appeared",
    _ship_presence,
    EvidenceRole.BOOKKEEPING,
    frozenset({"side"}),
    frozenset({"hull"}),
    base=Significance.TRIVIAL,
)
SHIP_DISAPPEARED = EventKind(
    "ship.disappeared",
    _ship_presence,
    EvidenceRole.BOOKKEEPING,
    frozenset({"side"}),
    frozenset({"hull"}),
    base=Significance.TRIVIAL,
)
FLEET_SHIPS_CHANGED = EventKind(
    "fleet.ships_changed",
    list_changed,
    EvidenceRole.BOOKKEEPING,
    frozenset({"transition"}),
    _LIST_OPTIONAL,
    base=Significance.TRIVIAL,
)

HAB_FACTION_CHANGED = EventKind(
    "hab.faction_changed",
    plain("faction"),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    share=ShareOf.HAB,
    scaling=Scaling.HAB,
    base=Significance.MINOR,
)
HAB_TYPE_CHANGED = EventKind(
    "hab.type_changed",
    _trailing("type", EntityDomain.FACTION),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    base=Significance.MINOR,
)
HAB_TIER_CHANGED = EventKind(
    "hab.tier_changed",
    _trailing("tier", EntityDomain.FACTION),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    base=Significance.MINOR,
)
HAB_IN_COMBAT_CHANGED = EventKind(
    "hab.in_combat_changed",
    _trailing("in-combat flag", EntityDomain.FACTION),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    base=Significance.MINOR,
)
HAB_UNDER_ASSAULT_CHANGED = EventKind(
    "hab.under_assault_changed",
    _trailing("under-assault flag", EntityDomain.FACTION),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    base=Significance.MINOR,
)
HAB_UNDER_BOMBARDMENT_CHANGED = EventKind(
    "hab.under_bombardment_changed",
    _trailing("under-bombardment flag", EntityDomain.FACTION),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    base=Significance.MINOR,
)
HAB_CORE_COMPLETED_CHANGED = EventKind(
    "hab.core_completed_changed",
    _trailing("core-completed flag", EntityDomain.FACTION),
    EvidenceRole.BOOKKEEPING,
    TRANSITION,
    base=Significance.MINOR,
)
HAB_APPEARED = EventKind(
    "hab.appeared",
    _hab_presence,
    EvidenceRole.BOOKKEEPING,
    frozenset({"side"}),
    frozenset({"core_completed", "projected_arrival", "projected_completion"}),
    share=ShareOf.HAB,
    scaling=Scaling.HAB,
    base=Significance.MINOR,
)
HAB_DISAPPEARED = EventKind(
    "hab.disappeared",
    lambda event: _presence(event, EntityDomain.FACTION, "faction"),
    EvidenceRole.BOOKKEEPING,
    frozenset({"side"}),
    base=Significance.TRIVIAL,
)
FACTION_HAB_DESTRUCTION_RECORDED = EventKind(
    "faction.hab_destruction_recorded",
    _destruction_recorded,
    EvidenceRole.EVIDENCE,
    frozenset({"hab_type", "space_body", "destroyer", "recorded_on"}),
    frozenset({"hab", "owner"}),
    base=Significance.MINOR,
)
FACTION_COMBAT_RECORDED = EventKind(
    "faction.combat_recorded",
    _combat_recorded,
    EvidenceRole.EVIDENCE,
    frozenset({"sides", "winner", "hab_faction", "attack_count", "surprising", "recorded_on", "side_dry_mass"}),
    share=ShareOf.COMBAT,
    scaling=Scaling.BATTLE,
    base=Significance.MINOR,
)
FACTION_COMBAT_ENTRY_REMOVED = EventKind(
    "faction.combat_entry_removed",
    _combat_entry_removed,
    EvidenceRole.BOOKKEEPING,
    frozenset({"sides", "winner", "hab_faction", "attack_count", "surprising", "recorded_on"}),
    base=Significance.TRIVIAL,
)

HAB_ESTABLISHED = EventKind(
    "hab.established", _hab_established, EvidenceRole.EVIDENCE, frozenset({"faction", "body"}), base=Significance.MAJOR
)
FACTION_FIRST_HAB_ON_BODY = EventKind(
    "faction.first_hab_on_body",
    _first_hab_on_body,
    EvidenceRole.EVIDENCE,
    frozenset({"body", "habs", "hab_count", "first_of_any_faction", "milestones"}),
    share=ShareOf.HAB,
    scaling=Scaling.HAB,
    base=Significance.MAJOR,
)
HAB_DESTROYED = EventKind(
    "hab.destroyed",
    _hab_destroyed,
    EvidenceRole.EVIDENCE,
    frozenset({"hab_type", "body", "signals", "ambiguous"}),
    frozenset({"destroyer", "recorded_on", "destroyers", "recorded_dates", "candidates", "vanished"}),
    share=ShareOf.HAB,
    scaling=Scaling.HAB,
    base=Significance.MAJOR,
)
FACTION_SPACE_LOSSES = EventKind(
    "faction.space_losses",
    _space_losses,
    EvidenceRole.EVIDENCE,
    frozenset({"victim", "ships_lost", "habs_lost", "ships", "habs"}),
    share=ShareOf.SPACE_LOSSES,
    scaling=Scaling.SPACE_LOSS,
    base=Significance.MAJOR,
)


def _side_label(label: str, alien: Observed) -> str:
    return f"the aliens ({label})" if alien is True else label


def _lost(label: str, ships: Observed, habs: Observed) -> str:
    lost = [_count(number, noun) for number, noun in ((ships, "ship"), (habs, "hab")) if number]
    return f"{label} lost {' and '.join(lost) if lost else 'nothing'}"


def _years(start: Observed, end: Observed) -> str:
    first, last = (str(value)[:4] for value in (start, end))
    return first if first == last else f"{first}\u2013{last}"


def _space_campaign(event: Event) -> str:
    sides, aliens = event.attribute("sides"), event.attribute("alien")
    ships, habs = event.attribute("ships_lost"), event.attribute("habs_lost")
    won = event.attribute("combats_won")
    assert isinstance(sides, tuple) and isinstance(aliens, tuple) and isinstance(ships, tuple)
    assert isinstance(habs, tuple) and isinstance(won, tuple)
    names = [render_event_value(side) for side in sides]
    labels = [_side_label(name, alien) for name, alien in zip(names, aliens, strict=True)]
    lost = ", ".join(_lost(label, *pair) for label, pair in zip(labels, zip(ships, habs, strict=True), strict=True))
    text = f"{' and '.join(labels)} conducted hostile space manoeuvres, "
    text += f"{_years(event.attribute('span_from'), event.attribute('span_to'))}: {lost}"
    if event.attribute("combats"):
        text += f"; {_count(event.attribute('combats'), 'recorded combat')}"
        if any(won):
            text += f", {render_value(won[0])} won by {names[0]} and {render_value(won[1])} by {names[1]}"
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
            "sides",
            "alien",
            "ships_lost",
            "habs_lost",
            "combats",
            "combats_won",
            "bodies",
            "span_from",
            "span_to",
        }
    ),
    base=Significance.MINOR,
    share=ShareOf.SPACE_CAMPAIGN,
    scaling=Scaling.SPACE_LOSS,
)
COLONISATION_WAVE = narrative_kind(
    "faction.colonisation_wave",
    _colonisation_wave,
    required=frozenset({"bodies", "hab_count", "first_of_any_faction"}),
    base=Significance.MAJOR,
    share=ShareOf.COLONY,
    scaling=Scaling.HAB,
)
FLEET_BUILDUP = narrative_kind(
    "faction.fleet_buildup",
    _fleet_buildup,
    required=frozenset({"hull", "count"}),
    base=Significance.MINOR,
    share=ShareOf.NEW_SHIPS,
    scaling=Scaling.FLEET,
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
    FACTION_SPACE_LOSSES,
    SPACE_CAMPAIGN,
    COLONISATION_WAVE,
    FLEET_BUILDUP,
)
