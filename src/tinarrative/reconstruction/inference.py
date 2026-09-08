"""Combine objective evidence into conservative inferred events."""

from ..model.events import Event


def infer_events(events: list[Event]) -> list[Event]:
    """Return no inferences until evidence-backed rules are added."""
    return []
