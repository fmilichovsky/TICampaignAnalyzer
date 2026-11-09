"""Armies and navies: the military build-up, demobilization and navy narrative events.

Narrative events are bookkeeping as constituents: the narrative event holding them states them in summary form.
"""

from __future__ import annotations

from ..model.events import Event, Role
from ..model.kinds import EventKind, EvidenceRole
from .text import attribute_label, count_label, role_label

# --- Narrative events (#325) ---------------------------------------------------------------------------------------


def _army_count(event: Event, change: str) -> str:
    return (
        f"{role_label(event, Role.ACTOR)} {change} its standard armies: "
        f"{attribute_label(event, 'before')} -> {attribute_label(event, 'after')}"
    )


def _military_buildup(event: Event) -> str:
    return _army_count(event, "built up")


def _demobilization(event: Event) -> str:
    return _army_count(event, "demobilized")


def _navy_established(event: Event) -> str:
    return (
        f"{role_label(event, Role.ACTOR)} established a navy ({count_label(event.attribute('navies'), 'naval army')})"
    )


_ARMY_COUNT = frozenset({"before", "after", "gdp_rank", "strength_rank"})

MILITARY_BUILDUP = EventKind(
    "nation.military_buildup", _military_buildup, None, EvidenceRole.BOOKKEEPING, required=_ARMY_COUNT
)
DEMOBILIZATION = EventKind(
    "nation.demobilization", _demobilization, None, EvidenceRole.BOOKKEEPING, required=_ARMY_COUNT
)
NAVY_ESTABLISHED = EventKind(
    "nation.navy_established",
    _navy_established,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"navies", "gdp_rank", "strength_rank"}),
)

NARRATIVE_KINDS = (MILITARY_BUILDUP, DEMOBILIZATION, NAVY_ESTABLISHED)
