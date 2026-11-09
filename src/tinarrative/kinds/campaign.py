"""Campaign-wide records: the first-milestone narrative event.

Narrative events are bookkeeping as constituents: the narrative event holding them states them in summary form.
"""

from __future__ import annotations

from ..model.events import Event, Role
from ..model.kinds import EventKind, EvidenceRole
from .text import attribute_text, role_label

# --- Narrative events (#325) ---------------------------------------------------------------------------------------


def _first_milestone(event: Event) -> str:
    return f"{role_label(event, Role.ACTOR)} recorded the campaign milestone {attribute_text(event, 'milestone')}"


FIRST_MILESTONE = EventKind(
    "campaign.first_milestone",
    _first_milestone,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"milestone", "faction"}),
)

NARRATIVE_KINDS = (FIRST_MILESTONE,)
