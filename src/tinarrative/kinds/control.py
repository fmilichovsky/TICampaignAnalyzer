"""Control of nations by factions: the takeover narrative events.

Narrative events are bookkeeping as constituents: the narrative event holding them states them in summary form.
"""

from __future__ import annotations

from ..model.events import Event, Role
from ..model.kinds import EventKind, EvidenceRole
from .text import METRIC_SHIFTS, METRIC_SHIFTS_OMITTED, count_label, has_role, refs_label, role_label

# --- Narrative events (#325) ---------------------------------------------------------------------------------------


def _takeover(event: Event) -> str:
    text = f"{role_label(event, Role.ACTOR)} took control of {role_label(event, Role.TARGET)}"
    if has_role(event, Role.LOSER):
        text += f" from {role_label(event, Role.LOSER)}"
    if event.attribute("consolidated") is True:
        text += " and holds every control point"
    return text


def _takeover_wave(event: Event) -> str:
    return (
        f"{role_label(event, Role.ACTOR)} took control of {refs_label(event, 'nations')} in quick succession "
        f"({count_label(event.attribute('count'), 'takeover')})"
    )


TAKEOVER = EventKind(
    "faction.takeover",
    _takeover,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"scopes", "cause", "executive_recorded_on", "previous_executive", "consolidated", "gdp_rank"})
    | METRIC_SHIFTS,
    optional=METRIC_SHIFTS_OMITTED,
)
TAKEOVER_WAVE = EventKind(
    "faction.takeover_wave",
    _takeover_wave,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"nations", "count"}),
    digests_members=True,
)

NARRATIVE_KINDS = (TAKEOVER, TAKEOVER_WAVE)
