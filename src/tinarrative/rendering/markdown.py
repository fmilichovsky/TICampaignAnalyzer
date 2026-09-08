"""Markdown rendering of already-structured events."""

from ..model.events import Event


def render_events(events: list[Event]) -> str:
    """Render a deterministic forensic list; richer narrative prose comes later."""
    return "\n".join(f"- {event.date}: {event.event_type}" for event in events)
