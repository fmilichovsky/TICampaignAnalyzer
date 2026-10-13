"""Text and JSON renderings of a :class:`StateDiff`."""

from __future__ import annotations

import json
from collections import Counter

from ..model.changes import ChangeKind, MapDetail, MembershipDetail, StateChange, StateDiff
from ..model.entities import EntityRef
from ..model.values import Observed, Unknown, to_jsonable


def render_value(value: Observed) -> str:
    """One-line text for a normalized value: references as ``domain:key``, unknowns with their reason."""
    if isinstance(value, Unknown):
        if value.raw is None:
            return f"unknown ({value.reason.value})"
        return f"unknown ({value.reason.value}, raw={render_value(value.raw)})"
    if isinstance(value, EntityRef):
        return str(value.entity_id)
    if isinstance(value, tuple):
        return "[" + ", ".join(render_value(item) for item in value) + "]"
    return json.dumps(to_jsonable(value), sort_keys=True, ensure_ascii=True)


def _subject(change: StateChange) -> str:
    """``nation:20 GDP`` for an entity field, ``campaign date`` for a snapshot-level field."""
    head = str(change.entity_id) if change.entity_id else change.domain
    return head if change.field is None else f"{head} {change.field}"


def render_change(change: StateChange) -> str:
    subject = _subject(change)
    if change.kind in (ChangeKind.APPEARED, ChangeKind.DISAPPEARED):
        return f"{subject}: {change.evidence.description}"
    if isinstance(change.detail, MembershipDetail):
        parts = [f"+{render_value(m)}" for m in change.detail.added]
        parts += [f"-{render_value(m)}" for m in change.detail.removed]
        return f"{subject}: {' '.join(parts)}"
    if isinstance(change.detail, MapDetail):
        groups = [
            f"{label} {', '.join(keys)}"
            for label, keys in (
                ("added", change.detail.added),
                ("removed", change.detail.removed),
                ("changed", change.detail.changed),
            )
            if keys
        ]
        return f"{subject}: {'; '.join(groups)}"
    return f"{subject}: {render_value(change.before)} -> {render_value(change.after)}"


def _snapshot_lines(label: str, diff: StateDiff, side: str) -> list[str]:
    snapshot = diff.before if side == "before" else diff.after
    return [
        f"{label}: {snapshot.source}",
        f"  date: {render_value(snapshot.date)}",
        f"  game_version: {snapshot.game_version or 'not serialized'}",
    ]


def render_text(diff: StateDiff) -> str:
    lines = ["tinarrative diff report"]
    lines += _snapshot_lines("before", diff, "before")
    lines += _snapshot_lines("after", diff, "after")
    lines.append(f"changes: {len(diff.changes)}")
    by_domain = Counter(change.domain for change in diff.changes)
    for domain in sorted(by_domain):
        lines.append(f"  {domain}: {by_domain[domain]}")
    if diff.changes:
        lines.append("changes:")
        lines += ["  " + render_change(change) for change in diff.changes]
    return _escape_non_ascii("\n".join(lines) + "\n")


def render_json(diff: StateDiff) -> str:
    return json.dumps(diff.to_dict(), indent=2, ensure_ascii=True) + "\n"


def _escape_non_ascii(text: str) -> str:
    """Keep the text report byte-stable on any console by escaping non-ASCII."""
    if text.isascii():
        return text
    return "".join(
        char if char.isascii() else (f"\\u{ord(char):04x}" if ord(char) <= 0xFFFF else f"\\U{ord(char):08x}")
        for char in text
    )
