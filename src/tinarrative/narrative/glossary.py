"""The entity glossary of the narrator package: what inline names do not say.

That is the names of entities referenced somewhere by ID only, and the former names of renamed entities.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ..model.entities import EntityDomain, EntityId


def _entity_id(text: str) -> EntityId | None:
    domain, separator, key = text.partition(":")
    try:
        return EntityId(EntityDomain(domain), key) if separator else None
    except ValueError:
        return None


def _references(node: Any) -> Iterable[Mapping[str, Any]]:
    """Also yields the faction shares' keys and the ref strings of ``allies``, which are references by ID only."""
    if isinstance(node, Mapping):
        if isinstance(node.get("ref"), str):
            yield node
        for key, value in node.items():
            if key == "shares" and isinstance(value, Mapping):
                for holder in value:
                    yield {"ref": holder}
            elif key == "allies" and isinstance(value, list):
                for ally in value:
                    if isinstance(ally, str):
                        yield {"ref": ally}
                    else:
                        yield from _references(ally)
            else:
                yield from _references(value)
    elif isinstance(node, list):
        for item in node:
            yield from _references(item)


def build_glossary(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Sorted by entity ID. ``name`` is the latest save's; ``former_names`` are the others, oldest first."""
    found: dict[str, dict[str, Any]] = {}
    earlier: dict[str, list[str]] = {}
    bare: set[str] = set()

    def note(reference: Mapping[str, Any]) -> None:
        text = reference["ref"]
        entry = found.setdefault(text, {})
        name = reference.get("name")
        if not isinstance(name, str):
            bare.add(text)
        elif name != entry.get("name"):
            if "name" in entry:
                former = earlier.setdefault(text, [])
                if entry["name"] in former:
                    former.remove(entry["name"])
                former.append(entry["name"])
            entry["name"] = name
            if name in earlier.get(text, ()):
                earlier[text].remove(name)

    # Narrative events carry save-time names but are not ordered against the intervals, so the chronological
    # members (saves, then intervals) are read last and have the final word.
    for key in ("narrative", *(key for key in document if key != "narrative")):
        for reference in _references(document.get(key)):
            note(reference)
    entries: list[dict[str, Any]] = []
    for text in sorted(found, key=_sort_key):
        if not earlier.get(text) and not (text in bare and "name" in found[text]):
            continue
        parsed = _entity_id(text)
        ordered: dict[str, Any] = {"ref": text, "domain": parsed.domain.value if parsed else text.partition(":")[0]}
        ordered.update(found[text])
        if earlier.get(text):
            ordered["former_names"] = earlier[text]
        entries.append(ordered)
    return entries


def _sort_key(text: str) -> tuple[str, int, int, str]:
    parsed = _entity_id(text)
    return parsed.sort_key if parsed is not None else (text, 1, 0, "")


__all__ = ["build_glossary"]
