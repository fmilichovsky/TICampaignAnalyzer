"""Technology and projects: the technology-milestone narrative event.

Narrative events are bookkeeping as constituents: the narrative event holding them states them in summary form.
"""

from __future__ import annotations

from ..model.events import Event, Role
from ..model.kinds import EventKind, EvidenceRole
from .text import attribute_text, has_role, role_label

# --- Narrative events (#325) ---------------------------------------------------------------------------------------


def _technology_milestone(event: Event) -> str:
    who = f"{role_label(event, Role.ACTOR)} completed" if has_role(event, Role.ACTOR) else "Completed"
    return f"{who} {attribute_text(event, 'template')}: {attribute_text(event, 'rationale')}"


TECHNOLOGY_MILESTONE = EventKind(
    "technology.milestone",
    _technology_milestone,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"template", "rationale"}),
)

NARRATIVE_KINDS = (TECHNOLOGY_MILESTONE,)
