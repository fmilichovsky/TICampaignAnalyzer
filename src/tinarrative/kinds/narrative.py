"""What every narrative-event kind shares: its level is set by the rule that emits it, it is bookkeeping when another
narrative event cites it, and its template names entities by role."""

from __future__ import annotations

from ..diff.render import render_value
from ..model.events import Event, Role
from ..model.kinds import EventKind, EvidenceRole, Template
from ..model.values import Observed

METRIC_SHIFTS_OMITTED = frozenset({"metric_shifts_omitted"})
"""How many shifts the bound cut; present only when it cut any."""


def narrative_kind(
    event_type: str,
    template: Template,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
    *,
    digests_members: bool = False,
) -> EventKind:
    """A kind whose level its rule sets; a kind with ``metric_shifts`` may also carry ``metric_shifts_omitted``."""
    if "metric_shifts" in required:
        optional |= METRIC_SHIFTS_OMITTED
    return EventKind(
        event_type,
        template,
        None,
        EvidenceRole.BOOKKEEPING,
        required,
        optional,
        digests_members=digests_members,
    )


def role(event: Event, wanted: Role) -> str:
    refs = [ref.label() for found, ref in event.roles if found is wanted]
    return ", ".join(refs) if refs else "null"


def has_role(event: Event, wanted: Role) -> bool:
    return any(found is wanted for found, _ in event.roles)


def count(value: Observed, noun: str) -> str:
    return f"{render_value(value)} {noun}{'' if value == 1 else 's'}"
