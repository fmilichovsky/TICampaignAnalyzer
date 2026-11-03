"""The narrator request: the packaged system prompt and a user message built from a narrator package.

A caller adds the model and limits. The same inputs always give the same bytes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from importlib import resources
from typing import Any

# The first three are set by the chapter planner only.
REQUEST_KEYS = ("chapter", "part", "covers", "period", "audience", "citations", "style", "length", "focus")
AUDIENCES = ("public", "insider")
CITATIONS = ("footnotes", "none")
STYLES = ("chronicle", "headlines")
PROMPT_FILE = "prompt.md"


def system_prompt(name: str = PROMPT_FILE) -> str:
    """A system prompt packaged with the narrator; ``name`` is its file name."""
    return resources.files("tinarrative.narrator").joinpath(name).read_text(encoding="utf-8")


def prompt_version(name: str = PROMPT_FILE) -> str:
    """The SHA-256 of the prompt text."""
    return hashlib.sha256(system_prompt(name).encode("utf-8")).hexdigest()


def digest(document: Mapping[str, Any]) -> str:
    """The SHA-256 of a document's compact JSON, the identity of a package or a dossier."""
    text = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_request(
    package: Mapping[str, Any], options: Mapping[str, str], *, notes: Sequence[str] = ()
) -> dict[str, Any]:
    """``notes`` are extra lines for the end of the request block."""
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


def chapter_package(request: Mapping[str, Any]) -> dict[str, Any]:
    """The inverse of ``build_request``."""
    try:
        content = request["messages"][0]["content"]
        _, fence, rest = content.partition("```json\n")
        body, closing, _ = rest.rpartition("\n```")
        package = json.loads(body) if fence and closing else None
    except (KeyError, IndexError, TypeError, AttributeError, json.JSONDecodeError):
        package = None
    if not isinstance(package, dict):
        raise ValueError("the request carries no narrator package")
    return package


def render_request(request: Mapping[str, Any]) -> str:
    return json.dumps(request, ensure_ascii=False, indent=2) + "\n"
