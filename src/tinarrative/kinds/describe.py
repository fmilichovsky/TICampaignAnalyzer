"""One-line, conservative text for an :class:`Event`: the message catalog renderers reuse.

A line states the literal transition and names entities as ``Name (domain:id)``; it never names a cause, and
literal save strings carried as attributes are not echoed. Exceptions: a rename quotes both names (the name is the
fact), a ``notification.*`` line quotes the game's log template identifier (the game's own statement, so evidence),
and inferred or narrative types name their reading, since that is the claim the event makes and the renderer marks
its status.
"""

from __future__ import annotations

from ..model.events import Event
from .registry import KINDS, kind_of


def describe_event(event: Event) -> str:
    """Deterministic ASCII text; an event type without a template falls back to the type and its entities.

    ``notification.<template>`` types share the one prefix kind, since the log template set is open-ended.
    """
    kind = kind_of(event.event_type)
    template = kind.template if kind is not None else None
    if template is None:
        entities = ", ".join(ref.label() for ref in event.entities)
        return _ascii(f"{event.event_type}: {entities}")
    return _ascii(template(event))


def known_event_types() -> frozenset[str]:
    """Every type a kind declares; ``notification.*`` excluded."""
    return frozenset(event_type for event_type, kind in KINDS.items() if not kind.prefix)


def _ascii(text: str) -> str:
    if text.isascii():
        return text
    return "".join(char if char.isascii() else f"\\u{ord(char):04x}" for char in text)
