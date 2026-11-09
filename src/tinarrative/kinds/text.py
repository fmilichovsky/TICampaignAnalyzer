"""The pieces kind templates are written from: entity labels, attribute values and the literal transition."""

from __future__ import annotations

from ..diff.render import render_value
from ..model.entities import EntityDomain, EntityRef
from ..model.events import Event
from ..model.kinds import Template
from ..model.values import Observed

TRANSITION = frozenset({"transition", "before", "after"})
"""The attribute keys of a literal transition (``analyzers.common.transition_attributes``)."""
ABSENT = "is absent from the after snapshot"
PRESENT = "is present only in the after snapshot"


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


def entity_of(event: Event, domain: EntityDomain, skip: int = 0) -> EntityRef | None:
    """The ``skip``-th entity of ``domain`` after the subject."""
    matches = [ref for ref in event.entities[1:] if ref.entity_id.domain is domain]
    return matches[skip] if len(matches) > skip else None


def name_of(ref: EntityRef | None) -> str:
    return ref.label() if ref is not None else "null"


def presence(event: Event) -> str:
    return PRESENT if event.attribute("side") == "after" else ABSENT


def with_context(label: str, domain: EntityDomain, prefix: str = "") -> Template:
    """``<subject> (<prefix><context>) <label>: before -> after`` with the first ``domain`` entity as context."""

    def describe(event: Event) -> str:
        return f"{subject_label(event)} ({prefix}{name_of(entity_of(event, domain))}) {transition_label(event, label)}"

    return describe


def presence_with(domain: EntityDomain, prefix: str) -> Template:
    return lambda event: f"{subject_label(event)} ({prefix} {name_of(entity_of(event, domain))}) {presence(event)}"


def list_changed(event: Event) -> str:
    field = event.sources[0].change.field if event.sources else "list"
    transition = event.attribute("transition")
    if transition == "unresolved":
        return f"{subject_label(event)} {transition_label(event, f'{field} list')}"
    sign = "+" if transition == "added" else "-"
    return f"{subject_label(event)} {field} list: {sign}{attribute_label(event, 'member')}"
