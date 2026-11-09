"""The pieces kind templates are written from: entity labels, attribute values and the literal transition."""

from __future__ import annotations

from ..diff.render import render_value
from ..model.entities import EntityRef
from ..model.events import Event
from ..model.kinds import Template
from ..model.values import Observed


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
