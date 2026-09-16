"""Static, semantics-free inspection of one serialized save file.

Everything here describes what is literally serialized: bytes, JSON types,
keys, lengths, and user-selected sub-trees. Nothing is normalized and no game
meaning is inferred; that work belongs to :mod:`tinarrative.parsing`.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal

Status = Literal["ok", "path_not_found", "unsupported_input"]
LineEndings = Literal["lf", "crlf", "mixed", "none"]

GZIP_MAGIC = b"\x1f\x8b"
ZIP_MAGIC = b"PK\x03\x04"
UTF8_BOM = b"\xef\xbb\xbf"
UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
ENVELOPE_KEYS = ("currentID", "gamestates")
"""Top-level keys documented in docs/game-data-notes/terra_invicta_json_v1.md."""

_ARRAY_INDEX = re.compile(r"^(0|[1-9][0-9]*)$")
_LEADING_BYTES = 8
_DECODE_CONTEXT_CHARS = 20


@dataclass(frozen=True)
class Diagnostic:
    """One reproducible finding about the input; never carries paths or times."""

    code: str
    message: str
    detail: str | None = None


@dataclass(frozen=True)
class FileFacts:
    size_bytes: int
    sha256: str
    leading_bytes_hex: str
    has_utf8_bom: bool
    line_endings: LineEndings
    decoded_chars: int | None


@dataclass(frozen=True)
class KeySummary:
    key: str
    type_label: str
    length: int | None


@dataclass(frozen=True)
class PathResult:
    pointer: str
    found: bool
    type_label: str | None
    length: int | None
    value: Any
    reason: str | None


@dataclass(frozen=True)
class RenderLimits:
    max_items: int = 10
    max_string: int = 80
    max_depth: int = 3


@dataclass(frozen=True)
class InspectReport:
    file_name: str
    file: FileFacts
    status: Status
    root_type: str | None
    top_level: tuple[KeySummary, ...]
    second_level: dict[str, tuple[KeySummary, ...]]
    paths: tuple[PathResult, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True)
class DecodeResult:
    ok: bool
    value: Any
    text: str | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True)
class PointerLookup:
    found: bool
    value: Any
    code: str | None = None
    reason: str | None = None


def type_label(value: Any) -> str:
    """Name a decoded value using JSON vocabulary rather than Python types."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def value_length(value: Any) -> int | None:
    if isinstance(value, dict | list | str):
        return len(value)
    return None


def _line_endings(data: bytes) -> LineEndings:
    crlf = data.count(b"\r\n")
    bare_lf = data.count(b"\n") - crlf
    if crlf == 0 and bare_lf == 0:
        return "none"
    if bare_lf == 0:
        return "crlf"
    if crlf == 0:
        return "lf"
    return "mixed"


def file_facts(data: bytes, text: str | None) -> FileFacts:
    leading = data[:_LEADING_BYTES]
    return FileFacts(
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        leading_bytes_hex=" ".join(f"{byte:02x}" for byte in leading) or "(none)",
        has_utf8_bom=data.startswith(UTF8_BOM),
        line_endings=_line_endings(data),
        decoded_chars=None if text is None else len(text),
    )


def decode_save(data: bytes) -> DecodeResult:
    """Decode bytes as UTF-8 JSON, or explain exactly why that is impossible."""
    diagnostics: list[Diagnostic] = []

    def failure(code: str, message: str, detail: str | None = None) -> DecodeResult:
        diagnostics.append(Diagnostic(code, message, detail))
        return DecodeResult(False, None, None, tuple(diagnostics))

    if not data:
        return failure("empty_file", "the file contains no bytes")
    if data.startswith(GZIP_MAGIC):
        return failure(
            "gzip_magic",
            "leading bytes 1f 8b indicate gzip; compressed saves are not a documented format",
        )
    if data.startswith(ZIP_MAGIC):
        return failure(
            "zip_magic",
            "leading bytes 50 4b 03 04 indicate a zip archive; compressed saves are not a documented format",
        )
    if data.startswith(UTF16_BOMS):
        return failure(
            "utf16_bom",
            "leading bytes indicate a UTF-16 byte-order mark; only UTF-8 is a documented encoding",
        )
    if data.startswith(UTF8_BOM):
        diagnostics.append(
            Diagnostic(
                "utf8_bom",
                "a UTF-8 byte-order mark precedes the JSON text; it was skipped but is outside the documented format",
            )
        )
        data = data[len(UTF8_BOM) :]

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        return failure(
            "invalid_utf8",
            f"{error.reason} at byte offset {error.start}",
        )

    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        start = max(0, error.pos - _DECODE_CONTEXT_CHARS)
        context = text[start : error.pos + _DECODE_CONTEXT_CHARS]
        return failure(
            "json_decode_error",
            f"{error.msg}: line {error.lineno} column {error.colno} (char {error.pos})",
            f"context: {context!r}",
        )
    return DecodeResult(True, value, text, tuple(diagnostics))


def _display_prefix(tokens: Sequence[str]) -> str:
    if not tokens:
        return "root"
    return "".join("/" + token.replace("~", "~0").replace("/", "~1") for token in tokens)


def resolve_pointer(value: Any, pointer: str) -> PointerLookup:
    """Follow an RFC 6901 JSON pointer; ``""`` addresses the root."""
    if pointer == "":
        return PointerLookup(True, value)
    if not pointer.startswith("/"):
        return PointerLookup(
            False,
            None,
            "pointer_syntax",
            "a JSON pointer must be empty or start with '/'",
        )
    current = value
    seen: list[str] = []
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        where = _display_prefix(seen)
        if isinstance(current, dict):
            if token not in current:
                return PointerLookup(False, None, "pointer_not_found", f"missing key {token!r} at {where}")
            current = current[token]
        elif isinstance(current, list):
            if not _ARRAY_INDEX.match(token):
                return PointerLookup(
                    False,
                    None,
                    "pointer_not_found",
                    f"{token!r} is not a decimal array index at {where}",
                )
            index = int(token)
            if index >= len(current):
                return PointerLookup(
                    False,
                    None,
                    "pointer_not_found",
                    f"index {index} is out of range (array length {len(current)}) at {where}",
                )
            current = current[index]
        else:
            return PointerLookup(
                False,
                None,
                "pointer_not_found",
                f"cannot descend into {type_label(current)} at {where}",
            )
        seen.append(token)
    return PointerLookup(True, current)


def truncate_value(value: Any, limits: RenderLimits, depth: int = 0) -> Any:
    """Return a bounded, JSON-serializable copy with explicit truncation markers."""
    if isinstance(value, dict):
        if not value:
            return {}
        if depth >= limits.max_depth:
            return "{...}"
        items = list(value.items())
        shown = {key: truncate_value(item, limits, depth + 1) for key, item in items[: limits.max_items]}
        hidden = len(items) - limits.max_items
        if hidden > 0:
            shown["..."] = f"(+{hidden} keys)"
        return shown
    if isinstance(value, list):
        if not value:
            return []
        if depth >= limits.max_depth:
            return "[...]"
        shown_list = [truncate_value(item, limits, depth + 1) for item in value[: limits.max_items]]
        hidden = len(value) - limits.max_items
        if hidden > 0:
            shown_list.append(f"...(+{hidden} items)")
        return shown_list
    if isinstance(value, str) and len(value) > limits.max_string:
        hidden = len(value) - limits.max_string
        return f"{value[: limits.max_string]}...(+{hidden} chars)"
    return value


def summarize_children(value: dict[str, Any]) -> tuple[KeySummary, ...]:
    return tuple(KeySummary(key, type_label(item), value_length(item)) for key, item in value.items())


def inspect_bytes(
    data: bytes,
    file_name: str,
    pointers: Sequence[str] = (),
    limits: RenderLimits | None = None,
) -> InspectReport:
    """Produce a deterministic structural report for one save's bytes."""
    if limits is None:
        limits = RenderLimits()
    decoded = decode_save(data)
    facts = file_facts(data, decoded.text)
    diagnostics = list(decoded.diagnostics)

    if not decoded.ok:
        paths = tuple(PathResult(pointer, False, None, None, None, "not evaluated") for pointer in pointers)
        return InspectReport(
            file_name=file_name,
            file=facts,
            status="unsupported_input",
            root_type=None,
            top_level=(),
            second_level={},
            paths=paths,
            diagnostics=tuple(diagnostics),
        )

    root = decoded.value
    top_level: tuple[KeySummary, ...] = ()
    second_level: dict[str, tuple[KeySummary, ...]] = {}
    if isinstance(root, dict):
        top_level = summarize_children(root)
        second_level = {key: summarize_children(item) for key, item in root.items() if isinstance(item, dict)}
        for key in ENVELOPE_KEYS:
            if key not in root:
                diagnostics.append(
                    Diagnostic(
                        "missing_key",
                        f"top-level key {key!r} from the documented envelope is absent",
                    )
                )
    else:
        diagnostics.append(
            Diagnostic(
                "root_not_object",
                f"the JSON root is {type_label(root)}, not an object; the documented envelope has an object root",
            )
        )

    status: Status = "ok"
    results: list[PathResult] = []
    for pointer in pointers:
        lookup = resolve_pointer(root, pointer)
        if lookup.found:
            results.append(
                PathResult(
                    pointer,
                    True,
                    type_label(lookup.value),
                    value_length(lookup.value),
                    truncate_value(lookup.value, limits),
                    None,
                )
            )
        else:
            status = "path_not_found"
            results.append(PathResult(pointer, False, None, None, None, lookup.reason))
            diagnostics.append(Diagnostic(lookup.code or "pointer_not_found", f"{pointer}: {lookup.reason}"))

    return InspectReport(
        file_name=file_name,
        file=facts,
        status=status,
        root_type=type_label(root),
        top_level=top_level,
        second_level=second_level,
        paths=tuple(results),
        diagnostics=tuple(diagnostics),
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
        "tinarrative inspect report",
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
