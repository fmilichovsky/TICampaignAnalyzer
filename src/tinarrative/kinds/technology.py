"""Research completions and faction project lists."""

from __future__ import annotations

from ..model.events import Event, Significance
from ..model.kinds import EventKind, EvidenceRole, Rule
from ..model.values import Unknown
from .text import attribute_label, list_changed, plain, subject_label, transition_label


def _presence(event: Event) -> str:
    return (
        "is present only in the after snapshot"
        if event.attribute("side") == "after"
        else "is absent from the after snapshot"
    )


def _technology_completed(event: Event) -> str:
    text = f"{subject_label(event)} is listed as finished"
    if event.attribute("side") == "after":
        text += " (no earlier research state)"
    return text


def _technology_presence(event: Event) -> str:
    return f"{subject_label(event)} (finished {attribute_label(event, 'finished')}) {_presence(event)}"


def _project_completed(event: Event) -> str:
    return f"{subject_label(event)} lists project {attribute_label(event, 'project')} as finished"


def _finished_projects_changed(event: Event) -> str:
    if isinstance(event.attribute("member"), Unknown):
        return f"{subject_label(event)} {transition_label(event, 'finished project list')}"
    return f"{subject_label(event)} finished project list: -{attribute_label(event, 'member')}"


TECHNOLOGY_COMPLETED = EventKind(
    "technology.completed",
    _technology_completed,
    None,
    EvidenceRole.EVIDENCE,
    required=frozenset(),
    optional=frozenset({"side", "transition", "before", "after", "completions"}),
    rule=Rule.COMPLETION,
)
TECHNOLOGY_FINISHED_CHANGED = EventKind(
    "technology.finished_changed",
    plain("finished"),
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"before", "after"}),
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
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
)
FACTION_PROJECT_COMPLETED = EventKind(
    "faction.project_completed",
    _project_completed,
    None,
    EvidenceRole.EVIDENCE,
    required=frozenset({"project"}),
    optional=frozenset({"completions"}),
    rule=Rule.COMPLETION,
)
FACTION_FINISHED_PROJECT_NAMES_CHANGED = EventKind(
    "faction.finished_project_names_changed",
    _finished_projects_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after", "count"}),
)

KINDS = (
    TECHNOLOGY_COMPLETED,
    TECHNOLOGY_FINISHED_CHANGED,
    TECHNOLOGY_APPEARED,
    TECHNOLOGY_DISAPPEARED,
    RESEARCH_FINISHED_TECHS_CHANGED,
    FACTION_PROJECT_COMPLETED,
    FACTION_FINISHED_PROJECT_NAMES_CHANGED,
)
