"""The JSON report of an analyzed save sequence: the narrator package when narrative events are supplied."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from ..config import Settings
from ..grouping import CampaignGroup
from ..model.entities import IdentityConfidence
from ..model.events import Event, Significance
from ..narrative.glossary import build_glossary
from ..sequence import IntervalResult, SequencePlan, situations
from .listing import Constituents, listing

FLOAT_DIGITS = 4
"""Significant digits of a float in the narrator package."""
DEFAULT_DROPPED: tuple[tuple[str, Any], ...] = (("alien", False), ("wars", []), ("federation", None))
"""Nation members left out of the narrator package while they hold their default."""
ZERO_DROPPED = (
    "unresolved_points",
    "armies",
    "navies",
    "boost",
    "mission_control",
    "space_defence_regions",
    "sto_fighters",
)
"""Nation counts the narrator form leaves out when they are zero, as most nations' are."""
DIGEST_KEYS = ("id", "event_type", "significance", "start", "start_basis", "end", "roles", "intervals")
"""What a narrative event listed as a digest keeps, besides ``member_of``."""


def build_document(
    plan: SequencePlan,
    intervals: Sequence[IntervalResult],
    *,
    campaign: CampaignGroup,
    settings: Settings,
    narrative: Sequence[Event] | None,
    min_significance: Significance = Significance.TRIVIAL,
    constituents: Constituents = "none",
) -> dict[str, Any]:
    """The report document; events are chosen by ``listing``.

    Dropped events are counted (``omitted`` per interval, ``narrative_omitted``) so an omission is never hidden;
    state changes are never filtered.
    """
    document: dict[str, Any] = {"campaign": campaign.to_dict(), **plan.to_dict()}
    reports = situations(intervals)
    document["saves"] = [
        {**save, "situation": reports[position].to_dict() if position < len(reports) else None}
        for position, save in enumerate(document["saves"])
    ]
    chosen = listing(intervals, narrative, minimum=min_significance, constituents=constituents)
    document["min_significance"] = min_significance.value
    document["constituents"] = None if narrative is None else constituents
    document["settings"] = None if narrative is None else {"narrative": settings.to_dict()["narrative"]}
    listed = chosen.narrative
    document["narrative"] = None if listed is None else [_entry(event, chosen.digested) for event in listed]
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
    return _narrator_package(document)


def _narrator_package(document: dict[str, Any]) -> dict[str, Any]:
    """The narrator package (architecture 13.1): the report without provenance and paths, for a reader that cites IDs.

    Every ID here still resolves in the full report. The glossary is built before references are slimmed.
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
        event.pop("sources", None)
    _drop_shift_events(document["narrative"])
    _prune_nations(document["saves"], _referenced(events))
    _slim_situations(document["saves"])
    glossary = build_glossary(document)
    slimmed: dict[str, Any] = _slim(document)
    slimmed["glossary"] = glossary
    return slimmed


def _entry(event: Event, digested: Mapping[str, str]) -> dict[str, Any]:
    entry = event.to_dict()
    member_of = digested.get(event.id)
    if member_of is None:
        return entry
    return {**{key: entry[key] for key in DIGEST_KEYS}, "member_of": member_of}


def _referenced(node: Any) -> set[str]:
    if isinstance(node, dict):
        found = {node["ref"]} if isinstance(node.get("ref"), str) else set()
        for value in node.values():
            found |= _referenced(value)
        return found
    if isinstance(node, list):
        return set().union(*(_referenced(item) for item in node)) if node else set()
    return set()


def _drop_shift_events(narrative: list[dict[str, Any]]) -> None:
    """They name shift events the package does not list."""
    for event in narrative:
        for entry in (event.get("attributes") or {}).get("metric_shifts") or ():
            entry.pop("events", None)


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


def _slim_situations(saves: list[dict[str, Any]]) -> None:
    """Reduce every report to what a reader narrates from; a faction's ``habs`` still counts every hab.

    Allies stay in the full report only.
    """
    for report in (save["situation"] for save in saves if save["situation"] is not None):
        for nation in report["nations"]:
            nation.pop("allies", None)
            for key, default in DEFAULT_DROPPED:
                if key in nation and nation[key] == default and type(nation[key]) is type(default):
                    del nation[key]
            if _executive_holds_all(nation):
                del nation["shares"]
            nation.pop("seat_basis", None)
            for key in ZERO_DROPPED:
                if _is_zero(nation.get(key)):
                    del nation[key]
        factions: list[dict[str, Any]] = []
        for faction in report["factions"]:
            bodies = faction["habs_by_body"]
            shared = [entry for entry in bodies if entry["habs"] > 1]
            slim: dict[str, Any] = {}
            for key, value in faction.items():
                slim[key] = shared if key == "habs_by_body" else value
                if key == "habs_by_body":
                    slim["other_bodies"] = len(bodies) - len(shared)
            factions.append(slim)
        report["factions"] = factions


def _executive_holds_all(nation: dict[str, Any]) -> bool:
    """The one faction in ``shares`` is the executive and holds every control point: both fields already say so."""
    shares, executive = nation.get("shares"), nation.get("executive")
    if not isinstance(shares, dict) or not isinstance(executive, dict) or not isinstance(executive.get("ref"), str):
        return False
    return list(shares) == [executive["ref"]] and shares[executive["ref"]] == nation.get("control_points")


def _is_zero(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value == 0


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
    if isinstance(node, float):
        return float(f"{node:.{FLOAT_DIGITS}g}")
    return node
