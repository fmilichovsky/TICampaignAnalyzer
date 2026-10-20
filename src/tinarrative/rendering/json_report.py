"""The JSON report of an analyzed save sequence: the narrator package when narrative events are supplied.

Like the Markdown renderer, this presents already-computed results; it never compares snapshots or infers facts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from ..config import Settings
from ..grouping import CampaignGroup
from ..model.events import Event, Significance
from ..narrative.glossary import build_glossary
from ..sequence import IntervalResult, SequencePlan, situations


def _kept(events: Sequence[Event], minimum: Significance) -> tuple[Event, ...]:
    return tuple(event for event in events if event.significance.rank >= minimum.rank)


def build_document(
    plan: SequencePlan,
    intervals: Sequence[IntervalResult],
    *,
    campaign: CampaignGroup,
    settings: Settings,
    narrative: Sequence[Event] | None,
    min_significance: Significance = Significance.TRIVIAL,
) -> dict[str, Any]:
    """The report document.

    Objective, inferred and narrative events below ``min_significance`` are dropped and counted (``omitted`` per
    interval, ``narrative_omitted`` for the narrative), so an omission is never hidden; state changes are never
    filtered. With ``narrative``, the document also holds the ``settings`` and the ``glossary`` of every entity ID it
    references.
    """
    document: dict[str, Any] = {"campaign": campaign.to_dict(), **plan.to_dict()}
    reports = situations(intervals)
    document["saves"] = [
        {**save, "situation": reports[position].to_dict() if position < len(reports) else None}
        for position, save in enumerate(document["saves"])
    ]
    document["min_significance"] = min_significance.value
    document["settings"] = None if narrative is None else settings.to_dict()
    listed = None if narrative is None else _kept(narrative, min_significance)
    document["narrative"] = None if listed is None or narrative is None else [event.to_dict() for event in listed]
    document["narrative_omitted"] = None if listed is None or narrative is None else len(narrative) - len(listed)
    rendered: list[dict[str, Any]] = []
    for interval in intervals:
        objective = _kept(interval.objective, min_significance)
        inferred = None if interval.inferred is None else _kept(interval.inferred, min_significance)
        entry = replace(interval, objective=objective, inferred=inferred).to_dict()
        entry["omitted"] = {
            "objective": len(interval.objective) - len(objective),
            "inferred": None
            if inferred is None or interval.inferred is None
            else len(interval.inferred) - len(inferred),
        }
        rendered.append(entry)
    document["intervals"] = rendered
    document["glossary"] = None if narrative is None else build_glossary(document, reports)
    return document
