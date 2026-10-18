"""Deterministic Markdown rendering for one already-analyzed comparison.

This module presents a diff, analyzer output and, when supplied, already-reconstructed
inferred events; it never compares snapshots or infers facts itself.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from ..analyzers.render import describe_event
from ..diff.render import render_change, render_value
from ..diff.state_diff import StateDiff
from ..model.changes import StateChange
from ..model.entities import EntityRef
from ..model.events import Event, EventSource, EventStatus, Significance
from ..model.evidence import Evidence, SourceLocation
from ..model.snapshot import SaveSnapshot


def render_comparison(
    comparison: StateDiff,
    events: Iterable[Event] = (),
    *,
    inferred: Iterable[Event] | None = None,
    verbose: bool = False,
    min_significance: Significance = Significance.TRIVIAL,
) -> str:
    """Render one comparison and supplied analyzer results as deterministic Markdown.

    Normal output includes only objective analyzer results of at least ``min_significance`` (the default
    keeps every level); the number omitted is stated once. Verbose output also identifies inferred results
    omitted from this factual comparison report.

    ``inferred`` events, when supplied, get their own section before the changes, filtered by the same
    ``min_significance`` with their own omitted count; each names the objective results it rests on.
    """
    event_list = list(events)
    objective = [event for event in event_list if event.status is EventStatus.OBJECTIVE]
    objective_events = sorted(
        (event for event in objective if event.significance.rank >= min_significance.rank),
        key=lambda event: event.sort_key,
    )
    omitted = len(objective) - len(objective_events)
    grouped_changes: dict[str, list[StateChange]] = defaultdict(list)
    grouped_events: dict[str, list[Event]] = defaultdict(list)
    for change in comparison.changes:
        grouped_changes[_change_category(change)].append(change)
    for event in objective_events:
        grouped_events[_event_category(event)].append(event)

    categories = sorted(set(grouped_changes) | set(grouped_events), key=str.casefold)
    lines = ["# Save comparison", "", "## Snapshots", *_snapshot_lines("Before", comparison.before)]
    lines.extend(_snapshot_lines("After", comparison.after))
    if inferred is not None:
        lines.extend(_inferred_section(inferred, objective, verbose=verbose, min_significance=min_significance))
    if not categories:
        lines.extend(["", "## Changes", "", "No state changes or objective analyzer results were recorded."])
    else:
        lines.extend(["", "## Changes"])
        for category in categories:
            lines.extend(["", f"### {category}"])
            category_events = grouped_events.get(category, [])
            if category_events:
                lines.extend(["", "Objective analyzer results:"])
                for event in category_events:
                    lines.extend(_event_lines(event, verbose=verbose))
            category_changes = sorted(grouped_changes.get(category, []), key=lambda change: change.sort_key)
            if category_changes:
                lines.extend(["", "Observed state changes:"])
                for change in category_changes:
                    lines.extend(_change_lines(change, verbose=verbose))
    if omitted:
        noun = "result" if omitted == 1 else "results"
        lines.extend(["", f"{omitted} objective analyzer {noun} below {min_significance.value} significance omitted."])

    if verbose:
        inferred = sorted(
            (event for event in event_list if event.status is not EventStatus.OBJECTIVE),
            key=lambda event: event.sort_key,
        )
        if inferred:
            lines.extend(["", "## Omitted non-objective results", ""])
            for event in inferred:
                marker = "[inferred, ambiguous]" if event.attribute("ambiguous") is True else "[inferred]"
                lines.append(f"- {marker} {describe_event(event)}")
        lines.extend(
            [
                "",
                "## Rendering notes",
                "",
                "- `unknown (...)` marks unavailable or unresolved normalized data.",
                "- `ambiguous` marks an analyzer result that needs interpretation.",
            ]
        )
    return "\n".join(lines) + "\n"


def _inferred_section(
    inferred: Iterable[Event], objective: Iterable[Event], *, verbose: bool, min_significance: Significance
) -> list[str]:
    candidates = list(inferred)
    listed = sorted(
        (event for event in candidates if event.significance.rank >= min_significance.rank),
        key=lambda event: event.sort_key,
    )
    by_id = {event.id: event for event in objective}
    lines = ["", "## Inferred events", ""]
    if not candidates:
        return [*lines, "No events were inferred."]
    lines.append("Reconstructed from the objective results below; never observed directly.")
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


def render_events(events: list[Event]) -> str:
    """Render the original deterministic event-list API."""
    return "\n".join(
        f"- {render_value(event.date)}: {event.event_type}"
        for event in sorted(events, key=lambda event: event.sort_key)
    )


def _snapshot_lines(label: str, snapshot: SaveSnapshot) -> list[str]:
    details = [f"date: `{snapshot.date}`", f"source: `{snapshot.source}`"]
    details.extend(
        [
            f"game version: `{_optional(snapshot.game_version)}`",
            f"campaign day: `{render_value(snapshot.campaign_day)}`",
            f"campaign quarter: `{render_value(snapshot.campaign_quarter)}`",
            f"timestamp: `{_optional(snapshot.timestamp)}`",
        ]
    )
    return [f"- **{label}:** " + "; ".join(details)]


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
            attributes = "; ".join(f"{name}: `{render_value(value)}`" for name, value in event.attributes)
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
    return ", ".join(str(entity.entity_id) for entity in ordered)


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


def _optional(value: object | None) -> str:
    return "<unknown>" if value is None else str(value)
