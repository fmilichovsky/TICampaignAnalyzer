"""One-line, conservative text for an :class:`Event`: the message catalog renderers reuse.

A line states the literal transition and names entities as ``Name (domain:id)``; it never names a cause, and
literal save strings carried as attributes are not echoed. Exceptions: a rename quotes both names (the name is the
fact), a ``notification.*`` line quotes the game's log template identifier (the game's own statement, so evidence),
and inferred or narrative types name their reading, since that is the claim the event makes and the renderer marks
its status.
"""

from __future__ import annotations

from ..model.events import Event
from .registry import KINDS, kind_for

NOTIFICATION_PREFIX = "notification."
"""The types whose names come from the game's log templates."""


def describe_event(event: Event) -> str:
    """Deterministic ASCII text from the type's kind; a type no kind declares falls back to the type and its entities.

    ``notification.<template>`` types share one template, since the log template set is open-ended.
    """
    kind = kind_for(event.event_type)
    if kind is None:
        entities = ", ".join(ref.label() for ref in event.entities)
        return _ascii(f"{event.event_type}: {entities}")
    return _ascii(kind.template(event))


def known_event_types() -> frozenset[str]:
    """Every type an exact kind declares; ``notification.*`` excluded."""
    return frozenset(event_type for event_type, kind in KINDS.items() if not kind.is_prefix)


def _ascii(text: str) -> str:
    if text.isascii():
        return text
    return "".join(char if char.isascii() else f"\\u{ord(char):04x}" for char in text)
