from __future__ import annotations

from datetime import datetime

from tinarrative.diff.state_diff import StateDiff
from tinarrative.model.changes import StateChange
from tinarrative.model.entities import EntityRef
from tinarrative.model.events import Confidence, Event, EventStatus
from tinarrative.model.evidence import Evidence
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.rendering.markdown import render_comparison


def _comparison(*changes: StateChange) -> StateDiff:
    return StateDiff(
        before=SaveSnapshot("before.save", "2030-01-01", "0.4", turn=12),
        after=SaveSnapshot("after.save", "2030-02-01", "0.4", timestamp=datetime(2030, 2, 1), turn=13),
        changes=list(changes),
    )


def _evidence() -> Evidence:
    return Evidence("after", "politics", "Control changed", "Servants", "Resistance", "nations/n-1/control")


def test_normal_markdown_golden_is_grouped_and_deterministic() -> None:
    change = StateChange("politics", "controller", "Servants", "Resistance", _evidence(), "n-1")
    event = Event(
        "e-1",
        "2030-02-01",
        "Faction control changed",
        EventStatus.OBJECTIVE,
        Confidence.HIGH,
        [_evidence()],
        [EntityRef("nation", "n-1", "Germany")],
    )
    expected = """# Save comparison

## Snapshots
- **Before:** date: `2030-01-01`; source: `before.save`; game version: `0.4`; turn: `12`; timestamp: `<unknown>`
- **After:** date: `2030-02-01`; source: `after.save`; game version: `0.4`; turn: `13`; timestamp: `2030-02-01 00:00:00`

## Changes

### Politics

Objective analyzer results:
- Faction control changed — affected: nation `Germany` (n-1)

Observed state changes:
- `controller` for `n-1`: `"Servants"` → `"Resistance"`
"""
    assert render_comparison(_comparison(change), [event]) == expected
    assert render_comparison(_comparison(change), [event]) == render_comparison(_comparison(change), [event])


def test_verbose_markdown_golden_includes_traceable_evidence() -> None:
    change = StateChange("politics", "controller", "Servants", "Resistance", _evidence(), "n-1")
    objective = Event(
        "e-1", "2030-02-01", "Faction control changed", EventStatus.OBJECTIVE, Confidence.HIGH, [_evidence()]
    )
    inferred = Event(
        "e-2", "2030-02-01", "A purge occurred", EventStatus.INFERRED, Confidence.LOW, attributes={"ambiguous": True}
    )
    rendered = render_comparison(_comparison(change), [inferred, objective], verbose=True)
    assert "event id: `e-1`" in rendered
    assert "path: `nations/n-1/control`" in rendered
    assert "[inferred, ambiguous] A purge occurred" in rendered
    assert "`<unknown>` marks unavailable normalized metadata." in rendered


def test_empty_diff_markdown_golden() -> None:
    rendered = render_comparison(_comparison())
    assert rendered.endswith("No state changes or objective analyzer results were recorded.\n")


def test_partially_normalized_snapshot_golden() -> None:
    comparison = StateDiff(SaveSnapshot("before.save", "<unknown>"), SaveSnapshot("after.save", "<unknown>"))
    rendered = render_comparison(comparison, verbose=True)
    assert "date: `<unknown>`" in rendered
    assert "game version: `<unknown>`" in rendered
    assert "turn: `<unknown>`" in rendered
