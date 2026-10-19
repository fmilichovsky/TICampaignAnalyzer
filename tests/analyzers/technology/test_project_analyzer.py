"""Faction project events: one completion per name added to ``finishedProjectNames``, removals as list changes."""

from tests.analyzers.support import AFTER, BEFORE, analyze, snapshot, state
from tinarrative.analyzers.technology import ProjectAnalyzer
from tinarrative.analyzers.technology.projects import FINISHED_LIST_CHANGED, PROJECT_COMPLETED
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, SourceRole
from tinarrative.model.values import Unknown, UnknownReason, freeze

ANALYZER = ProjectAnalyzer()
FACTION = EntityDomain.FACTION


def test_each_added_name_is_a_completion_and_a_removed_name_a_list_change() -> None:
    before = snapshot(BEFORE, state(FACTION, "15", BEFORE, finishedProjectNames=("Project_A", "Project_B")))
    after = snapshot(AFTER, state(FACTION, "15", AFTER, finishedProjectNames=("Project_A", "Project_C", "Project_D")))
    events = analyze(ANALYZER, before, after)
    assert [(event.event_type, event.id) for event in events] == [
        (PROJECT_COMPLETED, "faction.project_completed/faction:15/Project_C"),
        (PROJECT_COMPLETED, "faction.project_completed/faction:15/Project_D"),
        (FINISHED_LIST_CHANGED, "faction.finished_project_names_changed/faction:15/Project_B/removed"),
    ]
    completed = events[0]
    assert dict(completed.attributes) == {"project": "Project_C"}
    assert [(s.role, s.change.field, s.member) for s in completed.sources] == [
        (SourceRole.PRIMARY, "finishedProjectNames", "Project_C")
    ]
    assert [str(ref.entity_id) for ref in completed.entities] == ["faction:15"]
    assert dict(events[2].attributes) == {"member": "Project_B", "transition": "removed"}


def test_a_list_that_cannot_be_compared_is_reported_once_and_an_unparseable_side_not_at_all() -> None:
    before = snapshot(BEFORE, state(FACTION, "15", BEFORE, finishedProjectNames=None))
    after = snapshot(AFTER, state(FACTION, "15", AFTER, finishedProjectNames=("Project_A",)))
    (event,) = analyze(ANALYZER, before, after)
    assert event.id == "faction.finished_project_names_changed/faction:15/set"
    assert event.confidence is Confidence.HIGH
    unparseable = Unknown(UnknownReason.UNPARSEABLE, freeze({"bad": 1}))
    after = snapshot(AFTER, state(FACTION, "15", AFTER, finishedProjectNames=unparseable))
    assert analyze(ANALYZER, before, after) == []


def test_a_repeatable_project_added_several_times_is_one_event_with_its_count() -> None:
    before = snapshot(BEFORE, state(FACTION, "15", BEFORE, finishedProjectNames=("Project_R", "Project_R")))
    after = snapshot(AFTER, state(FACTION, "15", AFTER, finishedProjectNames=("Project_R",) * 5))
    (event,) = analyze(ANALYZER, before, after)
    assert event.id == "faction.project_completed/faction:15/Project_R"
    assert dict(event.attributes) == {"project": "Project_R", "completions": 3}
