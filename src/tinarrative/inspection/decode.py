"""Byte-level facts and UTF-8 JSON decoding of a save."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from ..log import fields, get_logger
from .report import Diagnostic, FileFacts, LineEndings

logger = get_logger(__name__)

GZIP_MAGIC = b"\x1f\x8b"
ZIP_MAGIC = b"PK\x03\x04"
UTF8_BOM = b"\xef\xbb\xbf"
UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
_LEADING_BYTES = 8
_DECODE_CONTEXT_CHARS = 20


@dataclass(frozen=True)
class DecodeResult:
    ok: bool
    value: Any
    text: str | None
    diagnostics: tuple[Diagnostic, ...]


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

    def failure(code: str, message: str, detail: str | None = None, **context: object) -> DecodeResult:
        logger.debug("decode rejected %s", fields(code=code, **context))
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
        logger.debug("utf8 bom stripped %s", fields(bytes=len(UTF8_BOM)))

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        return failure(
            "invalid_utf8",
            f"{error.reason} at byte offset {error.start}",
            offset=error.start,
        )
    logger.debug("utf-8 decoded %s", fields(bytes=len(data), chars=len(text)))

    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        start = max(0, error.pos - _DECODE_CONTEXT_CHARS)
        context = text[start : error.pos + _DECODE_CONTEXT_CHARS]
        return failure(
            "json_decode_error",
            f"{error.msg}: line {error.lineno} column {error.colno} (char {error.pos})",
            f"context: {context!r}",
            line=error.lineno,
            column=error.colno,
            pos=error.pos,
        )
    logger.debug("json decoded %s", fields(root=type(value).__name__))
    return DecodeResult(True, value, text, tuple(diagnostics))
