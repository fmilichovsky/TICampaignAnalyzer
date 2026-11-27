"""Research completions, faction project lists, and the completions that are milestones."""

from __future__ import annotations

from ..model.events import Event, Role, Significance
from ..model.kinds import UNEXAMINED, EventKind, EvidenceRole, Rule
from ..model.values import Unknown
from .narrative import has_role, narrative_kind, role
from .text import attribute_label, attribute_text, plain, subject_label, transition_label


def _technology_completed(event: Event) -> str:
    text = f"{subject_label(event)} is listed as finished"
    if event.attribute("side") == "after":
        text += " (no earlier research state)"
    return text


def _technology_presence(event: Event) -> str:
    """``<tech> appeared, finished <flag>``: the type name already says the side, so the snapshot mechanics go."""
    verb = "appeared" if event.attribute("side") == "after" else "disappeared"
    return f"{subject_label(event)} {verb}, finished {attribute_label(event, 'finished')}"


def _finished_techs_changed(event: Event) -> str:
    """The subject is the technology and the member is its own name, so the member is not repeated."""
    if event.attribute("transition") == "unresolved":
        return f"{subject_label(event)} {transition_label(event, 'research finished techs list')}"
    verb = "added to" if event.attribute("transition") == "added" else "removed from"
    return f"{subject_label(event)} {verb} the research finished techs list"


def _project_completed(event: Event) -> str:
    return f"{subject_label(event)} lists project {attribute_label(event, 'project')} as finished"


def _finished_projects_changed(event: Event) -> str:
    if isinstance(event.attribute("member"), Unknown):
        return f"{subject_label(event)} {transition_label(event, 'finished project list')}"
    return (
        f"{subject_label(event)} had project {attribute_label(event, 'member')} removed from its finished project list"
    )


TECHNOLOGY_COMPLETED = EventKind(
    "technology.completed",
    _technology_completed,
    EvidenceRole.EVIDENCE,
    required=frozenset(),
    optional=frozenset({"side", "transition", "before", "after", "completions"}),
    rule=Rule.COMPLETION,
    base=Significance.MINOR,
    reason=UNEXAMINED,
)
TECHNOLOGY_FINISHED_CHANGED = EventKind(
    "technology.finished_changed",
    plain("finished"),
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"before", "after"}),
    base=Significance.MINOR,
    reason=UNEXAMINED,
)
TECHNOLOGY_APPEARED = EventKind(
    "technology.appeared",
    _technology_presence,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"side", "finished"}),
    base=Significance.TRIVIAL,
    reason=UNEXAMINED,
)
TECHNOLOGY_DISAPPEARED = EventKind(
    "technology.disappeared",
    _technology_presence,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"side", "finished"}),
    base=Significance.TRIVIAL,
    reason=UNEXAMINED,
)
RESEARCH_FINISHED_TECHS_CHANGED = EventKind(
    "research.finished_techs_changed",
    _finished_techs_changed,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
    base=Significance.TRIVIAL,
    reason=UNEXAMINED,
)
FACTION_PROJECT_COMPLETED = EventKind(
    "faction.project_completed",
    _project_completed,
    EvidenceRole.EVIDENCE,
    required=frozenset({"project"}),
    optional=frozenset({"completions"}),
    rule=Rule.COMPLETION,
    base=Significance.MINOR,
    reason=UNEXAMINED,
)
FACTION_FINISHED_PROJECT_NAMES_CHANGED = EventKind(
    "faction.finished_project_names_changed",
    _finished_projects_changed,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after", "count"}),
    base=Significance.MINOR,
    reason=UNEXAMINED,
)


def _milestone(event: Event) -> str:
    who = f"{role(event, Role.ACTOR)} completed" if has_role(event, Role.ACTOR) else "Completed"
    return f"{who} {attribute_text(event, 'template')}: {attribute_text(event, 'rationale')}"


MILESTONE = narrative_kind(
    "technology.milestone",
    _milestone,
    required=frozenset({"template", "rationale"}),
    base=Significance.MINOR,
    reason=UNEXAMINED,  # Only the fallback: a rule builds this kind for curated names, whose tier sets the level.
    rule=Rule.MILESTONE_TIER,
)

KINDS = (
    TECHNOLOGY_COMPLETED,
    TECHNOLOGY_FINISHED_CHANGED,
    TECHNOLOGY_APPEARED,
    TECHNOLOGY_DISAPPEARED,
    RESEARCH_FINISHED_TECHS_CHANGED,
    FACTION_PROJECT_COMPLETED,
    FACTION_FINISHED_PROJECT_NAMES_CHANGED,
    MILESTONE,
)
