"""Raw serialized-save representation boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .errors import MalformedSaveError, UnsupportedSaveShapeError
from .game_version import (
    DEFAULT_FORMAT,
    detect_game_version,
    require_supported_format,
    require_supported_game_version,
)

ENVELOPE_KEYS = ("currentID", "gamestates")
"""Top-level members observed in every sample of ``terra_invicta_json_v1``."""

_UTF8_BOM = b"\xef\xbb\xbf"
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
_GZIP_MAGIC = b"\x1f\x8b"
_ZIP_MAGIC = b"PK\x03\x04"


@dataclass(frozen=True)
class RawSave:
    """A validated, otherwise uninterpreted decoded save.

    ``root`` is the decoded JSON object exactly as serialized; normalizers read
    it and keep ``source`` for provenance.
    """

    source: str
    format: str
    game_version: str | None
    root: dict[str, Any]
    size_bytes: int


def _decode_json(data: bytes) -> Any:
    if not data:
        raise MalformedSaveError("The save file is empty.")
    if data.startswith(_GZIP_MAGIC):
        raise MalformedSaveError("The save looks gzip-compressed; only uncompressed JSON is supported.")
    if data.startswith(_ZIP_MAGIC):
        raise MalformedSaveError("The save looks like a zip archive; only uncompressed JSON is supported.")
    if data.startswith(_UTF16_BOMS):
        raise MalformedSaveError("The save is UTF-16 encoded; only UTF-8 JSON is supported.")
    if data.startswith(_UTF8_BOM):
        raise MalformedSaveError("The save starts with a UTF-8 byte-order mark; the documented format has none.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MalformedSaveError(f"The save is not valid UTF-8 (byte offset {error.start}).") from None
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise MalformedSaveError(
            f"The save is not valid JSON: {error.msg} (line {error.lineno}, column {error.colno})."
        ) from None


def parse_raw_save(data: bytes, *, source: str, format: str = DEFAULT_FORMAT) -> RawSave:
    """Validate ``data`` as a save of ``format`` and return it as a ``RawSave``.

    Raises a :class:`~tinarrative.parsing.errors.SaveLoadError` subclass on failure.
    State types are not checked, so added or removed ones never cause a rejection.
    """
    require_supported_format(format)
    root = _decode_json(data)
    if not isinstance(root, dict):
        raise UnsupportedSaveShapeError(f"The save's JSON root is {type(root).__name__}, expected an object.")
    for key in ENVELOPE_KEYS:
        if key not in root:
            raise UnsupportedSaveShapeError(f"The save has no top-level {key!r} member.")
    if not isinstance(root["gamestates"], dict):
        raise UnsupportedSaveShapeError("The save's 'gamestates' member is not an object.")
    require_supported_game_version(root)
    return RawSave(
        source=source,
        format=format,
        game_version=detect_game_version(root),
        root=root,
        size_bytes=len(data),
    )
