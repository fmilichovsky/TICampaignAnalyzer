"""The pieces kind templates are written from: entity labels, attribute values and the literal transition."""

from __future__ import annotations

from ..diff.render import render_value
from ..model.entities import EntityRef
from ..model.events import Event, Role
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


# --- Narrative events (#325) ---------------------------------------------------------------------------------------

METRIC_SHIFTS = frozenset({"metric_shifts"})
"""Every narrative event that carries ``bounded_shifts`` has this key, the omitted count only when it cut."""
METRIC_SHIFTS_OMITTED = frozenset({"metric_shifts_omitted"})


def role_label(event: Event, role: Role) -> str:
    refs = [ref.label() for found, ref in event.roles if found is role]
    return ", ".join(refs) if refs else "null"


def has_role(event: Event, role: Role) -> bool:
    return any(found is role for found, _ in event.roles)


def refs_label(event: Event, name: str) -> str:
    """A tuple attribute of references as a comma-separated list of IDs."""
    value = event.attribute(name)
    if not isinstance(value, tuple):
        return render_event_value(value)
    return ", ".join(render_event_value(item) for item in value)


def count_label(value: Observed, noun: str) -> str:
    return f"{render_value(value)} {noun}{'' if value == 1 else 's'}"


def band_label(event: Event) -> str:
    statistic, start, end = (attribute_text(event, name) for name in ("statistic", "from_band", "to_band"))
    return f"{statistic}: {start} -> {end}"
