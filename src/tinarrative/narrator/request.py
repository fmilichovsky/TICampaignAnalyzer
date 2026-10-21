"""The narrator request: the packaged system prompt and a user message built from a narrator package.

The user message is a request block followed by the package. The result is a Messages-style body,
``{"system": ..., "messages": [...]}``, to which a caller adds the model and limits. The same inputs always give the
same bytes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from importlib import resources
from typing import Any

# The request block lists its keys in this order and only the ones that are set; the first three are set by the
# chapter planner only.
REQUEST_KEYS = ("chapter", "part", "covers", "period", "audience", "citations", "style", "length", "focus")
AUDIENCES = ("public", "insider")
CITATIONS = ("footnotes", "none")
STYLES = ("chronicle", "headlines")


def system_prompt() -> str:
    """The narrator system prompt, shipped as package data."""
    return resources.files("tinarrative.narrator").joinpath("prompt.md").read_text(encoding="utf-8")


def prompt_version() -> str:
    """The version of the prompt: the SHA-256 of its text, in hex."""
    return hashlib.sha256(system_prompt().encode("utf-8")).hexdigest()


def build_request(
    package: Mapping[str, Any], options: Mapping[str, str], *, notes: Sequence[str] = ()
) -> dict[str, Any]:
    """The request body for ``package`` with the request block ``options`` (only the keys given).

    ``notes`` are extra lines for the end of the block.
    """
    if package.get("narrative") is None or package.get("glossary") is None:
        raise ValueError("not a narrator package: run tinarrative events with --narrative --format json")
    unknown = sorted(set(options) - set(REQUEST_KEYS))
    if unknown:
        raise ValueError(f"unknown request keys: {', '.join(unknown)}")
    lines = [f"{key}: {options[key]}" for key in REQUEST_KEYS if options.get(key)]
    block = "\n".join([*lines, *notes])
    body = json.dumps(package, ensure_ascii=False, separators=(",", ":"))
    content = (f"{block}\n\n" if block else "") + f"The narrator package follows.\n\n```json\n{body}\n```\n"
    return {"system": system_prompt(), "messages": [{"role": "user", "content": content}]}


def render_request(request: Mapping[str, Any]) -> str:
    """The text a request is written as: indented JSON with a trailing newline."""
    return json.dumps(request, ensure_ascii=False, indent=2) + "\n"
