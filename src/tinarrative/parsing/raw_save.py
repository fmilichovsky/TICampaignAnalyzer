"""Raw serialized-save representation boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..log import fields, get_logger
from .errors import MalformedSaveError, UnsupportedSaveShapeError
from .game_version import DEFAULT_FORMAT, detect_game_version, require_supported_format

ENVELOPE_KEYS = ("currentID", "gamestates")
"""Top-level members of ``terra_invicta_json_v1``."""

_UTF8_BOM = b"\xef\xbb\xbf"
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
_GZIP_MAGIC = b"\x1f\x8b"
_ZIP_MAGIC = b"PK\x03\x04"

logger = get_logger(__name__)


@dataclass(frozen=True)
class RawSave:
    """A validated, otherwise uninterpreted decoded save; ``root`` is the JSON object exactly as serialized."""

    source: str
    format: str
    game_version: str | None
    root: dict[str, Any]
    size_bytes: int


def _rejected(code: str, message: str, **context: object) -> MalformedSaveError:
    """Log why the bytes were rejected (never their content) and build the error to raise."""
    logger.debug("decode rejected %s", fields(code=code, **context))
    return MalformedSaveError(message)


def _decode_json(data: bytes) -> Any:
    if not data:
        raise _rejected("empty_file", "The save file is empty.")
    if data.startswith(_GZIP_MAGIC):
        raise _rejected("gzip_magic", "The save looks gzip-compressed; only uncompressed JSON is supported.")
    if data.startswith(_ZIP_MAGIC):
        raise _rejected("zip_magic", "The save looks like a zip archive; only uncompressed JSON is supported.")
    if data.startswith(_UTF16_BOMS):
        raise _rejected("utf16_bom", "The save is UTF-16 encoded; only UTF-8 JSON is supported.")
    if data.startswith(_UTF8_BOM):
        raise _rejected("utf8_bom", "The save starts with a UTF-8 byte-order mark; the documented format has none.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _rejected(
            "invalid_utf8", f"The save is not valid UTF-8 (byte offset {error.start}).", offset=error.start
        ) from None
    logger.debug("utf-8 decoded %s", fields(bytes=len(data), chars=len(text)))
    try:
        root = json.loads(text)
    except json.JSONDecodeError as error:
        raise _rejected(
            "json_decode_error",
            f"The save is not valid JSON: {error.msg} (line {error.lineno}, column {error.colno}).",
            line=error.lineno,
            column=error.colno,
            pos=error.pos,
        ) from None
    logger.debug("json decoded %s", fields(root=type(root).__name__))
    return root


def parse_raw_save(data: bytes, *, source: str, format: str = DEFAULT_FORMAT) -> RawSave:
    """Raises a :class:`~tinarrative.parsing.errors.SaveLoadError` subclass on failure.

    State types are not checked, so added or removed ones never cause a rejection.
    """
    require_supported_format(format)
    logger.debug("format accepted %s", fields(format=format, bytes=len(data)))
    root = _decode_json(data)
    if not isinstance(root, dict):
        raise UnsupportedSaveShapeError(f"The save's JSON root is {type(root).__name__}, expected an object.")
    for key in ENVELOPE_KEYS:
        if key not in root:
            raise UnsupportedSaveShapeError(f"The save has no top-level {key!r} member.")
    if not isinstance(root["gamestates"], dict):
        raise UnsupportedSaveShapeError("The save's 'gamestates' member is not an object.")
    logger.debug("envelope ok %s", fields(top_level_keys=len(root), state_types=len(root["gamestates"])))
    return RawSave(
        source=source,
        format=format,
        game_version=detect_game_version(root),
        root=root,
        size_bytes=len(data),
    )
