"""Text and JSON renderings of a scan run. Paths shown are the user's own arguments, as ``parse`` prints them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..parsing.unknowns import ShapeSummary, UnknownFinding, UnknownKind
from .registry import RegistryUpdate
from .scan import ScanRun

_ENTRY_KINDS = frozenset((UnknownKind.STATE_TYPE, UnknownKind.SINGLETON_COUNT))


def _plural(count: int, noun: str, plural: str | None = None) -> str:
    return f"{count} {noun if count == 1 else (plural or noun + 's')}"


def finding_label(finding: UnknownFinding) -> str:
    """``<kind> <state type>.<field> [detail]``; envelope keys print as ``/<key>``."""
    if finding.kind is UnknownKind.ENVELOPE_KEY:
        subject = f"/{finding.field}"
    elif finding.field:
        subject = f"{finding.state_type}.{finding.field}"
    else:
        subject = finding.state_type
    label = f"{finding.kind.value} {subject}"
    return f"{label} [{finding.detail}]" if finding.detail else label


def shape_line(shape: ShapeSummary) -> str:
    parts = ["|".join(shape.types) or "none"]
    if shape.object_keys:
        parts.append("keys " + ", ".join(shape.object_keys) + (" (+more)" if shape.object_keys_omitted else ""))
    elif shape.object_keys_omitted:
        parts.append("keys omitted")
    if shape.array_item_types:
        parts.append("items " + "|".join(shape.array_item_types))
    if shape.array_item_keys:
        parts.append("item keys " + ", ".join(shape.array_item_keys))
    return "; ".join(parts)


def render_text(run: ScanRun, update: RegistryUpdate | None, registry: Path | None) -> str:
    lines = ["tinarrative unknowns report", "saves:"]
    for result in run.results:
        if result.report is not None:
            lines.append(f"  {result.path}: {_plural(result.report.total, 'unknown structure')}")
        else:
            lines.append(f"  {result.path}: skipped ({result.error_class}: {result.error})")
    if not run.findings:
        lines.append("findings: none")
    else:
        lines.append(f"findings: {len(run.findings)} across {_plural(len(run.scanned), 'save')}")
    for merged in run.findings:
        finding = merged.finding
        noun = "entry" if finding.kind in _ENTRY_KINDS else "occurrence"
        plural = "entries" if noun == "entry" else None
        lines.append(
            f"  {finding_label(finding)}: {_plural(finding.occurrences, noun, plural)}, {_plural(merged.saves, 'save')}"
        )
        if finding.shape is not None:
            lines.append(f"    shape: {shape_line(finding.shape)}")
    if update is None:
        lines.append("registry: not updated")
    else:
        lines.append(
            f"registry: {registry}: {update.added} added, {update.updated} updated, {update.pruned} pruned, "
            f"{update.total} total"
        )
    return _escape_non_ascii("\n".join(lines) + "\n")


def run_to_dict(run: ScanRun, update: RegistryUpdate | None, registry: Path | None) -> dict[str, Any]:
    saves: list[dict[str, Any]] = []
    for result in run.results:
        saves.append(
            {
                "path": str(result.path),
                "status": "scanned" if result.scanned else "skipped",
                "findings": result.report.total if result.report is not None else None,
                "game_version": result.game_version,
                "error": result.error,
                "error_class": result.error_class,
            }
        )
    findings = [{**merged.finding.to_dict(), "saves": merged.saves} for merged in run.findings]
    registry_data: dict[str, Any] | None = None
    if update is not None:
        registry_data = {
            "path": str(registry),
            "added": update.added,
            "updated": update.updated,
            "pruned": update.pruned,
            "total": update.total,
        }
    return {"saves": saves, "findings": findings, "registry": registry_data}


def render_json(run: ScanRun, update: RegistryUpdate | None, registry: Path | None) -> str:
    return json.dumps(run_to_dict(run, update, registry), indent=2, ensure_ascii=True) + "\n"


def _escape_non_ascii(text: str) -> str:
    if text.isascii():
        return text
    return "".join(
        char if char.isascii() else (f"\\u{ord(char):04x}" if ord(char) <= 0xFFFF else f"\\U{ord(char):08x}")
        for char in text
    )
