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
    """Every reference object (a mapping with a ``ref``) in a JSON-shaped value, and the faction shares' keys."""
    if isinstance(node, Mapping):
        if isinstance(node.get("ref"), str):
            yield node
        for key, value in node.items():
            if key == "shares" and isinstance(value, Mapping):
                for holder in value:
                    yield {"ref": holder}
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
    type). A nation entry also has ``regions``: its regions' ``ref`` and ``name``. Regions are entries too.
    """
    found: dict[str, dict[str, Any]] = {}

    def note(reference: Mapping[str, Any]) -> None:
        text = reference["ref"]
        entry = found.setdefault(text, {})
        for source, target in (("name", "name"), ("state_type", "kind")):  # name first in the entry
            value = reference.get(source)
            if isinstance(value, str) and target not in entry:
                entry[target] = value

    for reference in _references(document):
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
        if text in nation_regions:
            ordered["regions"] = nation_regions[text]
        entries.append(ordered)
    return entries


def _sort_key(text: str) -> tuple[str, int, int, str]:
    parsed = _entity_id(text)
    return parsed.sort_key if parsed is not None else (text, 1, 0, "")


__all__ = ["build_glossary"]
