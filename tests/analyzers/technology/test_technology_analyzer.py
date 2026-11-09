"""Technology events: completion (by value or by appearance), literal finished changes, presence, list leftovers."""

from tests.analyzers.support import AFTER, BEFORE, analyze, only, snapshot, technology_state
from tinarrative.analyzers.technology import TechnologyAnalyzer
from tinarrative.kinds.technology import (
    RESEARCH_FINISHED_TECHS_CHANGED,
    TECHNOLOGY_APPEARED,
    TECHNOLOGY_COMPLETED,
    TECHNOLOGY_DISAPPEARED,
    TECHNOLOGY_FINISHED_CHANGED,
)
from tinarrative.model.entities import IdentityConfidence
from tinarrative.model.events import Confidence, SourceRole
from tinarrative.model.snapshot import ResearchState, SaveSnapshot
from tinarrative.model.values import Observed, Unknown, freeze

ANALYZER = TechnologyAnalyzer()


def with_research(snap: SaveSnapshot, finished: Observed) -> SaveSnapshot:
    return SaveSnapshot(**{**snap.__dict__, "research": ResearchState(finished_techs_names=finished)})


def test_completion_by_value_cites_the_finished_list_and_progress_stays_in_the_diff() -> None:
    before = with_research(
        snapshot(
            BEFORE,
            technology_state("TechA", BEFORE, True),
            technology_state("TechB", BEFORE, False, freeze({"accumulatedResearch": 5.0})),
        ),
        ("TechA",),
    )
    after = with_research(
        snapshot(
            AFTER,
            technology_state("TechA", AFTER, True),
            technology_state("TechB", AFTER, True, freeze({"accumulatedResearch": 12.0})),
        ),
        ("TechA", "TechB"),
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.id == "technology.completed/technology:TechB" and event.confidence is Confidence.HIGH
    assert event.entities[0].confidence is IdentityConfidence.NAME_KEY
    assert dict(event.attributes) == {"transition": "changed", "before": False, "after": True}
    assert [(s.role, s.change.domain, s.change.field, s.member) for s in event.sources] == [
        (SourceRole.PRIMARY, "technology", "finished", None),
        (SourceRole.CORROBORATING, "research", "finished_techs_names", "TechB"),
    ]


def test_completion_by_appearance_and_progress_only_appearance_are_distinct() -> None:
    before = with_research(snapshot(BEFORE, technology_state("TechA", BEFORE, True)), ("TechA",))
    after = with_research(
        snapshot(
            AFTER,
            technology_state("TechA", AFTER, True),
            technology_state("TechC", AFTER, True),
            technology_state("TechE", AFTER, False, freeze({"accumulatedResearch": 1.0})),
        ),
        ("TechA", "TechC"),
    )
    events = analyze(ANALYZER, before, after)
    completed = only(events, TECHNOLOGY_COMPLETED.event_type)
    assert completed.id == "technology.completed/technology:TechC" and completed.attribute("side") == "after"
    assert [(s.role, s.change.field, s.member) for s in completed.sources] == [
        (SourceRole.PRIMARY, None, None),
        (SourceRole.CORROBORATING, "finished_techs_names", "TechC"),
    ]
    appeared = only(events, TECHNOLOGY_APPEARED.event_type)
    assert appeared.id == "technology.appeared/technology:TechE" and appeared.attribute("finished") is False
    assert len(appeared.sources) == 1
    assert len(events) == 2


def test_removed_names_and_reverted_flags_are_reported_literally() -> None:
    before = with_research(
        snapshot(BEFORE, technology_state("TechA", BEFORE, True), technology_state("TechD", BEFORE, True)),
        ("TechA", "TechD", "Ghost"),
    )
    after = with_research(
        snapshot(AFTER, technology_state("TechA", AFTER, False, freeze({"accumulatedResearch": 1.0}))),
        (),
    )
    events = analyze(ANALYZER, before, after)
    reverted = only(events, TECHNOLOGY_FINISHED_CHANGED.event_type)
    assert dict(reverted.attributes) == {"transition": "changed", "before": True, "after": False}
    assert [s.member for s in reverted.sources] == [None, "TechA"]
    gone = only(events, TECHNOLOGY_DISAPPEARED.event_type)
    assert gone.attribute("finished") is True and [s.member for s in gone.sources] == [None, "TechD"]
    ghost = only(events, RESEARCH_FINISHED_TECHS_CHANGED.event_type)
    assert ghost.id == "research.finished_techs_changed/Ghost/removed"
    assert ghost.sources[0].member == "Ghost" and str(ghost.entities[0].entity_id) == "technology:Ghost"
    assert len(events) == 3


def test_identical_snapshots_and_unknown_research_produce_nothing() -> None:
    before = with_research(snapshot(BEFORE, technology_state("TechA", BEFORE, True)), Unknown())
    after = with_research(snapshot(AFTER, technology_state("TechA", AFTER, True)), ("TechA",))
    assert analyze(ANALYZER, before, after) == []
    assert analyze(ANALYZER, before, before) == []
