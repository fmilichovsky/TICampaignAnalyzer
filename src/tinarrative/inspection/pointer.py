"""JSON-pointer resolution and bounded rendering of decoded values."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .report import RenderLimits

_ARRAY_INDEX = re.compile(r"^(0|[1-9][0-9]*)$")


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
