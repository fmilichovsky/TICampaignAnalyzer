"""Chronological ordering helpers."""

from ..model.events import Event


def chronological(events: list[Event]) -> list[Event]:
    return sorted(events, key=lambda event: (event.date, event.id))
