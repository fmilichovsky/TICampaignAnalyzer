"""One-line, conservative text for an :class:`Event`: the message catalog renderers reuse.

A line states the literal transition and names entities as ``Name (domain:id)``; it never names a cause, and
literal save strings carried as attributes are not echoed. Exceptions: a rename quotes both names (the name is the
fact), a ``notification.*`` line quotes the game's log template identifier (the game's own statement, so evidence),
and inferred or narrative types name their reading, since that is the claim the event makes and the renderer marks
its status.
"""

from __future__ import annotations

from collections.abc import Callable

from ..diff.render import render_value
from ..model.entities import EntityDomain
from ..model.events import Event, Role
from .registry import KINDS, kind_of
from .text import attribute_label as _attr
from .text import attribute_text as _text
from .text import entity_of as _entity
from .text import name_of as _name
from .text import refs as _refs
from .text import subject_label as _subject


def describe_event(event: Event) -> str:
    """Deterministic ASCII text; an event type without a template falls back to the type and its entities.

    The kind's template, else the type's entry in the table not yet migrated to kinds. ``notification.<template>``
    types share the one prefix kind, since the log template set is open-ended.
    """
    kind = kind_of(event.event_type)
    template = kind.template if kind is not None else _TEMPLATES.get(event.event_type)
    if template is None:
        entities = ", ".join(ref.label() for ref in event.entities)
        return _ascii(f"{event.event_type}: {entities}")
    return _ascii(template(event))


def known_event_types() -> frozenset[str]:
    """Every type a kind declares or the table not yet migrated to kinds describes; ``notification.*`` excluded."""
    return frozenset(event_type for event_type, kind in KINDS.items() if not kind.prefix) | frozenset(_TEMPLATES)


def _ascii(text: str) -> str:
    if text.isascii():
        return text
    return "".join(char if char.isascii() else f"\\u{ord(char):04x}" for char in text)


def _hab_established(event: Event) -> str:
    faction = _name(_entity(event, EntityDomain.FACTION))
    return f"{_subject(event)} ({faction}) became operational at {_attr(event, 'body')}"


def _first_hab_on_body(event: Event) -> str:
    count = event.attribute("hab_count")
    habs = f"{render_value(count)} hab{'' if count == 1 else 's'}"
    first = ", the first of any faction there" if event.attribute("first_of_any_faction") is True else ""
    return f"{_subject(event)} established its first presence on {_attr(event, 'body')} ({habs}{first})"


def _hab_destroyed(event: Event) -> str:
    where = f"(type {_attr(event, 'hab_type')} at {_attr(event, 'body')})"
    if event.attribute("ambiguous") is True:
        return (
            f"{_subject(event)} {where} was destroyed by {_refs(event, 'destroyers')}: one of "
            f"{_attr(event, 'candidates')} recorded destructions for {_attr(event, 'vanished')} vanished habs"
        )
    return f"{_subject(event)} {where} was destroyed by {_attr(event, 'destroyer')} on {_text(event, 'recorded_on')}"


def _battle_outcome(event: Event) -> str:
    text = f"{_subject(event)} inflicted {_attr(event, 'kill_count')} kills on {_attr(event, 'victim')}"
    losses = [
        f"{render_value(count)} {label}{'' if count == 1 else 's'}"
        for name, label in (("habs_lost", "hab"), ("fleets_lost", "fleet"))
        if (count := event.attribute(name))
    ]
    if losses:
        text += f", which lost {' and '.join(losses)}"
    won, lost = event.attribute("combats_won"), event.attribute("combats_lost")
    if won or lost:
        text += f"; recorded combats won {render_value(won)}, lost {render_value(lost)}"
    return text


def _role(event: Event, role: Role) -> str:
    refs = [ref.label() for found, ref in event.roles if found is role]
    return ", ".join(refs) if refs else "null"


_TEMPLATES: dict[str, Callable[[Event], str]] = {
    # The types not yet migrated to a kind.
    "hab.established": _hab_established,
    "faction.first_hab_on_body": _first_hab_on_body,
    "hab.destroyed": _hab_destroyed,
    "faction.battle_outcome": _battle_outcome,
}
