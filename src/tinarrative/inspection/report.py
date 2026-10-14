"""Result types of a structural inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from tinarrative.identity import IdentityReport

Status = Literal["ok", "path_not_found", "unsupported_input"]
LineEndings = Literal["lf", "crlf", "mixed", "none"]


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
    identity: IdentityReport | None = None
