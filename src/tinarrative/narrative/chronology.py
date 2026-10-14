"""Chronological ordering helpers."""

from ..model.events import Event


def chronological(events: list[Event]) -> list[Event]:
    return sorted(events, key=lambda event: event.sort_key)
