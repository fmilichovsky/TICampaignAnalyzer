"""Markdown rendering of already-structured events."""

from ..model.events import Event
from ..model.values import to_jsonable


def render_events(events: list[Event]) -> str:
    """Render a deterministic forensic list; richer narrative prose comes later."""
    return "\n".join(f"- {to_jsonable(event.date)}: {event.event_type}" for event in events)
