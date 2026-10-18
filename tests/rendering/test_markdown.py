from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime

from tinarrative.model.changes import StateChange
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import Confidence, DateBasis, Event, EventSource, EventStatus, Significance
from tinarrative.model.evidence import Evidence, SourceLocation
from tinarrative.model.values import Observed
from tinarrative.rendering.markdown import render_sequence
from tinarrative.sequence import IntervalResult, SaveRef, SequencePlan

BEFORE = SaveRef("before.save", "a" * 64, datetime(2030, 1, 1))
AFTER = SaveRef("after.save", "b" * 64, datetime(2030, 2, 1))


def _render(
    objective: Iterable[Event] = (),
    *,
    inferred: Iterable[Event] | None = None,
    state_changes: Iterable[StateChange] | None = None,
    verbose: bool = False,
    min_significance: Significance = Significance.TRIVIAL,
) -> str:
    """Render one interval between ``BEFORE`` and ``AFTER``."""
    changes = None if state_changes is None else tuple(state_changes)
    interval = IntervalResult(
        index=0,
        key=AFTER.date,
        before=BEFORE,
        after=AFTER,
        changes=len(changes or ()),
        objective=tuple(objective),
        inferred=None if inferred is None else tuple(inferred),
        state_changes=changes,
    )
    plan = SequencePlan((BEFORE, AFTER), (BEFORE.date, AFTER.date), 2)
    return render_sequence(plan, [interval], verbose=verbose, min_significance=min_significance)


def _section(rendered: str, heading: str) -> str:
    """The body of one ``####`` section of the single interval."""
    body = rendered.split(f"\n#### {heading}\n", 1)[1]
    return body.split("\n#### ", 1)[0]


def _control_change() -> StateChange:
    return StateChange("politics", "controller", "Servants", "Resistance", _evidence(), _nation().entity_id)


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


def test_sequence_golden_lists_results_and_changes_by_category_and_is_deterministic() -> None:
    change = _control_change()
    event = _control_event(change)
    expected = (
        "# Save sequence\n\n## Saves\n\n"
        "1. `2030-01-01T00:00:00`: `before.save`\n2. `2030-02-01T00:00:00`: `after.save`\n\n"
        "2 saves given; ordered by serialized game time.\n\n## Intervals\n\n"
        "### 2030-01-01T00:00:00 to 2030-02-01T00:00:00\n\n- 1 state change\n\n"
        "#### Objective analyzer results\n\nPolitics:\n\n"
        '- nation:1 (null) controller: "Servants" -> "Resistance"\n\n'
        "#### State changes\n\nPolitics:\n\n"
        '- nation:1 controller: "Servants" -> "Resistance"\n'
    )
    assert _render([event], state_changes=[change]) == expected
    assert _render([event], state_changes=[change]) == _render([event], state_changes=[change])


def test_without_kept_changes_there_is_no_state_change_section() -> None:
    rendered = _render([_control_event(_control_change())])
    assert "#### State changes" not in rendered
    assert "- 0 state changes\n" in rendered


def test_an_empty_change_list_says_nothing_changed() -> None:
    rendered = _render(state_changes=[])
    assert rendered.endswith("\n#### State changes\n\nNo state changes were recorded.\n")
    assert "No objective analyzer results were recorded." in rendered


def test_state_changes_are_grouped_by_domain_and_never_filtered() -> None:
    politics = _control_change()
    economy = StateChange("nation_economy", "GDP", 1000.0, 1200.0, _evidence(), _nation().entity_id)
    rendered = _render(state_changes=[politics, economy], min_significance=Significance.CAMPAIGN_DEFINING)
    section = _section(rendered, "State changes")
    assert section.index("Nation Economy:") < section.index("Politics:")
    assert "- nation:1 GDP: 1000.0 -> 1200.0" in section
    assert '- nation:1 controller: "Servants" -> "Resistance"' in section


def test_verbose_output_includes_traceable_evidence() -> None:
    change = _control_change()
    rendered = _render([_control_event(change)], state_changes=[change], verbose=True)
    assert "event id: `e-1`" in rendered
    assert "  - significance: `minor`" in rendered
    changes = _section(rendered, "State changes")
    assert "  - evidence: Control changed" in changes
    assert "  - before source: `before / TINationState / 1 / /control`" in changes


def test_minimum_significance_omits_lesser_results_and_counts_them_once() -> None:
    change = _control_change()
    trivial = _control_event(change, event_id="e-trivial", significance=Significance.TRIVIAL)
    major = _control_event(change, event_id="e-major", significance=Significance.MAJOR)
    everything = _render([trivial, major])
    assert everything.count('- nation:1 (null) controller: "Servants" -> "Resistance"') == 2
    assert "omitted" not in everything
    rendered = _render([trivial, major], min_significance=Significance.MAJOR, verbose=True)
    assert "event id: `e-major`" in rendered and "event id: `e-trivial`" not in rendered
    assert rendered.endswith("\n1 objective analyzer result below major significance omitted.\n")


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


def test_without_inferred_events_there_is_no_inferred_section() -> None:
    assert "#### Inferred events" not in _render([_control_event(_control_change())])


def test_an_empty_inferred_section_says_nothing_was_inferred() -> None:
    rendered = _render(inferred=[])
    assert "\n#### Inferred events\n\nNo events were inferred.\n\n#### Objective analyzer results\n" in rendered


def test_inferred_events_name_confidence_alternatives_and_constituents_before_the_results() -> None:
    change = _control_change()
    objective = _control_event(change)
    plain = _inferred_event(change, event_id="i-1", constituents=("e-1", "e-missing"))
    ambiguous = _inferred_event(
        change, event_id="i-2", constituents=("e-1",), attributes=(("ambiguous", True), ("alternatives", ("i-1",)))
    )
    rendered = _render([objective], inferred=[ambiguous, plain])
    lines = _section(rendered, "Inferred events").rstrip("\n").splitlines()
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
    change = _control_change()
    objective = _control_event(change, significance=Significance.TRIVIAL)
    inferred = replace(_inferred_event(change, event_id="i-1", constituents=("e-1",)), significance=Significance.MINOR)
    rendered = _render([objective], inferred=[inferred], min_significance=Significance.MAJOR, verbose=True)
    section = _section(rendered, "Inferred events")
    assert "- " not in section
    assert section.endswith("\n1 inferred event below major significance omitted.\n")
    assert "1 objective analyzer result below major significance omitted." in rendered
