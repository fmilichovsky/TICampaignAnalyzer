"""Static inspection of one serialized save file: what is literally serialized, nothing normalized.

This package must not import :mod:`tinarrative.parsing`.
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
