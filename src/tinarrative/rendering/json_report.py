"""The JSON report of an analyzed save sequence: the narrator package when narrative events are supplied.

Like the Markdown renderer, this presents already-computed results; it never compares snapshots or infers facts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from ..config import Settings
from ..grouping import CampaignGroup
from ..model.entities import IdentityConfidence
from ..model.events import Event, Significance
from ..narrative.glossary import build_glossary
from ..narrative.situation import SituationReport
from ..sequence import IntervalResult, SequencePlan, situations
from .listing import listing


def build_document(
    plan: SequencePlan,
    intervals: Sequence[IntervalResult],
    *,
    campaign: CampaignGroup,
    settings: Settings,
    narrative: Sequence[Event] | None,
    min_significance: Significance = Significance.TRIVIAL,
    include_constituents: bool = False,
) -> dict[str, Any]:
    """The report document.

    Without ``narrative``, objective and inferred events below ``min_significance`` are dropped. With it, narrative
    events below ``min_significance`` are dropped, and an objective or inferred event is kept only as a constituent
    of a kept narrative event when ``include_constituents`` is set (``listing``). Dropped events are counted
    (``omitted`` per interval, ``narrative_omitted``), so an omission is never hidden; state changes are never
    filtered. With ``narrative``, the document is the narrator package: it also holds the narrative rules'
    ``settings`` and the ``glossary`` of every entity ID it references, and leaves out provenance and paths
    (``_narrator_package``).
    """
    document: dict[str, Any] = {"campaign": campaign.to_dict(), **plan.to_dict()}
    reports = situations(intervals)
    document["saves"] = [
        {**save, "situation": reports[position].to_dict() if position < len(reports) else None}
        for position, save in enumerate(document["saves"])
    ]
    chosen = listing(intervals, narrative, minimum=min_significance, include_constituents=include_constituents)
    document["min_significance"] = min_significance.value
    document["include_constituents"] = None if narrative is None else include_constituents
    document["settings"] = None if narrative is None else {"narrative": settings.to_dict()["narrative"]}
    listed = chosen.narrative
    document["narrative"] = None if listed is None else [event.to_dict() for event in listed]
    document["narrative_omitted"] = None if listed is None or narrative is None else len(narrative) - len(listed)
    rendered: list[dict[str, Any]] = []
    for interval in intervals:
        objective = chosen.kept(interval.objective)
        inferred = None if interval.inferred is None else chosen.kept(interval.inferred)
        entry = replace(interval, objective=objective, inferred=inferred).to_dict()
        entry["omitted"] = {
            "objective": len(interval.objective) - len(objective),
            "inferred": None
            if inferred is None or interval.inferred is None
            else len(interval.inferred) - len(inferred),
        }
        rendered.append(entry)
    document["intervals"] = rendered
    if narrative is None:
        document["glossary"] = None
        return document
    return _narrator_package(document, reports)


def _narrator_package(document: dict[str, Any], reports: Sequence[SituationReport]) -> dict[str, Any]:
    """The narrator package (architecture 13.1): the report without provenance and paths, for a reader that cites IDs.

    Every event loses its ``sources``, and the campaign, skipped files, saves and intervals lose their file paths; the
    report without ``--narrative`` (at ``trivial``) keeps both, and every ID here resolves in it. A nation that holds no
    region in any save and is not referenced by a listed event is left out of the situation reports. The glossary is
    built from what remains, then references are reduced to ``ref`` and ``name`` (and ``confidence`` when the identity
    is not an in-save ID), the glossary keeping each entity's kind.
    """
    document["campaign"] = {key: value for key, value in document["campaign"].items() if key != "sources"}
    document["skipped"] = [{"error_class": skipped["error_class"]} for skipped in document["skipped"]]
    document["saves"] = [
        {key: value for key, value in save.items() if key not in ("source", "aliases")} for save in document["saves"]
    ]
    events: list[dict[str, Any]] = list(document["narrative"])
    for interval in document["intervals"]:
        del interval["before"], interval["after"]
        events.extend(interval["events"])
        events.extend(interval["inferred"] or ())
    for event in events:
        del event["sources"]
    _prune_nations(document["saves"], _referenced(events))
    glossary = build_glossary(document, reports)
    slimmed: dict[str, Any] = _slim(document)
    slimmed["glossary"] = glossary
    return slimmed


def _referenced(node: Any) -> set[str]:
    if isinstance(node, dict):
        found = {node["ref"]} if isinstance(node.get("ref"), str) else set()
        for value in node.values():
            found |= _referenced(value)
        return found
    if isinstance(node, list):
        return set().union(*(_referenced(item) for item in node)) if node else set()
    return set()


def _prune_nations(saves: list[dict[str, Any]], referenced: set[str]) -> None:
    """Drop, from every report, the nations that hold no region in any report and that no listed event references."""
    reports = [save["situation"] for save in saves if save["situation"] is not None]
    kept = {
        nation["nation"]["ref"]
        for report in reports
        for nation in report["nations"]
        if nation["regions"] != 0 or nation["nation"]["ref"] in referenced
    }
    for report in reports:
        report["nations"] = [nation for nation in report["nations"] if nation["nation"]["ref"] in kept]


def _slim(node: Any) -> Any:
    if isinstance(node, dict):
        if isinstance(node.get("ref"), str) and "state_type" in node:
            slim: dict[str, Any] = {"ref": node["ref"]}
            if "name" in node:
                slim["name"] = node["name"]
            if node.get("confidence") != IdentityConfidence.IN_SAVE_ID.value:
                slim["confidence"] = node.get("confidence")
            return slim
        return {key: _slim(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_slim(item) for item in node]
    return node
