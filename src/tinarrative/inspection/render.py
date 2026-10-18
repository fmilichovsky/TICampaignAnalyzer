"""Text and JSON renderings of an :class:`InspectReport`."""

from __future__ import annotations

import json
from dataclasses import asdict

from tinarrative.identity import IdentityReport

from .report import InspectReport, KeySummary


def _render_identity(lines: list[str], identity: IdentityReport) -> None:
    lines.append("identity:")
    shared = identity.ids_shared_across_types
    lines.append(f"  ids: {identity.total_ids} distinct, {shared} shared across state types")
    lines.append(f"  max_observed_id: {'n/a' if identity.max_observed_id is None else identity.max_observed_id}")
    lines.append(f"  currentID: {'n/a' if identity.current_id is None else identity.current_id}")
    for item in identity.domains:
        domain = item.domain
        lines.append(f"  {domain.domain}: confidence={domain.confidence}")
        lines.append(f"    id_source: {domain.id_source}")
        lines.append(f"    secondary_key: {domain.secondary_key or 'none'}")
        for observed in item.types:
            if not observed.present:
                lines.append(f"    {observed.state_type}: absent")
                continue
            id_range = "none" if observed.min_id is None else f"{observed.min_id}..{observed.max_id}"
            lines.append(
                f"    {observed.state_type}: {observed.entries} entries, ids {id_range}, "
                f"key==id {observed.id_matches}, mismatch {observed.id_mismatches}, "
                f"missing {observed.id_missing}, duplicate {observed.id_duplicates}"
            )


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def describe(label: str, length: int | None) -> str:
    if length is None:
        return label
    noun = {"object": "key", "array": "item", "string": "char"}.get(label)
    if noun is None:
        return label
    return f"{label} ({_plural(length, noun)})"


def _render_key_lines(lines: list[str], summaries: tuple[KeySummary, ...]) -> None:
    for summary in summaries:
        lines.append(f"  {summary.key}: {describe(summary.type_label, summary.length)}")


def render_text(report: InspectReport) -> str:
    facts = report.file
    lines = [
        "tinarrative save inspect report",
        f"file: {report.file_name}",
        f"  size_bytes: {facts.size_bytes}",
        f"  sha256: {facts.sha256}",
        f"  leading_bytes: {facts.leading_bytes_hex}",
        f"  utf8_bom: {'yes' if facts.has_utf8_bom else 'no'}",
        f"  line_endings: {facts.line_endings}",
        "  decoded_chars: " + ("n/a" if facts.decoded_chars is None else str(facts.decoded_chars)),
    ]

    if report.status == "unsupported_input":
        lines += ["decode: failed", "root: n/a", "top-level keys: n/a"]
    else:
        lines.append("decode: ok (json)")
        root_type = report.root_type or "n/a"
        if root_type == "object":
            lines.append(f"root: {describe('object', len(report.top_level))}")
            if report.top_level:
                lines.append("top-level keys:")
                _render_key_lines(lines, report.top_level)
            else:
                lines.append("top-level keys: none")
            for key, children in report.second_level.items():
                if children:
                    lines.append(f"{key} keys:")
                    _render_key_lines(lines, children)
                else:
                    lines.append(f"{key} keys: none")
        else:
            lines.append(f"root: {root_type}")
            lines.append(f"top-level keys: n/a (root is {root_type})")

    if report.identity is not None:
        _render_identity(lines, report.identity)

    if report.paths:
        lines.append("selected paths:")
        for result in report.paths:
            if result.found:
                label = describe(result.type_label or "", result.length)
                lines.append(f"  {result.pointer}: {label}")
                rendered = json.dumps(result.value, indent=2, ensure_ascii=True)
                lines += ["    " + line for line in rendered.splitlines()]
            elif result.reason == "not evaluated":
                lines.append(f"  {result.pointer}: not evaluated (input could not be decoded)")
            else:
                lines.append(f"  {result.pointer}: not found ({result.reason})")
    else:
        lines.append("selected paths: none")

    if report.diagnostics:
        lines.append("diagnostics:")
        for diagnostic in report.diagnostics:
            lines.append(f"  {diagnostic.code}: {diagnostic.message}")
            if diagnostic.detail is not None:
                lines.append(f"    {diagnostic.detail}")
    else:
        lines.append("diagnostics: none")

    return _escape_non_ascii("\n".join(lines) + "\n")


def _escape_non_ascii(text: str) -> str:
    """Keep the text report byte-stable on any console by escaping non-ASCII."""
    if text.isascii():
        return text
    return "".join(
        char if char.isascii() else (f"\\u{ord(char):04x}" if ord(char) <= 0xFFFF else f"\\U{ord(char):08x}")
        for char in text
    )


def render_json(report: InspectReport) -> str:
    return json.dumps(asdict(report), indent=2, ensure_ascii=True) + "\n"
