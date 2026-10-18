from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from tinarrative.diff.state_diff import StateDiff
from tinarrative.model.changes import StateChange
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import Confidence, DateBasis, Event, EventSource, EventStatus, Significance
from tinarrative.model.evidence import Evidence, SourceLocation
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.model.values import Observed
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


def _control_event(
    change: StateChange,
    *,
    status: EventStatus = EventStatus.OBJECTIVE,
    event_id: str = "e-1",
    significance: Significance = Significance.MINOR,
) -> Event:
    return Event(
        id=event_id,
        event_type="control_point.controller_changed",
        status=status,
        confidence=Confidence.HIGH,
        date="2030-02-01",
        date_basis=DateBasis.INTERVAL,
        not_before="2030-01-01",
        sources=(EventSource(change),),
        entities=(_nation(),),
        attributes=(("before", change.before), ("after", change.after)),
        significance=significance,
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
    assert "  - significance: `minor`" in rendered
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


def test_minimum_significance_omits_lesser_results_and_counts_them_once() -> None:
    change = StateChange("politics", "controller", "Servants", "Resistance", _evidence(), _nation().entity_id)
    trivial = _control_event(change, event_id="e-trivial", significance=Significance.TRIVIAL)
    major = _control_event(change, event_id="e-major", significance=Significance.MAJOR)
    everything = render_comparison(_comparison(change), [trivial, major])
    assert everything.count('- nation:1 (null) controller: "Servants" -> "Resistance"') == 2
    assert "omitted" not in everything
    rendered = render_comparison(
        _comparison(change), [trivial, major], min_significance=Significance.MAJOR, verbose=True
    )
    assert "event id: `e-major`" in rendered and "event id: `e-trivial`" not in rendered
    assert "\n1 objective analyzer result below major significance omitted.\n" in rendered
    assert rendered.index("Observed state changes:") < rendered.index("omitted") < rendered.index("## Rendering notes")
    only_changes = render_comparison(_comparison(change), [trivial], min_significance=Significance.MINOR)
    assert "Objective analyzer results:" not in only_changes and "### Politics" in only_changes
    assert "1 objective analyzer result below minor significance omitted." in only_changes


def _inferred_event(
    change: StateChange,
    *,
    event_id: str,
    constituents: tuple[str, ...],
    attributes: tuple[tuple[str, Observed], ...] = (),
) -> Event:
    return Event(
        id=event_id,
        event_type="fixture.inferred",
        status=EventStatus.INFERRED,
        confidence=Confidence.MEDIUM,
        date="2030-02-01",
        date_basis=DateBasis.INTERVAL,
        not_before="2030-01-01",
        sources=(EventSource(change),),
        entities=(_nation(),),
        attributes=attributes,
        significance=Significance.MAJOR,
        constituents=constituents,
    )


def test_without_inferred_events_the_report_is_unchanged() -> None:
    change = StateChange("politics", "controller", "Servants", "Resistance", _evidence(), _nation().entity_id)
    event = _control_event(change)
    plain = render_comparison(_comparison(change), [event])
    assert render_comparison(_comparison(change), [event], inferred=None) == plain
    assert "## Inferred events" not in plain


def test_an_empty_inferred_section_says_nothing_was_inferred() -> None:
    rendered = render_comparison(_comparison(), inferred=[])
    assert "\n## Inferred events\n\nNo events were inferred.\n\n## Changes\n" in rendered


def test_inferred_events_name_confidence_alternatives_and_constituents_before_the_changes() -> None:
    change = StateChange("politics", "controller", "Servants", "Resistance", _evidence(), _nation().entity_id)
    objective = _control_event(change)
    plain = _inferred_event(change, event_id="i-1", constituents=("e-1", "e-missing"))
    ambiguous = _inferred_event(
        change, event_id="i-2", constituents=("e-1",), attributes=(("ambiguous", True), ("alternatives", ("i-1",)))
    )
    rendered = render_comparison(_comparison(change), [objective], inferred=[ambiguous, plain])
    section = rendered.split("## Inferred events\n", 1)[1].split("\n## Changes\n", 1)[0]
    lines = section.splitlines()
    assert lines[1] == "Reconstructed from the objective results below; never observed directly."
    first, second = (index for index, line in enumerate(lines) if line.startswith("- "))
    assert lines[first].endswith(" (confidence: `medium`)") and not lines[first].startswith("- [ambiguous]")
    assert lines[first + 1 : second] == [
        '  - from `e-1`: nation:1 (null) controller: "Servants" -> "Resistance"',
        "  - from `e-missing`",
    ]
    assert lines[second].startswith("- [ambiguous] ")
    assert lines[second + 1 :] == [
        "  - alternatives: `i-1`",
        '  - from `e-1`: nation:1 (null) controller: "Servants" -> "Resistance"',
    ]


def test_inferred_events_below_the_minimum_are_counted_in_their_own_section() -> None:
    change = StateChange("politics", "controller", "Servants", "Resistance", _evidence(), _nation().entity_id)
    objective = _control_event(change, significance=Significance.TRIVIAL)
    inferred = replace(_inferred_event(change, event_id="i-1", constituents=("e-1",)), significance=Significance.MINOR)
    rendered = render_comparison(
        _comparison(change), [objective], inferred=[inferred], min_significance=Significance.MAJOR, verbose=True
    )
    section = rendered.split("## Inferred events\n", 1)[1].split("\n## Changes\n", 1)[0]
    assert "- " not in section
    assert section.endswith("\n1 inferred event below major significance omitted.\n")
    assert "1 objective analyzer result below major significance omitted." in rendered
