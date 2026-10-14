"""One-line, conservative text for an :class:`Event`.

This is the message catalog: the wording per event type that a renderer may reuse. It describes the
literal transition and names the entities; it never names a cause. A literal save value that an event
carries as an attribute (for example a recorded cause string) is deliberately not echoed here.
"""

from __future__ import annotations

from collections.abc import Callable

from ..diff.render import render_value
from ..model.entities import EntityDomain, EntityRef
from ..model.events import Event
from ..model.values import Unknown

ABSENT = "is absent from the after snapshot"
PRESENT = "is present only in the after snapshot"


def describe_event(event: Event) -> str:
    """Deterministic ASCII text; an event type without a template falls back to the type and its entities."""
    template = _TEMPLATES.get(event.event_type)
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


def _federation(event: Event) -> str:
    return f"{_subject(event)} {_transition(event, 'federation')} (unmodelled state type)"


def _nation_presence(event: Event) -> str:
    return f"{_subject(event)} {_presence(event)}"


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
    "nation.federation_changed": _federation,
    "nation.breakaway_parent_changed": _plain("breakaway parent"),
    "nation.regions_changed": _list_changed,
    "nation.breakaways_changed": _list_changed,
    "nation.allies_changed": _list_changed,
    "nation.rivals_changed": _list_changed,
    "nation.wars_changed": _list_changed,
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
}
