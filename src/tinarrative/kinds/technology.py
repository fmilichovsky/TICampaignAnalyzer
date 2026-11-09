"""Technology and project completion, and the presence of name-keyed technology states.

A completion is narrator evidence: it dates what a milestone narrative event names. The other types are
bookkeeping the completion already states.
"""

from __future__ import annotations

from ..model.events import Event, Significance
from ..model.kinds import EventKind, EvidenceRole, Rule
from ..model.values import Unknown
from .text import TRANSITION, attribute_label, list_changed, plain, presence, subject_label, transition_label


def _technology_completed(event: Event) -> str:
    text = f"{subject_label(event)} is listed as finished"
    if event.attribute("side") == "after":
        text += " (no earlier research state)"
    return text


def _technology_presence(event: Event) -> str:
    return f"{subject_label(event)} (finished {attribute_label(event, 'finished')}) {presence(event)}"


def _project_completed(event: Event) -> str:
    return f"{subject_label(event)} lists project {attribute_label(event, 'project')} as finished"


def _finished_projects_changed(event: Event) -> str:
    if isinstance(event.attribute("member"), Unknown):
        return f"{subject_label(event)} {transition_label(event, 'finished project list')}"
    return f"{subject_label(event)} finished project list: -{attribute_label(event, 'member')}"


TECHNOLOGY_COMPLETED = EventKind(
    "technology.completed",
    _technology_completed,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=frozenset(),
    optional=TRANSITION | {"side"},
    rule=Rule.COMPLETION,
)
TECHNOLOGY_FINISHED_CHANGED = EventKind(
    "technology.finished_changed",
    plain("finished"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
)
TECHNOLOGY_APPEARED = EventKind(
    "technology.appeared",
    _technology_presence,
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"side", "finished"}),
)
TECHNOLOGY_DISAPPEARED = EventKind(
    "technology.disappeared",
    _technology_presence,
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"side", "finished"}),
)
RESEARCH_FINISHED_TECHS_CHANGED = EventKind(
    "research.finished_techs_changed",
    list_changed,
    Significance.TRIVIAL,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"member", "transition"}),
)
PROJECT_COMPLETED = EventKind(
    "faction.project_completed",
    _project_completed,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"project"}),
    optional=frozenset({"completions"}),
    rule=Rule.COMPLETION,
)
FINISHED_PROJECTS_CHANGED = EventKind(
    "faction.finished_project_names_changed",
    _finished_projects_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"before", "after", "member", "count"}),
)

KINDS = (
    TECHNOLOGY_COMPLETED,
    TECHNOLOGY_FINISHED_CHANGED,
    TECHNOLOGY_APPEARED,
    TECHNOLOGY_DISAPPEARED,
    RESEARCH_FINISHED_TECHS_CHANGED,
    PROJECT_COMPLETED,
    FINISHED_PROJECTS_CHANGED,
)
