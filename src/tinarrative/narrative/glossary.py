"""The entity glossary of the narrator package: every entity ID a report document references, with what the save
says about it.

The glossary is read from the finished document (its situation reports, interval events and narrative events), so it
holds exactly the IDs the document references and no snapshot is kept. A nation also lists its regions, which are
glossary entries themselves.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.values import to_jsonable
from .situation import SituationReport


def _entity_id(text: str) -> EntityId | None:
    domain, separator, key = text.partition(":")
    try:
        return EntityId(EntityDomain(domain), key) if separator else None
    except ValueError:
        return None


def _references(node: Any) -> Iterable[Mapping[str, Any]]:
    """Every reference object (a mapping with a ``ref``) in a JSON-shaped value, the faction shares' keys and the
    ref strings of a narrator package's ``allies``."""
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


def _region_lists(reports: Sequence[SituationReport]) -> dict[str, list[EntityRef]]:
    """Each nation's regions in the latest report that lists them."""
    regions: dict[str, list[EntityRef]] = {}
    for report in reports:
        for nation in report.nations:
            if isinstance(nation.region_refs, tuple):
                regions[str(nation.nation.entity_id)] = [
                    ref for ref in nation.region_refs if isinstance(ref, EntityRef)
                ]
    return regions


def build_glossary(document: Mapping[str, Any], reports: Sequence[SituationReport]) -> list[dict[str, Any]]:
    """The glossary of ``document``, sorted by entity ID.

    Every entry has ``ref``, ``domain`` and, where the save gives them, ``name`` and ``kind`` (the save's state
    type). For an entity whose display name changes between saves, ``name`` is the one the latest save or interval
    carries; its other names, oldest first, are ``former_names``. A nation entry also has ``regions``: its regions'
    ``ref`` and ``name``. Regions are entries too.
    """
    found: dict[str, dict[str, Any]] = {}
    earlier: dict[str, list[str]] = {}

    def note(reference: Mapping[str, Any]) -> None:
        text = reference["ref"]
        entry = found.setdefault(text, {})
        name = reference.get("name")
        if isinstance(name, str) and name != entry.get("name"):
            if "name" in entry:
                former = earlier.setdefault(text, [])
                if entry["name"] in former:
                    former.remove(entry["name"])
                former.append(entry["name"])
            entry["name"] = name
            if name in earlier.get(text, ()):
                earlier[text].remove(name)
        kind = reference.get("state_type")
        if isinstance(kind, str) and "kind" not in entry:
            entry["kind"] = kind

    # Narrative events carry save-time names but are not ordered against the intervals, so the chronological
    # members (saves, then intervals) are read last and have the final word.
    for key in ("narrative", *(key for key in document if key != "narrative")):
        for reference in _references(document.get(key)):
            note(reference)
    regions = _region_lists(reports)
    nation_regions: dict[str, list[dict[str, Any]]] = {}
    for text in list(found):
        if text in regions:
            nation_regions[text] = []
        for region in regions.get(text, ()):
            rendered = to_jsonable(region)
            note(rendered)
            nation_regions[text].append(
                {"ref": rendered["ref"], **({"name": rendered["name"]} if "name" in rendered else {})}
            )
    entries: list[dict[str, Any]] = []
    for text in sorted(found, key=_sort_key):
        entry = dict(sorted(found[text].items(), key=lambda item: item[0] != "name"))
        parsed = _entity_id(text)
        ordered: dict[str, Any] = {"ref": text, "domain": parsed.domain.value if parsed else text.partition(":")[0]}
        ordered.update(entry)
        if earlier.get(text):
            ordered["former_names"] = earlier[text]
        if text in nation_regions:
            ordered["regions"] = nation_regions[text]
        entries.append(ordered)
    return entries


def _sort_key(text: str) -> tuple[str, int, int, str]:
    parsed = _entity_id(text)
    return parsed.sort_key if parsed is not None else (text, 1, 0, "")


__all__ = ["build_glossary"]
