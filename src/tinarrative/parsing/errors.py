"""User-facing failure categories for turning save bytes into a ``RawSave``.

Unreadable paths are not covered: ``OSError`` propagates from :mod:`tinarrative.io` and the CLI reports it.
"""

from __future__ import annotations


class SaveLoadError(Exception):
    """Base class for save-decoding failures that the CLI reports without a traceback."""


class MalformedSaveError(SaveLoadError):
    """The bytes are not uncompressed UTF-8 JSON as the documented envelope requires."""


class UnsupportedSaveShapeError(SaveLoadError):
    """The bytes are valid JSON but do not have the documented envelope shape."""


class UnsupportedSaveFormatError(SaveLoadError, ValueError):
    """Raised when no parser contract has been documented for a format."""
