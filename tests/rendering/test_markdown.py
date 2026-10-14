from __future__ import annotations

from datetime import datetime

from tinarrative.diff.state_diff import StateDiff
from tinarrative.model.changes import StateChange
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import Confidence, DateBasis, Event, EventSource, EventStatus
from tinarrative.model.evidence import Evidence, SourceLocation
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.rendering.markdown import render_comparison


def _comparison(*changes: StateChange) -> StateDiff:
    return StateDiff(
        before=SaveSnapshot("before.save", "2030-01-01", "0.4", campaign_day=12),
        after=SaveSnapshot("after.save", "2030-02-01", "0.4", timestamp=datetime(2030, 2, 1), campaign_day=13),
        changes=changes,
    )


def _evidence() -> Evidence:
    return Evidence(
        "politics",
        "Control changed",
        "Servants",
        "Resistance",
        SourceLocation("before", "TINationState", 1, "/control"),
        SourceLocation("after", "TINationState", 1, "/control"),
    )


def _nation() -> EntityRef:
    return EntityRef(EntityId(EntityDomain.NATION, "1"), IdentityConfidence.IN_SAVE_ID, name="Germany")


def _control_event(change: StateChange, *, status: EventStatus = EventStatus.OBJECTIVE) -> Event:
    return Event(
        id="e-1",
        event_type="control_point.controller_changed",
        status=status,
        confidence=Confidence.HIGH,
        date="2030-02-01",
        date_basis=DateBasis.INTERVAL,
        not_before="2030-01-01",
        sources=(EventSource(change),),
        entities=(_nation(),),
        attributes=(("before", change.before), ("after", change.after)),
    )


def test_normal_markdown_golden_is_grouped_and_deterministic() -> None:
    change = StateChange("politics", "controller", "Servants", "Resistance", _evidence(), _nation().entity_id)
    event = _control_event(change)
    expected = (
        "# Save comparison\n\n## Snapshots\n"
        "- **Before:** date: `2030-01-01`; source: `before.save`; game version: `0.4`; "
        "campaign day: `12`; campaign quarter: `unknown (missing)`; timestamp: `<unknown>`\n"
        "- **After:** date: `2030-02-01`; source: `after.save`; game version: `0.4`; "
        "campaign day: `13`; campaign quarter: `unknown (missing)`; timestamp: `2030-02-01 00:00:00`\n"
        "\n## Changes\n\n### Politics\n\nObjective analyzer results:\n"
        '- nation:1 (null) controller: "Servants" -> "Resistance"\n\n'
        'Observed state changes:\n- nation:1 controller: "Servants" -> "Resistance"\n'
    )
    assert render_comparison(_comparison(change), [event]) == expected
    assert render_comparison(_comparison(change), [event]) == render_comparison(_comparison(change), [event])


def test_verbose_markdown_golden_includes_traceable_evidence() -> None:
    change = StateChange("politics", "controller", "Servants", "Resistance", _evidence(), _nation().entity_id)
    objective = _control_event(change)
    inferred = Event(
        id="e-2",
        event_type="A purge occurred",
        status=EventStatus.INFERRED,
        confidence=Confidence.LOW,
        date="2030-02-01",
        date_basis=DateBasis.INTERVAL,
        not_before="2030-01-01",
        sources=(EventSource(change),),
        entities=(_nation(),),
        attributes=(("ambiguous", True),),
    )
    rendered = render_comparison(_comparison(change), [inferred, objective], verbose=True)
    assert "event id: `e-1`" in rendered
    assert "before / TINationState / 1 / /control" in rendered
    assert "[inferred, ambiguous] A purge occurred" in rendered
    assert "`unknown (...)` marks unavailable or unresolved normalized data." in rendered


def test_empty_diff_markdown_golden() -> None:
    rendered = render_comparison(_comparison())
    assert rendered.endswith("No state changes or objective analyzer results were recorded.\n")


def test_partially_normalized_snapshot_golden() -> None:
    comparison = StateDiff(SaveSnapshot("before.save", "<unknown>"), SaveSnapshot("after.save", "<unknown>"))
    rendered = render_comparison(comparison, verbose=True)
    assert "date: `<unknown>`" in rendered
    assert "game version: `<unknown>`" in rendered
    assert "campaign day: `unknown (missing)`" in rendered
