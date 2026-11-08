"""Chapters of a narrator package under a token budget. See architecture 20.3 and 20.4.

A chapter package selects entries of the package and never rewrites one, so an ID means the same event in both.
Continuity is built from the package, never from earlier prose, so a plan is deterministic.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..config import NarratorSettings
from .request import build_request, digest, prompt_version, render_request

PERIODS = ("year", "half", "quarter")
LONGEST_DAYS = {"year": 366, "half": 184, "quarter": 92}
"""Saves further apart than this, by median, are too sparse to tell the period."""
SIGNIFICANCE = ("trivial", "minor", "major", "campaign_defining")
RECALLED_FROM = "major"
LENGTH_WEIGHTS = {"trivial": 1, "minor": 1, "major": 2, "campaign_defining": 4}
REDUCTIONS = ("atomic_dropped", "split")
PLANNER_KEYS = (
    "max_input_tokens",
    "chars_per_token",
)
"""Recorded in ``plan.json``; the provider keys never change a plan."""


@dataclass(frozen=True)
class Chapter:
    """``first`` and ``last`` are inclusive interval positions in the package."""

    first: int
    last: int
    atomic: bool = True
    reduction: str | None = None


@dataclass(frozen=True)
class PlannedChapter:
    chapter: Chapter
    index: int
    part: str
    covers: tuple[str, str]
    periods: tuple[str, ...]
    period: str
    period_basis: str
    """``requested``, ``campaign_span`` (``derive_period``) or ``save_spacing`` (coarsened)."""
    narrative_events: int
    continuing: int
    recalled: int
    estimate: int
    request: dict[str, Any]

    @property
    def request_sha256(self) -> str:
        return hashlib.sha256(render_request(self.request).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChapterPlan:
    package_sha256: str
    options: dict[str, str]
    length: int | None
    settings: NarratorSettings
    chapters: tuple[PlannedChapter, ...]
    sparse: tuple[str, ...]
    """Requested-period labels the saves are too far apart for; empty when no period was requested."""

    def to_dict(self) -> dict[str, Any]:
        """No time and no path, so the same inputs give the same bytes."""
        return {
            "prompt_version": prompt_version(),
            "package_sha256": self.package_sha256,
            "settings": {key: getattr(self.settings, key) for key in PLANNER_KEYS},
            "request": {**self.options, **({} if self.length is None else {"length": self.length})},
            "chapters": [
                {
                    "index": planned.index,
                    "part": planned.part,
                    "covers": {"from": planned.covers[0], "to": planned.covers[1]},
                    "periods": list(planned.periods),
                    "period": planned.period,
                    "period_basis": planned.period_basis,
                    "intervals": planned.chapter.last - planned.chapter.first + 1,
                    "narrative_events": planned.narrative_events,
                    "continuing": planned.continuing,
                    "recalled": planned.recalled,
                    "estimate": planned.estimate,
                    "reduction": planned.chapter.reduction,
                    "request_sha256": planned.request_sha256,
                }
                for planned in self.chapters
            ],
        }


@dataclass(frozen=True)
class OverBudget:
    """A single interval whose request, without atomic stream, needs more than the budget."""

    interval: str
    needed: int
    budget: int


def validate(package: object) -> dict[str, Any]:
    if not isinstance(package, dict) or not all(
        isinstance(package.get(key), list) for key in ("saves", "intervals", "narrative", "glossary")
    ):
        raise ValueError("not a narrator package: run tinarrative events with --narrative --format json")
    for interval in package["intervals"]:
        if not isinstance(interval, dict) or not all(
            isinstance(interval.get(key), str) for key in ("key", "not_before", "date")
        ):
            raise ValueError("not a narrator package: an interval has no key or dates")
    return package


def period_label(date: str, period: str) -> str:
    """``2032``, ``2032-H1`` or ``2032-Q2``."""
    moment = datetime.fromisoformat(date)
    if period == "year":
        return f"{moment.year:04d}"
    if period == "half":
        return f"{moment.year:04d}-H{(moment.month - 1) // 6 + 1}"
    return f"{moment.year:04d}-Q{(moment.month - 1) // 3 + 1}"


def derive_period(package: Mapping[str, Any], settings: NarratorSettings) -> str:
    """Quarter for a campaign spanning ``quarter_span_days`` or fewer, half up to ``half_span_days``, else year."""
    saves = package["saves"]
    span = (datetime.fromisoformat(saves[-1]["date"]) - datetime.fromisoformat(saves[0]["date"])).days
    if span <= settings.quarter_span_days:
        return "quarter"
    if span <= settings.half_span_days:
        return "half"
    return "year"


def base_options(
    package: Mapping[str, Any],
    settings: NarratorSettings,
    *,
    period: str | None = None,
    audience: str | None = None,
    citations: str | None = None,
    style: str | None = None,
    focus: str | None = None,
) -> dict[str, str]:
    """``focus`` defaults to the player faction for an ``insider`` audience."""
    if focus is None and audience == "insider":
        situation = package["saves"][-1].get("situation") if package["saves"] else None
        name = situation.get("player_faction_name") if isinstance(situation, dict) else None
        focus = name if isinstance(name, str) and name else None
    chosen = {
        "period": period or derive_period(package, settings),
        "audience": audience,
        "citations": citations,
        "style": style,
        "focus": focus,
    }
    return {key: value for key, value in chosen.items() if value}


def estimate(request: Mapping[str, Any], chars_per_token: float) -> int:
    characters = len(request["system"]) + sum(len(message["content"]) for message in request["messages"])
    return math.ceil(characters / chars_per_token)


def referenced(node: Any) -> set[str]:
    """Includes the faction keys of ``shares`` and the ref strings of ``allies``."""
    if isinstance(node, dict):
        found = {node["ref"]} if isinstance(node.get("ref"), str) else set()
        if isinstance(node.get("shares"), dict):
            found.update(node["shares"])
        if isinstance(node.get("allies"), list):
            found.update(ally for ally in node["allies"] if isinstance(ally, str))
        for value in node.values():
            found |= referenced(value)
        return found
    if isinstance(node, list):
        return set().union(*(referenced(item) for item in node)) if node else set()
    return set()


def glossary_for(glossary: Sequence[Mapping[str, Any]], refs: set[str]) -> list[Mapping[str, Any]]:
    return [entry for entry in glossary if entry["ref"] in refs]


def plan_chapters(
    package: Mapping[str, Any],
    options: Mapping[str, str],
    settings: NarratorSettings,
    *,
    length: int | None = None,
    requested: bool = False,
) -> ChapterPlan | OverBudget:
    """narrative events are never dropped: a period that does not fit loses its atomic stream, then is split at saves;
    an interval that still does not fit is ``OverBudget``. A ``requested`` period is never coarsened."""
    planner = _Planner(validate(dict(package)), options, settings, length, requested)
    chapters = planner.plan()
    if isinstance(chapters, OverBudget):
        return chapters
    return planner.finish(chapters)


class _Planner:
    def __init__(
        self,
        package: dict[str, Any],
        options: Mapping[str, str],
        settings: NarratorSettings,
        length: int | None,
        requested: bool,
    ) -> None:
        if not package["intervals"]:
            raise ValueError("nothing to narrate: the package holds no interval")
        self.package = package
        self.options = dict(options)
        self.settings = settings
        self.length = length
        self.intervals: list[dict[str, Any]] = package["intervals"]
        self.save_position = {save["key"]: position for position, save in enumerate(package["saves"])}
        interval_position = {interval["key"]: position for position, interval in enumerate(self.intervals)}
        self.starts = [self._start_position(event, interval_position) for event in package["narrative"]]
        self.events: dict[str, Mapping[str, Any]] = {event["id"]: event for event in package["narrative"]}
        for interval in self.intervals:
            for event in self._atomic(interval):
                self.events.setdefault(event["id"], event)
        self.base = self.options.get("period", "year")
        self.requested = requested
        self.granularity = [self.base] * len(self.intervals)
        self.sparse = tuple(label for _, label in self._sparse()) if requested else ()
        if not requested:
            self._coarsen()
        self.periods = [
            period_label(interval["date"], period)
            for interval, period in zip(self.intervals, self.granularity, strict=True)
        ]

    def _sparse(self) -> list[tuple[str, str]]:
        """An interval belongs to the period of its closing save."""
        lengths: dict[tuple[str, str], list[int]] = {}
        for interval, period in zip(self.intervals, self.granularity, strict=True):
            days = (datetime.fromisoformat(interval["date"]) - datetime.fromisoformat(interval["not_before"])).days
            lengths.setdefault((period, period_label(interval["date"], period)), []).append(days)
        return [key for key, days in lengths.items() if statistics.median(days) > LONGEST_DAYS[key[0]]]

    def _coarsen(self) -> None:
        """Calendar periods nest, so coarsened labels stay contiguous and never overlap."""
        while coarsened := [(period, label) for period, label in self._sparse() if period != "year"]:
            parents: set[tuple[str, str]] = set()
            for period, label in coarsened:
                coarser = PERIODS[PERIODS.index(period) - 1]
                parents.update(
                    (coarser, period_label(interval["date"], coarser))
                    for interval, current in zip(self.intervals, self.granularity, strict=True)
                    if current == period and period_label(interval["date"], period) == label
                )
            for position, interval in enumerate(self.intervals):
                for coarser, label in parents:
                    finer = PERIODS.index(self.granularity[position]) > PERIODS.index(coarser)
                    if finer and period_label(interval["date"], coarser) == label:
                        self.granularity[position] = coarser

    def _period(self, chapter: Chapter) -> str:
        return self.granularity[chapter.first]

    def _period_basis(self, chapter: Chapter) -> str:
        if self.requested:
            return "requested"
        return "campaign_span" if self._period(chapter) == self.base else "save_spacing"

    def _start_position(self, event: Mapping[str, Any], interval_position: Mapping[str, int]) -> int:
        """Follows the prompt's period rule: a recorded start files by start, otherwise by the interval by which the
        narrative event was known."""
        start, end = event.get("start"), event.get("end")
        if isinstance(start, str) and (event.get("start_basis") == "record" or not isinstance(end, str)):
            position = 0
            for candidate, interval in enumerate(self.intervals):
                if interval["not_before"] <= start:
                    position = candidate
            return position
        if isinstance(end, str):
            for candidate, interval in enumerate(self.intervals):
                if interval["date"] >= end:
                    return candidate
            return len(self.intervals) - 1
        keys = [key for key in event.get("intervals") or () if key in interval_position]
        return interval_position[keys[0]] if keys else 0

    @staticmethod
    def _atomic(interval: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        return [*(interval.get("events") or ()), *(interval.get("inferred") or ())]

    # Planning

    def plan(self) -> list[Chapter] | OverBudget:
        groups: list[tuple[int, int]] = []
        for position, label in enumerate(self.periods):
            if groups and self.periods[groups[-1][0]] == label:
                groups[-1] = (groups[-1][0], position)
            else:
                groups.append((position, position))
        chapters: list[Chapter] = []
        current: Chapter | None = None
        for first, last in groups:
            if current is not None:
                grown = Chapter(current.first, last)
                if self.granularity[current.first] == self.granularity[first] and self._fits(grown, chapters):
                    current = grown
                    continue
                chapters.append(current)
                current = None
            alone = Chapter(first, last)
            if self._fits(alone, chapters):
                current = alone
                continue
            reduced = Chapter(first, last, atomic=False, reduction="atomic_dropped")
            if self._fits(reduced, chapters):
                chapters.append(reduced)
                continue
            failed = self._split(first, last, chapters)
            if failed is not None:
                return failed
        if current is not None:
            chapters.append(current)
        return chapters

    def _split(self, first: int, last: int, chapters: list[Chapter]) -> OverBudget | None:
        run: Chapter | None = None
        for position in range(first, last + 1):
            if run is not None:
                grown = Chapter(run.first, position, atomic=False, reduction="split")
                if self._fits(grown, chapters):
                    run = grown
                    continue
                chapters.append(run)
            run = Chapter(position, position, atomic=False, reduction="split")
            needed = self._estimate(run, chapters)
            if needed > self.settings.max_input_tokens:
                return OverBudget(self.intervals[position]["key"], needed, self.settings.max_input_tokens)
        if run is not None:
            chapters.append(run)
        return None

    def _fits(self, chapter: Chapter, earlier: Sequence[Chapter]) -> bool:
        return self._estimate(chapter, earlier) <= self.settings.max_input_tokens

    def _estimate(self, chapter: Chapter, earlier: Sequence[Chapter]) -> int:
        """Values not known yet are taken at their largest, so a final request never exceeds its estimate."""
        widest = len(self.intervals)
        request = self._request(chapter, earlier, index=widest, count=widest, part="middle", length=self.length)
        return estimate(request, self.settings.chars_per_token)

    # Requests

    def finish(self, chapters: Sequence[Chapter]) -> ChapterPlan:
        count = len(chapters)
        shares = self._shares(chapters)
        planned: list[PlannedChapter] = []
        for position, chapter in enumerate(chapters):
            earlier = chapters[:position]
            part = _part(position, count)
            request = self._request(
                chapter, earlier, index=position + 1, count=count, part=part, length=shares[position]
            )
            continuity = self._continuity(chapter, earlier)
            planned.append(
                PlannedChapter(
                    chapter=chapter,
                    index=position + 1,
                    part=part,
                    covers=self._covers(chapter),
                    periods=tuple(dict.fromkeys(self.periods[chapter.first : chapter.last + 1])),
                    period=self._period(chapter),
                    period_basis=self._period_basis(chapter),
                    narrative_events=len(self._narrative_events(chapter)),
                    continuing=len(continuity["continuing"]),
                    recalled=len(continuity["earlier"]),
                    estimate=estimate(request, self.settings.chars_per_token),
                    request=request,
                )
            )
        return ChapterPlan(
            package_sha256=digest(self.package),
            options=self.options,
            length=self.length,
            settings=self.settings,
            chapters=tuple(planned),
            sparse=self.sparse,
        )

    def _shares(self, chapters: Sequence[Chapter]) -> list[int | None]:
        """Rounded by largest remainder so the shares add up to ``length``."""
        if self.length is None:
            return [None] * len(chapters)
        weights = [
            sum(LENGTH_WEIGHTS.get(str(event.get("significance")), 1) for event in self._narrative_events(chapter))
            for chapter in chapters
        ]
        if not any(weights):
            weights = [chapter.last - chapter.first + 1 for chapter in chapters]
        total = sum(weights)
        exact = [self.length * weight / total for weight in weights]
        shares = [math.floor(value) for value in exact]
        order = sorted(range(len(chapters)), key=lambda position: (shares[position] - exact[position], position))
        for position in order[: self.length - sum(shares)]:
            shares[position] += 1
        return [share or None for share in shares]

    def _request(
        self, chapter: Chapter, earlier: Sequence[Chapter], *, index: int, count: int, part: str, length: int | None
    ) -> dict[str, Any]:
        covers = self._covers(chapter)
        options = {
            "chapter": f"{index} of {count}",
            "part": part,
            "covers": f"{covers[0][:10]} to {covers[1][:10]}",
            **self.options,
            "period": self._period(chapter),
        }
        if length:
            options["length"] = f"about {length} words"
        return build_request(self.chapter_package(chapter, earlier, index=index, count=count, part=part), options)

    # Chapter packages

    def chapter_package(
        self, chapter: Chapter, earlier: Sequence[Chapter], *, index: int, count: int, part: str
    ) -> dict[str, Any]:
        narrative_events = self._narrative_events(chapter)
        continuity = self._continuity(chapter, earlier)
        roots = [*narrative_events, *continuity["continuing"]]
        kept = self._closure(roots) if chapter.atomic else set()
        intervals = [
            {
                **interval,
                "events": [event for event in interval.get("events") or () if event["id"] in kept],
                "inferred": None
                if interval.get("inferred") is None
                else [event for event in interval["inferred"] if event["id"] in kept],
            }
            for interval in self.intervals[chapter.first : chapter.last + 1]
        ]
        atomic = [event for interval in intervals for event in self._atomic(interval)]
        refs = referenced([narrative_events, continuity, atomic])
        told = referenced([narrative_events, continuity["continuing"], atomic])
        saves = [self._pruned(save, refs, told) for save in self._saves(chapter)]
        covers = self._covers(chapter)
        restricted: dict[str, Any] = {}
        for key, value in self.package.items():
            restricted[key] = {"saves": saves, "intervals": intervals, "narrative": narrative_events}.get(key, value)
        restricted["chapter"] = {
            "index": index,
            "count": count,
            "part": part,
            "covers": {"from": covers[0], "to": covers[1]},
        }
        restricted["continuity"] = continuity
        restricted["glossary"] = glossary_for(
            self.package["glossary"], referenced({key: value for key, value in restricted.items() if key != "glossary"})
        )
        return restricted

    def _narrative_events(self, chapter: Chapter) -> list[Mapping[str, Any]]:
        return [
            event
            for event, start in zip(self.package["narrative"], self.starts, strict=True)
            if chapter.first <= start <= chapter.last
        ]

    def _continuity(self, chapter: Chapter, earlier: Sequence[Chapter]) -> dict[str, Any]:
        """Still-running earlier narrative events in full, and a capped digest of the others from ``RECALLED_FROM``.

        A member listed as a digest is neither: the narrative event it belongs to carries it.
        """
        keys = {interval["key"] for interval in self.intervals[chapter.first : chapter.last + 1]}
        before = [
            (position, event)
            for position, (event, start) in enumerate(zip(self.package["narrative"], self.starts, strict=True))
            if start < chapter.first and "member_of" not in event
        ]
        continuing = [
            event for _, event in before if event.get("open") is True or keys & set(event.get("intervals") or ())
        ]
        told = {event["id"] for event in continuing}
        floor = SIGNIFICANCE.index(RECALLED_FROM)
        candidates = [
            (position, event) for position, event in before if event["id"] not in told and _rank(event) >= floor
        ]
        # The most significant first, then the latest; the kept ones are listed in package order.
        ranked = sorted(
            candidates, key=lambda item: (_rank(item[1]), _sort_text(item[1].get("start")), item[0]), reverse=True
        )
        recalled = sorted(position for position, _ in ranked[: self.settings.recalled_narrative_events])
        narrative = self.package["narrative"]
        return {
            "continuing": continuing,
            "earlier": [_digest(narrative[position]) for position in recalled],
            "earlier_omitted": len(candidates) - len(recalled),
        }

    def _closure(self, roots: Iterable[Mapping[str, Any]]) -> set[str]:
        seen: set[str] = set()
        pending = [constituent for root in roots for constituent in root.get("constituents") or ()]
        while pending:
            identifier = pending.pop()
            if identifier in seen:
                continue
            seen.add(identifier)
            pending.extend((self.events.get(identifier) or {}).get("constituents") or ())
        return seen

    def _saves(self, chapter: Chapter) -> list[Mapping[str, Any]]:
        saves = self.package["saves"]
        opening = self.save_position.get(self.intervals[chapter.first]["key"])
        closing = self.save_position.get(self.intervals[chapter.last]["key"])
        positions = [*(() if not opening else (opening - 1,)), *(() if closing is None else (closing,))]
        return [saves[position] for position in positions]

    def _pruned(self, save: Mapping[str, Any], refs: set[str], told: set[str]) -> Mapping[str, Any]:
        """Keeps referenced nations and the largest economies.

        A landless nation is never ranked and is kept only when ``told`` holds it; a mention in an earlier digest does
        not keep it.
        """
        situation = save.get("situation")
        if not isinstance(situation, dict) or not isinstance(situation.get("nations"), list):
            return save
        nations: list[Mapping[str, Any]] = situation["nations"]
        landless = {position for position, nation in enumerate(nations) if _landless(nation)}
        ranked = sorted(
            (
                (gdp, position)
                for position, nation in enumerate(nations)
                if position not in landless and (gdp := _gdp(nation)) is not None
            ),
            key=lambda item: (-item[0], item[1]),
        )
        largest = {position for _, position in ranked[: self.settings.top_economies]}
        kept = [
            nation
            for position, nation in enumerate(nations)
            if (nation.get("nation") or {}).get("ref") in (told if position in landless else refs)
            or position in largest
        ]
        return {**save, "situation": {**situation, "nations": kept}}

    def _covers(self, chapter: Chapter) -> tuple[str, str]:
        return self.intervals[chapter.first]["not_before"], self.intervals[chapter.last]["date"]


def _part(position: int, count: int) -> str:
    if count == 1:
        return "whole"
    if position == 0:
        return "first"
    return "last" if position == count - 1 else "middle"


def _rank(event: Mapping[str, Any]) -> int:
    significance = event.get("significance")
    return SIGNIFICANCE.index(significance) if significance in SIGNIFICANCE else -1


def _sort_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _digest(event: Mapping[str, Any]) -> dict[str, Any]:
    return {key: event.get(key) for key in ("id", "event_type", "significance", "start", "end", "roles")}


def _landless(nation: Mapping[str, Any]) -> bool:
    regions = nation.get("regions")
    return isinstance(regions, int) and not isinstance(regions, bool) and regions == 0


def _gdp(nation: Mapping[str, Any]) -> float | None:
    statistics = nation.get("statistics")
    value = statistics.get("GDP") if isinstance(statistics, dict) else None
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)
