"""Shared helpers for the reconstruction tests: running the pipeline up to inference and its provenance checks."""

from __future__ import annotations

from tests.analyzers.support import only as only
from tinarrative.analyzers import ALL_ANALYZERS, run_analyzers
from tinarrative.kinds import describe_event
from tinarrative.model.changes import StateDiff
from tinarrative.model.events import Event, EventStatus, Significance, SourceRole
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.narrative import assign_significance
from tinarrative.reconstruction import infer_events

Scenario = tuple[SaveSnapshot, SaveSnapshot, StateDiff]


def run(scenario: Scenario) -> tuple[tuple[Event, ...], list[Event]]:
    before, after, diff = scenario
    objective = run_analyzers(ALL_ANALYZERS, before, after, diff)
    return objective, infer_events(objective, before, after, diff)


def assert_traceable(scenario: Scenario) -> None:
    """Every inferred event is inferred, rests on input events, cites all their sources and only diff changes,
    has a primary source, and the output is deterministic."""
    objective, inferred = run(scenario)
    assert inferred
    by_id = {event.id: event for event in objective}
    diff_changes = set(scenario[2].changes)
    for event in inferred:
        assert event.status is EventStatus.INFERRED
        assert event.constituents and set(event.constituents) <= set(by_id)
        cited = {source.change for source in event.sources}
        assert cited <= diff_changes
        for constituent in event.constituents:
            assert {source.change for source in by_id[constituent].sources} <= cited
        assert any(source.role is SourceRole.PRIMARY for source in event.sources)
    assert infer_events(objective, *scenario) == inferred
    assert infer_events((*objective, *inferred), *scenario) == inferred  # inferred input is ignored


def lines_of(scenario: Scenario) -> dict[str, tuple[str, Significance]]:
    before, after, _ = scenario
    _, inferred = run(scenario)
    return {
        event.id: (describe_event(event), event.significance) for event in assign_significance(inferred, before, after)
    }
