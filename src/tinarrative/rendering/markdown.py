"""Deterministic Markdown rendering for one already-analyzed comparison.

This module presents a diff and analyzer output; it never compares snapshots or
infers facts itself.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from typing import Any, cast

from ..diff.state_diff import StateDiff
from ..model.changes import StateChange
from ..model.entities import EntityRef
from ..model.events import Event, EventStatus
from ..model.evidence import Evidence
from ..model.snapshot import SaveSnapshot


def render_comparison(
    comparison: StateDiff,
    events: Iterable[Event] = (),
    *,
    verbose: bool = False,
) -> str:
    """Render one comparison and supplied analyzer results as deterministic Markdown.

    Normal output includes only objective analyzer results. Verbose output also
    identifies inferred results omitted from this factual comparison report.
    """
    event_list = list(events)
    objective_events = sorted(
        (event for event in event_list if event.status is EventStatus.OBJECTIVE),
        key=_event_sort_key,
    )
    grouped_changes: dict[str, list[StateChange]] = defaultdict(list)
    grouped_events: dict[str, list[Event]] = defaultdict(list)
    for change in comparison.changes:
        grouped_changes[_change_category(change)].append(change)
    for event in objective_events:
        grouped_events[_event_category(event)].append(event)

    categories = sorted(set(grouped_changes) | set(grouped_events), key=str.casefold)
    lines = ["# Save comparison", "", "## Snapshots", *_snapshot_lines("Before", comparison.before)]
    lines.extend(_snapshot_lines("After", comparison.after))
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
            category_changes = sorted(grouped_changes.get(category, []), key=_change_sort_key)
            if category_changes:
                lines.extend(["", "Observed state changes:"])
                for change in category_changes:
                    lines.extend(_change_lines(change, verbose=verbose))

    if verbose:
        inferred = sorted(
            (event for event in event_list if event.status is not EventStatus.OBJECTIVE),
            key=_event_sort_key,
        )
        if inferred:
            lines.extend(["", "## Omitted non-objective results", ""])
            for event in inferred:
                marker = "[inferred, ambiguous]" if event.attributes.get("ambiguous") else "[inferred]"
                lines.append(f"- {marker} {_event_summary(event)}")
        lines.extend(
            [
                "",
                "## Rendering notes",
                "",
                "- `<unknown>` marks unavailable normalized metadata.",
                "- `ambiguous` marks an analyzer result that needs interpretation.",
            ]
        )
    return "\n".join(lines) + "\n"


def render_events(events: list[Event]) -> str:
    """Render the original deterministic event-list API."""
    return "\n".join(f"- {event.date}: {event.event_type}" for event in sorted(events, key=_event_sort_key))


def _snapshot_lines(label: str, snapshot: SaveSnapshot) -> list[str]:
    details = [f"date: `{snapshot.date}`", f"source: `{snapshot.source}`"]
    details.extend(
        [
            f"game version: `{_optional(snapshot.game_version)}`",
            f"turn: `{_optional(snapshot.turn)}`",
            f"timestamp: `{_optional(snapshot.timestamp)}`",
        ]
    )
    return [f"- **{label}:** " + "; ".join(details)]


def _event_lines(event: Event, *, verbose: bool) -> list[str]:
    lines = [f"- {_event_summary(event)}"]
    if verbose:
        lines.extend(
            [
                f"  - event id: `{event.id}`",
                f"  - date: `{event.date}`",
                f"  - confidence: `{event.confidence}`",
            ]
        )
        lines.extend(_entity_lines(event.entities, indent="  "))
        lines.extend(_evidence_lines(event.sources, indent="  "))
        if event.attributes:
            lines.append(f"  - attributes: `{_value(event.attributes)}`")
    return lines


def _event_summary(event: Event) -> str:
    entities = _entities(event.entities)
    return f"{event.event_type}" + (f" — affected: {entities}" if entities else "")


def _change_lines(change: StateChange, *, verbose: bool) -> list[str]:
    entity = f" for `{change.entity_id}`" if change.entity_id is not None else ""
    lines = [f"- `{change.field}`{entity}: `{_value(change.before)}` → `{_value(change.after)}`"]
    if verbose:
        lines.append(f"  - evidence: {change.evidence.description}")
        lines.extend(_evidence_lines([change.evidence], indent="  ", include_description=False))
    return lines


def _entity_lines(entities: Iterable[EntityRef], *, indent: str) -> list[str]:
    rendered = _entities(entities)
    return [f"{indent}- affected entities: {rendered}"] if rendered else []


def _entities(entities: Iterable[EntityRef]) -> str:
    ordered = sorted(entities, key=lambda entity: (entity.kind, entity.id, entity.name or ""))
    return ", ".join(f"{entity.kind} `{entity.name or entity.id}` ({entity.id})" for entity in ordered)


def _evidence_lines(evidence: Iterable[Evidence], *, indent: str, include_description: bool = True) -> list[str]:
    lines: list[str] = []
    for item in sorted(evidence, key=_evidence_sort_key):
        parts = [f"save: `{item.save_id}`", f"domain: `{item.domain}`"]
        if item.path is not None:
            parts.append(f"path: `{item.path}`")
        parts.extend([f"before: `{_value(item.before)}`", f"after: `{_value(item.after)}`"])
        if include_description:
            parts.insert(0, item.description)
        lines.append(f"{indent}- evidence: " + "; ".join(parts))
    return lines


def _event_category(event: Event) -> str:
    category = event.attributes.get("category")
    if isinstance(category, str) and category:
        return category
    domains = {evidence.domain for evidence in event.sources}
    return next(iter(domains)).replace("_", " ").title() if len(domains) == 1 else "Analyzer results"


def _change_category(change: StateChange) -> str:
    return change.domain.replace("_", " ").title()


def _change_sort_key(change: StateChange) -> tuple[str, str, str, str, str]:
    return (change.domain, change.entity_id or "", change.field, _value(change.before), _value(change.after))


def _event_sort_key(event: Event) -> tuple[str, str, str]:
    return (event.date, event.id, event.event_type)


def _evidence_sort_key(evidence: Evidence) -> tuple[str, str, str, str, str]:
    return (evidence.domain, evidence.path or "", evidence.description, _value(evidence.before), _value(evidence.after))


def _optional(value: object | None) -> str:
    return "<unknown>" if value is None else str(value)


def _value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, default=_json_default)


def _json_default(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(cast(Any, value))
    return str(value)
