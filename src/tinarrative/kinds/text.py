"""The pieces kind templates are written from: entity labels, attribute values and the literal transition."""

from __future__ import annotations

from ..diff.render import render_value
from ..model.entities import EntityDomain, EntityRef
from ..model.events import Event
from ..model.kinds import Template
from ..model.values import Observed

TRANSITION = frozenset({"transition", "before", "after"})
"""The attribute keys of a literal transition (``analyzers.common.transition_attributes``)."""


def subject_label(event: Event) -> str:
    return event.entities[0].label() if event.entities else event.id


def render_event_value(value: Observed) -> str:
    """Like :func:`render_value`, but a reference reads as ``Name (domain:id)``, also inside a list."""
    if isinstance(value, EntityRef):
        return value.label()
    if isinstance(value, tuple):
        return "[" + ", ".join(render_event_value(item) for item in value) + "]"
    return render_value(value)


def attribute_label(event: Event, name: str) -> str:
    return render_event_value(event.attribute(name))


def attribute_text(event: Event, name: str) -> str:
    """A date, relation name or transition label as plain text; anything else like a value."""
    value = event.attribute(name)
    return value if isinstance(value, str) else render_event_value(value)


def transition_label(event: Event, label: str) -> str:
    return f"{label}: {attribute_label(event, 'before')} -> {attribute_label(event, 'after')}"


def plain(label: str) -> Template:
    """``<subject> <label>: <before> -> <after>``."""
    return lambda event: f"{subject_label(event)} {transition_label(event, label)}"


ABSENT = "is absent from the after snapshot"
PRESENT = "is present only in the after snapshot"


def entity(event: Event, domain: EntityDomain, skip: int = 0) -> EntityRef | None:
    """The ``skip``-th context entity of ``domain``, after the subject."""
    matches = [ref for ref in event.entities[1:] if ref.entity_id.domain is domain]
    return matches[skip] if len(matches) > skip else None


def name(ref: EntityRef | None) -> str:
    return ref.label() if ref is not None else "null"


def presence(event: Event) -> str:
    return PRESENT if event.attribute("side") == "after" else ABSENT


def list_changed(event: Event) -> str:
    field = event.sources[0].change.field if event.sources else "list"
    transition = event.attribute("transition")
    if transition == "unresolved":
        return f"{subject_label(event)} {transition_label(event, f'{field} list')}"
    sign = "+" if transition == "added" else "-"
    return f"{subject_label(event)} {field} list: {sign}{attribute_label(event, 'member')}"


def refs(event: Event, attribute: str) -> str:
    """A tuple attribute of references as a comma-separated list of IDs."""
    value = event.attribute(attribute)
    if not isinstance(value, tuple):
        return render_event_value(value)
    return ", ".join(render_event_value(item) for item in value)


def region_count(count: Observed) -> str:
    return f"{render_value(count)} region{'' if count == 1 else 's'}"


def regions(event: Event) -> str:
    return region_count(event.attribute("region_count"))


def bands(event: Event) -> str:
    """``<statistic>: <band> -> <band>``, the game's own band labels."""
    return (
        f"{attribute_text(event, 'statistic')}: "
        f"{attribute_text(event, 'from_band')} -> {attribute_text(event, 'to_band')}"
    )
