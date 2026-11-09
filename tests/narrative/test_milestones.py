"""The curated milestone list: its shape and how a completion event names its template."""

from __future__ import annotations

from tests.narrative.support import atomic, faction, ref
from tinarrative.kinds import attributes
from tinarrative.kinds.technology import PROJECT_COMPLETED, TECHNOLOGY_COMPLETED
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Significance
from tinarrative.narrative.milestones import MILESTONE_TEMPLATES, completed_template, milestone_of

K1 = "2032-04-01T00:00:00"


def test_every_entry_has_a_rationale_and_a_tier_a_history_can_show() -> None:
    assert MILESTONE_TEMPLATES
    for name, milestone in MILESTONE_TEMPLATES.items():
        assert milestone.rationale.strip(), name
        assert milestone.significance.rank >= Significance.MINOR.rank, name


def test_names_are_save_template_names() -> None:
    for name in MILESTONE_TEMPLATES:
        assert name and not any(character.isspace() for character in name), name
        assert name.count("Project_") == (1 if name.startswith("Project_") else 0), name


def test_a_completion_names_its_technology_or_its_project() -> None:
    tech = atomic(
        "technology.completed/technology:SpaceNavies",
        K1,
        entities=[ref(EntityDomain.TECHNOLOGY, "SpaceNavies")],
        attributes=attributes(TECHNOLOGY_COMPLETED, side="after"),
    )
    project = atomic(
        "faction.project_completed/faction:15/Project_Warships",
        K1,
        entities=[faction("15")],
        attributes=attributes(PROJECT_COMPLETED, project="Project_Warships"),
    )
    other = atomic("fleet.disappeared/fleet:1", K1, entities=[ref(EntityDomain.FLEET, "1")])

    assert completed_template(tech) == "SpaceNavies"
    assert completed_template(project) == "Project_Warships"
    assert completed_template(other) is None
    assert milestone_of(project) is MILESTONE_TEMPLATES["Project_Warships"]
    assert milestone_of(other) is None
