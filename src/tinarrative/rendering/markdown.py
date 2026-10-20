"""Deterministic Markdown rendering for an already-analyzed save sequence.

This module presents analyzer output, already-reconstructed inferred events, already-aggregated narrative
events and, when supplied, the literal state changes of each interval; it never compares snapshots or infers
facts itself.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Final, Literal

from ..analyzers.render import describe_event, render_event_value
from ..diff.render import render_change, render_value
from ..grouping import CampaignGroup
from ..model.changes import StateChange
from ..model.entities import EntityRef
from ..model.events import Event, EventSource, EventStatus, Significance
from ..model.evidence import Evidence, SourceLocation
from ..model.values import Observed, Unknown
from ..sequence import IntervalResult, SequencePlan

Period = Literal["year", "half", "quarter"]
PERIODS: Final[tuple[Period, ...]] = ("year", "half", "quarter")

_ATTRIBUTE_NAMES: Final = (
    "war",
    "shared_federation",
    "cause",
    "mode",
    "region_count",
    "duration_days",
    "milestone",
    "hull",
    "count",
    "template",
)
"""The attributes a narrative line summarises, in order; ``metric_shifts`` leads as a count. Reference lists are left
to the roles and the JSON."""


def _inferred_lines(
    inferred: Iterable[Event], by_id: Mapping[str, Event], *, verbose: bool, min_significance: Significance
) -> list[str]:
    """The body of an inferred-events section; ``by_id`` resolves the objective constituents."""
    candidates = list(inferred)
    listed = sorted(
        (event for event in candidates if event.significance.rank >= min_significance.rank),
        key=lambda event: event.sort_key,
    )
    if not candidates:
        return ["No events were inferred."]
    lines = ["Reconstructed from the objective results below; never observed directly."]
    if listed:
        lines.append("")
    for event in listed:
        ambiguous = event.attribute("ambiguous") is True
        marker = "[ambiguous] " if ambiguous else ""
        lines.append(f"- {marker}{describe_event(event)} (confidence: `{event.confidence}`)")
        alternatives = event.attribute("alternatives")
        if ambiguous and isinstance(alternatives, tuple) and alternatives:
            lines.append("  - alternatives: " + ", ".join(f"`{alternative}`" for alternative in alternatives))
        for constituent in event.constituents:
            source = by_id.get(constituent)
            suffix = f": {describe_event(source)}" if source is not None else ""
            lines.append(f"  - from `{constituent}`{suffix}")
        if verbose:
            lines.extend(_event_lines(event, verbose=True)[1:])
    omitted = len(candidates) - len(listed)
    if omitted:
        noun = "event" if omitted == 1 else "events"
        lines.extend(["", f"{omitted} inferred {noun} below {min_significance.value} significance omitted."])
    return lines


def render_sequence(
    plan: SequencePlan,
    intervals: Sequence[IntervalResult],
    *,
    verbose: bool = False,
    min_significance: Significance = Significance.TRIVIAL,
    campaign: CampaignGroup | None = None,
    left_out: int = 0,
    narrative: Sequence[Event] | None = None,
    changed_settings: Mapping[str, object] | None = None,
    period: Period = "year",
) -> str:
    """Render the saves of a sequence in chronological order and the analyzer results of each interval.

    With a ``campaign``, a section first names the campaign the saves were grouped into and the signals it rests on;
    ``left_out`` counts the given saves that belong to other campaigns. Each interval lists its inferred events (when
    they were reconstructed), its objective analyzer results of at least ``min_significance`` grouped by category and,
    when they were kept, its literal state changes grouped by category. State changes are never filtered. Event IDs
    are the sequence-qualified ones. With ``narrative``, a section above the intervals lists the narrative events of
    at least ``min_significance`` by the ``period`` (year, half or quarter) they start in, and names the
    ``changed_settings`` (dotted key to value) it was built with when they differ from the defaults. An interval with
    nothing to list at ``min_significance`` (and no state changes) is a single line.
    """
    lines = ["# Save sequence", ""]
    if campaign is not None:
        lines.extend(_campaign_lines(campaign, left_out))
    lines.extend(["## Saves", ""])
    previous: datetime | None = None
    for position, (key, save) in enumerate(zip(plan.keys, plan.saves, strict=True), start=1):
        details = f"{position}. `{key}`: `{save.source}`"
        if save.aliases:
            details += " (identical: " + ", ".join(f"`{alias}`" for alias in save.aliases) + ")"
        if previous is not None and previous == save.timestamp:
            details += " (same game time as the previous save, different bytes; ordered by path)"
        lines.append(details)
        previous = save.timestamp
    summary = f"{plan.inputs} {'save' if plan.inputs == 1 else 'saves'} given"
    if plan.duplicates:
        summary += f", {plan.duplicates} byte-identical {'copy' if plan.duplicates == 1 else 'copies'} merged"
    if plan.skipped:
        summary += f", {len(plan.skipped)} skipped"
    lines.extend(["", summary + "; ordered by serialized game time."])
    if plan.skipped:
        lines.extend(["", "Skipped (inside a given directory, not a usable save):", ""])
        lines.extend(f"- `{skipped.source}`: {skipped.error_class}: {skipped.error}" for skipped in plan.skipped)

    if narrative is not None:
        lines.extend(["", "## Narrative", ""])
        if changed_settings:
            listed = ", ".join(f"`{key} = {value}`" for key, value in sorted(changed_settings.items()))
            lines.extend([f"Built with non-default settings: {listed}.", ""])
        lines.extend(_narrative_lines(narrative, verbose=verbose, min_significance=min_significance, period=period))

    lines.extend(["", "## Intervals"])
    if not intervals:
        lines.extend(["", "Fewer than two distinct saves; no interval was compared."])
    for interval in intervals:
        if _collapsed(interval, min_significance):
            line = _collapsed_line(interval, min_significance)
            lines.extend([line] if lines[-1].startswith("- `") else ["", line])
            continue
        lines.extend(["", f"### {interval.before.date} to {interval.after.date}", ""])
        lines.append(f"- {interval.changes} state {'change' if interval.changes == 1 else 'changes'}")
        if interval.inferred is not None:
            by_id = {event.id: event for event in interval.objective}
            lines.extend(["", "#### Inferred events", ""])
            lines.extend(_inferred_lines(interval.inferred, by_id, verbose=verbose, min_significance=min_significance))
        lines.extend(_objective_lines(interval.objective, verbose=verbose, min_significance=min_significance))
        if interval.state_changes is not None:
            lines.extend(_state_change_lines(interval.state_changes, verbose=verbose))
    return "\n".join(lines) + "\n"


def _listed(events: Iterable[Event] | None, min_significance: Significance) -> int:
    return sum(event.significance.rank >= min_significance.rank for event in events or ())


def _collapsed(interval: IntervalResult, min_significance: Significance) -> bool:
    """Whether a filtered interval lists nothing: no inferred or objective event at the level, no changes.

    Without a filter (``trivial``) every interval keeps its section, so an empty one still says what was not found."""
    return (
        min_significance is not Significance.TRIVIAL
        and interval.state_changes is None
        and not _listed(interval.inferred, min_significance)
        and not _listed(interval.objective, min_significance)
    )


def _collapsed_line(interval: IntervalResult, min_significance: Significance) -> str:
    omitted = len(interval.objective) + len(interval.inferred or ())
    changes = f"{interval.changes} state {'change' if interval.changes == 1 else 'changes'}"
    events = f"{omitted} {'event' if omitted == 1 else 'events'} below {min_significance.value} significance omitted"
    return f"- `{interval.before.date}` to `{interval.after.date}`: nothing listed ({changes}; {events})"


def _period_heading(start: Observed, period: Period) -> str:
    """``2032``, ``2032 H1`` or ``2032 Q1`` for a start date; ``Undated`` when the start is not a date."""
    if not isinstance(start, str) or len(start) < 7 or not start[:4].isdigit() or not start[5:7].isdigit():
        return "Undated"
    month = int(start[5:7])
    if period == "half":
        return f"{start[:4]} H{(month - 1) // 6 + 1}"
    if period == "quarter":
        return f"{start[:4]} Q{(month - 1) // 3 + 1}"
    return start[:4]


def _attribute_summary(event: Event) -> str:
    parts: list[str] = []
    shifts = event.attribute("metric_shifts")
    if isinstance(shifts, tuple) and shifts:
        parts.append(f"metric_shifts: {len(shifts)}")
    for name in _ATTRIBUTE_NAMES:
        value = event.attribute(name)
        if not isinstance(value, Unknown) and value is not None and value != ():
            parts.append(f"{name}: `{render_event_value(value)}`")
    return "; ".join(parts)


def _narrative_lines(
    narrative: Sequence[Event], *, verbose: bool, min_significance: Significance, period: Period = "year"
) -> list[str]:
    """Narrative events by the period they start in (undated first), each with span, roles, attributes and sources."""
    if not narrative:
        return ["No narrative events were built."]
    listed = sorted(
        (event for event in narrative if event.significance.rank >= min_significance.rank),
        key=lambda event: event.sort_key,
    )
    lines = ["Aggregated from the events of every interval below."]
    heading: str | None = None
    for event in listed:
        current = _period_heading(event.start, period)
        if current != heading:
            lines.extend(["", f"### {current}", ""])
            heading = current
        span = f"`{_date(event.start)}` to `{_date(event.end)}`"
        state = f"{event.status.value}, confidence `{event.confidence}`, significance `{event.significance}`"
        lines.append(f"- {span}{' (open)' if event.open else ''}: {describe_event(event)} ({state})")
        if event.roles:
            lines.append("  - roles: " + "; ".join(f"{role.value}: {ref.label()}" for role, ref in event.roles))
        summary = _attribute_summary(event)
        if summary and not verbose:
            lines.append(f"  - attributes: {summary}")
        lines.extend(f"  - from `{constituent}`" for constituent in event.constituents)
        if verbose:
            lines.extend(_event_lines(event, verbose=True)[1:])
    omitted = len(narrative) - len(listed)
    if omitted:
        noun = "event" if omitted == 1 else "events"
        lines.extend(["", f"{omitted} narrative {noun} below {min_significance.value} significance omitted."])
    return lines


def _date(value: Observed) -> str:
    return value if isinstance(value, str) else render_value(value)


def _campaign_lines(campaign: CampaignGroup, left_out: int) -> list[str]:
    """The campaign the saves were grouped into; grouping is inference, so its signals are shown."""
    started = "unknown" if campaign.started is None else f"`{campaign.started:%Y-%m-%d %H:%M:%S}`"
    lines = [
        "## Campaign",
        "",
        f"- key: `{campaign.key}`",
        f"- player faction: {campaign.faction_name or 'unknown'}",
        f"- scenario: `{campaign.scenario_label}`",
        f"- real-world start: {started}",
        "",
    ]
    if campaign.unclassified:
        basis = f"Not grouped: {campaign.unclassified_reason}."
    elif campaign.started is None:
        basis = "Grouped by matching human faction, faction name and scenario; no real-world start was found."
    else:
        basis = "Grouped by matching human faction, faction name, scenario and real-world start."
    if left_out:
        basis += f" {left_out} given {'save belongs' if left_out == 1 else 'saves belong'} to other campaigns."
    lines.extend([basis, ""])
    return lines


def _objective_lines(events: Iterable[Event], *, verbose: bool, min_significance: Significance) -> list[str]:
    objective = [event for event in events if event.status is EventStatus.OBJECTIVE]
    listed = sorted(
        (event for event in objective if event.significance.rank >= min_significance.rank),
        key=lambda event: event.sort_key,
    )
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in listed:
        grouped[_event_category(event)].append(event)
    lines = ["", "#### Objective analyzer results"]
    if not objective:
        lines.extend(["", "No objective analyzer results were recorded."])
    for category in sorted(grouped, key=str.casefold):
        lines.extend(["", f"{category}:", ""])
        for event in grouped[category]:
            lines.extend(_event_lines(event, verbose=verbose))
    omitted = len(objective) - len(listed)
    if omitted:
        noun = "result" if omitted == 1 else "results"
        lines.extend(["", f"{omitted} objective analyzer {noun} below {min_significance.value} significance omitted."])
    return lines


def _state_change_lines(changes: Iterable[StateChange], *, verbose: bool) -> list[str]:
    grouped: dict[str, list[StateChange]] = defaultdict(list)
    for change in changes:
        grouped[_change_category(change)].append(change)
    lines = ["", "#### State changes"]
    if not grouped:
        lines.extend(["", "No state changes were recorded."])
    for category in sorted(grouped, key=str.casefold):
        lines.extend(["", f"{category}:", ""])
        for change in sorted(grouped[category], key=lambda change: change.sort_key):
            lines.extend(_change_lines(change, verbose=verbose))
    return lines


def render_events(events: list[Event]) -> str:
    """Render the original deterministic event-list API."""
    return "\n".join(
        f"- {render_value(event.date)}: {event.event_type}"
        for event in sorted(events, key=lambda event: event.sort_key)
    )


def _event_lines(event: Event, *, verbose: bool) -> list[str]:
    lines = [f"- {describe_event(event)}"]
    if verbose:
        lines.extend(
            [
                f"  - event id: `{event.id}`",
                f"  - date: `{event.date}`",
                f"  - confidence: `{event.confidence}`",
                f"  - significance: `{event.significance}`",
            ]
        )
        lines.extend(_entity_lines(event.entities, indent="  "))
        lines.extend(_event_source_lines(event.sources, indent="  "))
        if event.attributes:
            attributes = "; ".join(f"{name}: `{render_event_value(value)}`" for name, value in event.attributes)
            lines.append(f"  - attributes: {attributes}")
    return lines


def _change_lines(change: StateChange, *, verbose: bool) -> list[str]:
    lines = [f"- {render_change(change)}"]
    if verbose:
        lines.append(f"  - evidence: {change.evidence.description}")
        lines.extend(_evidence_lines(change.evidence, indent="  "))
    return lines


def _entity_lines(entities: Iterable[EntityRef], *, indent: str) -> list[str]:
    rendered = _entities(entities)
    return [f"{indent}- affected entities: {rendered}"] if rendered else []


def _entities(entities: Iterable[EntityRef]) -> str:
    ordered = sorted(entities, key=lambda entity: entity.entity_id.sort_key)
    return ", ".join(entity.label() for entity in ordered)


def _event_source_lines(sources: Iterable[EventSource], *, indent: str) -> list[str]:
    lines: list[str] = []
    for source in sorted(sources, key=lambda source: source.sort_key):
        lines.append(f"{indent}- source ({source.role.value}): {render_change(source.change)}")
        lines.extend(_evidence_lines(source.change.evidence, indent=indent + "  "))
        if source.entry is not None:
            lines.append(f"{indent}  - record entry: `{_location(source.entry)}`")
    return lines


def _evidence_lines(evidence: Evidence, *, indent: str) -> list[str]:
    return [
        f"{indent}- before source: `{_location(evidence.before_location)}`",
        f"{indent}- after source: `{_location(evidence.after_location)}`",
    ]


def _location(location: SourceLocation | None) -> str:
    if location is None:
        return "absent"
    parts = [location.save_id]
    if location.state_type is not None:
        parts.append(location.state_type)
    if location.map_id is not None:
        parts.append(str(location.map_id))
    if location.path is not None:
        parts.append(location.path)
    return " / ".join(parts)


def _event_category(event: Event) -> str:
    category = event.attribute("category")
    if isinstance(category, str) and category:
        return category
    domains = {source.change.domain for source in event.sources}
    return next(iter(domains)).replace("_", " ").title() if len(domains) == 1 else "Analyzer results"


def _change_category(change: StateChange) -> str:
    return change.domain.replace("_", " ").title()
