"""Static inspection of one serialized save file.

Everything here describes what is literally serialized: bytes, JSON types,
keys, lengths, user-selected sub-trees, and a count of the serialized entity
IDs. Nothing is normalized; that work belongs to :mod:`tinarrative.parsing`,
which this package must not import.
"""

from .analysis import ENVELOPE_KEYS, inspect_bytes, summarize_children
from .decode import DecodeResult, decode_save, file_facts
from .pointer import PointerLookup, resolve_pointer, truncate_value, type_label, value_length
from .render import describe, render_json, render_text
from .report import Diagnostic, FileFacts, InspectReport, KeySummary, PathResult, RenderLimits

__all__ = [
    "ENVELOPE_KEYS",
    "DecodeResult",
    "Diagnostic",
    "FileFacts",
    "InspectReport",
    "KeySummary",
    "PathResult",
    "PointerLookup",
    "RenderLimits",
    "decode_save",
    "describe",
    "file_facts",
    "inspect_bytes",
    "render_json",
    "render_text",
    "resolve_pointer",
    "summarize_children",
    "truncate_value",
    "type_label",
    "value_length",
]
