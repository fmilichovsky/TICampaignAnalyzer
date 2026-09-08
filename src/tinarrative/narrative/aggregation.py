"""Group atomic events into human-scale developments."""

from ..model.events import Event


def aggregate(events: list[Event]) -> list[Event]:
    """Aggregation is intentionally deferred until atomic event semantics exist."""
    return events
