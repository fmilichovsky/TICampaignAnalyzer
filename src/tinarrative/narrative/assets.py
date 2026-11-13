"""The military, space-support and ranking narrative rules."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from ..analyzers.military.armies import APPEARED, DEPLOYMENT_TYPE_CHANGED, DISAPPEARED
from ..analyzers.politics.nation_assets import (
    BOOST_METRIC,
    GDP,
    MISSION_CONTROL_METRIC,
    NAVAL,
    RANKED_METRICS,
    STANDARD,
    STRENGTH,
)
from ..analyzers.politics.nation_rank import RANKED_PLACES
from ..analyzers.politics.nation_space import (
    BOOST_STATISTIC,
    GROWTH,
    MISSION_CONTROL_STATISTIC,
    SPACE_DEFENCES_STATISTIC,
)
from ..config import GeopoliticsSettings, NarrativeSettings, NationMetricsSettings
from ..kinds import military as military_kinds
from ..kinds import nations as nation_kinds
from ..kinds.nations import RANK_CHANGED, SPACE_ASSETS_CHANGED
from ..model.entities import EntityId
from ..model.events import Event, Role
from ..model.values import FrozenMap, Observed, number
from .aggregation import Join, NarrativeBuilder, interval_reports
from .chronology import interval_of
from .rulekit import NATION_ARMIES_CHANGED, army_home, by_subject, by_type, chained, intervals_of, sorted_keys, subject
from .significance import in_top_n
from .situation import Place, SituationReport
from .stream import EventStream

MILITARY_BUILDUP = military_kinds.MILITARY_BUILDUP.event_type
DEMOBILIZATION = military_kinds.DEMOBILIZATION.event_type
NAVY_ESTABLISHED = military_kinds.NAVY_ESTABLISHED.event_type
SPACE_PROGRAM_GROWTH = nation_kinds.SPACE_PROGRAM_GROWTH.event_type
SPACE_DEFENCES_ESTABLISHED = nation_kinds.SPACE_DEFENCES_ESTABLISHED.event_type
RANKING_CHANGED = nation_kinds.RANKING_CHANGED.event_type
BUILDUP_WINDOW_DAYS = 365
SPACE_METRICS = ((BOOST_STATISTIC, BOOST_METRIC), (MISSION_CONTROL_STATISTIC, MISSION_CONTROL_METRIC))


def _of_kind(event: Event, kind: str) -> bool:
    """A nation list event always may concern ``kind``."""
    if event.event_type in (APPEARED, DISAPPEARED):
        return event.attribute("deployment_type") == kind
    if event.event_type == DEPLOYMENT_TYPE_CHANGED:
        return kind in (event.attribute("before"), event.attribute("after"))
    return True


def _by_home(events: Sequence[Event]) -> dict[EntityId, list[Event]]:
    grouped: dict[EntityId, list[Event]] = defaultdict(list)
    for event in events:
        home = army_home(event)
        if home is not None:
            grouped[home.entity_id].append(event)
    return grouped


@dataclass(frozen=True)
class MilitaryBuildupRule:
    """``nation.military_buildup`` / ``nation.demobilization``: a nation's standard armies grew or shrank.

    The size of the move comes from the reports around the run, not from counting its events.
    """

    settings: NationMetricsSettings
    geopolitics: GeopoliticsSettings
    name: str = MILITARY_BUILDUP
    emitted_types: frozenset[str] = frozenset({MILITARY_BUILDUP, DEMOBILIZATION})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    window_days: int | None = BUILDUP_WINDOW_DAYS

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        build = build.scoring_with(self.geopolitics)  # TODO(#362): the top-rank rule reads ``top_gdp_nations``
        reports = interval_reports(situations)
        last_key = next(reversed(reports), None)
        candidates = [
            event
            for event in by_type(stream, APPEARED, DISAPPEARED, DEPLOYMENT_TYPE_CHANGED, NATION_ARMIES_CHANGED)
            if _of_kind(event, STANDARD) and stream.citable(event)
        ]
        grouped = _by_home(candidates)
        built = []
        for nation_id in sorted_keys(grouped):
            for run in chained(grouped[nation_id], BUILDUP_WINDOW_DAYS):
                keys = intervals_of(run)
                first, last = reports.get(keys[0]), reports.get(keys[-1])
                start = first[0].nation(nation_id) if first is not None else None
                end = last[1].nation(nation_id) if last is not None else None
                if last is None or start is None or end is None:
                    continue
                before, after = start.armies, end.armies
                if not isinstance(before, int) or not isinstance(after, int):
                    continue
                if abs(after - before) < self.settings.buildup_min_armies:
                    continue
                nation = end.nation
                built.append(
                    build.event(
                        military_kinds.MILITARY_BUILDUP if after > before else military_kinds.DEMOBILIZATION,
                        id_parts=[nation_id],
                        constituents=run,
                        roles=[(Role.ACTOR, nation)],
                        join=Join.ENTITY,
                        attributes=(
                            ("before", before),
                            ("after", after),
                            ("gdp_rank", last[1].rank(nation_id, GDP)),
                            ("strength_rank", last[1].rank(nation_id, STRENGTH)),
                        ),
                        open=keys[-1] == last_key,
                    )
                )
        return built


@dataclass(frozen=True)
class NavyEstablishedRule:
    """``nation.navy_established``: a nation without a naval army has one in the next report."""

    geopolitics: GeopoliticsSettings
    name: str = NAVY_ESTABLISHED
    emitted_types: frozenset[str] = frozenset({NAVY_ESTABLISHED})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    window_days: int | None = 0

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        build = build.scoring_with(self.geopolitics)  # TODO(#362): the top-rank rule reads ``top_gdp_nations``
        candidates = [
            event
            for event in by_type(stream, APPEARED, DEPLOYMENT_TYPE_CHANGED, NATION_ARMIES_CHANGED)
            if _of_kind(event, NAVAL) and stream.citable(event)
        ]
        grouped = _by_home(candidates)
        built = []
        for key, (earlier, later) in interval_reports(situations).items():
            for item in later.nations:
                nation_id = item.nation.entity_id
                previous = earlier.nation(nation_id)
                if previous is None or previous.navies != 0 or not isinstance(item.navies, int) or item.navies == 0:
                    continue
                cited = [event for event in grouped.get(nation_id, []) if interval_of(event.id) == key]
                if not cited:
                    continue
                built.append(
                    build.event(
                        military_kinds.NAVY_ESTABLISHED,
                        id_parts=[nation_id],
                        constituents=cited,
                        roles=[(Role.ACTOR, item.nation)],
                        join=Join.ENTITY,
                        attributes=(
                            ("navies", item.navies),
                            ("gdp_rank", later.rank(nation_id, GDP)),
                            ("strength_rank", later.rank(nation_id, STRENGTH)),
                        ),
                        open=False,
                    )
                )
        return built


@dataclass(frozen=True)
class SpaceProgramGrowthRule:
    """``nation.space_program_growth``: a nation's boost or mission control grew, once or in a chain."""

    settings: NationMetricsSettings
    name: str = SPACE_PROGRAM_GROWTH
    emitted_types: frozenset[str] = frozenset({SPACE_PROGRAM_GROWTH})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()

    @property
    def window_days(self) -> int:
        return self.settings.space_assets_window_days

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        reports = interval_reports(situations)
        last_key = next(reversed(reports), None)
        growth = [
            event
            for event in by_type(stream, SPACE_ASSETS_CHANGED.event_type)
            if event.attribute("direction") == GROWTH
            and event.attribute("statistic") in (BOOST_STATISTIC, MISSION_CONTROL_STATISTIC)
            and stream.citable(event)
        ]
        grouped = by_subject(growth)
        top = min(self.settings.ranking_top_n, RANKED_PLACES)
        built = []
        for nation_id in sorted_keys(grouped):
            for run in chained(grouped[nation_id], self.settings.space_assets_window_days):
                nation = subject(run[0])
                keys = intervals_of(run)
                first, last = reports.get(keys[0]), reports.get(keys[-1])
                if nation is None or first is None or last is None:
                    continue
                attributes: list[tuple[str, Observed]] = []
                entered = False
                for statistic, metric in SPACE_METRICS:
                    moves = [event for event in run if event.attribute("statistic") == statistic]
                    after_rank = last[1].rank(nation_id, metric)
                    entered = entered or (
                        nation_id in last[1].top(metric, top) and nation_id not in first[0].top(metric, top)
                    )
                    attributes.extend(
                        (
                            (f"{metric}_before", moves[0].attribute("before") if moves else None),
                            (f"{metric}_after", moves[-1].attribute("after") if moves else None),
                            (f"{metric}_territory_share", _territory_share(moves)),
                            (f"{metric}_rank", after_rank),
                        )
                    )
                built.append(
                    build.event(
                        nation_kinds.SPACE_PROGRAM_GROWTH,
                        id_parts=[nation_id],
                        constituents=run,
                        roles=[(Role.ACTOR, nation)],
                        join=Join.ENTITY,
                        attributes=(*attributes, ("entered_top", entered)),
                        open=keys[-1] == last_key,
                    )
                )
        return built


def _territory_share(moves: Sequence[Event]) -> float | None:
    """The share of the change that regions changing hands carried; ``None`` without a change."""
    deltas = [number(event.attribute("territory_delta")) for event in moves]
    changes = [
        (after - before)
        for event in moves
        if (before := number(event.attribute("before"))) is not None
        and (after := number(event.attribute("after"))) is not None
    ]
    total = sum(changes)
    if not moves or len(changes) != len(moves) or None in deltas or total == 0:
        return None
    return sum(delta for delta in deltas if delta is not None) / total


@dataclass(frozen=True)
class SpaceDefencesEstablishedRule:
    """``nation.space_defences_established``: a nation's first regions with space defences or STO fighters."""

    name: str = SPACE_DEFENCES_ESTABLISHED
    emitted_types: frozenset[str] = frozenset({SPACE_DEFENCES_ESTABLISHED})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    window_days: int | None = 0

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        built = []
        for event in by_type(stream, SPACE_ASSETS_CHANGED.event_type):
            nation = subject(event)
            if (
                nation is None
                or not stream.citable(event)
                or event.attribute("statistic") != SPACE_DEFENCES_STATISTIC
                or event.attribute("before") != 0
            ):
                continue
            built.append(
                build.event(
                    nation_kinds.SPACE_DEFENCES_ESTABLISHED,
                    id_parts=[nation.entity_id],
                    constituents=[event],
                    roles=[(Role.ACTOR, nation)],
                    join=Join.ENTITY,
                    attributes=(("regions", event.attribute("after")),),
                    open=False,
                )
            )
        return built


def _placed(report: SituationReport, nation_id: EntityId, metric: str, top: int) -> bool:
    """Tied places count, unlike ``SituationReport.top``."""
    return in_top_n(report.rank(nation_id, metric), top)


def _entry(place: Place) -> FrozenMap:
    return FrozenMap((("nation", place.nation), ("rank", place.rank), ("value", place.value)))


@dataclass(frozen=True)
class RankingRule:
    """``world.ranking_changed``: nations entered or left the top ``ranking_top_n`` by one metric in one interval.

    An entry the next report reverses is dropped; with no later report it is kept and the narrative event is open.
    """

    settings: NationMetricsSettings
    name: str = RANKING_CHANGED
    emitted_types: frozenset[str] = frozenset({RANKING_CHANGED})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    window_days: int | None = 0

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        reports = interval_reports(situations)
        following = {id(report): later for report, later in zip(situations, situations[1:], strict=False)}
        top = min(self.settings.ranking_top_n, RANKED_PLACES)
        changes: dict[tuple[str, str, EntityId], Event] = {}
        for event in by_type(stream, RANK_CHANGED.event_type):
            metric, nation = event.attribute("metric"), subject(event)
            if isinstance(metric, str) and nation is not None and stream.citable(event):
                changes[(interval_of(event.id), metric, nation.entity_id)] = event
        built = []
        for key, (earlier, report) in reports.items():
            later = following.get(id(report))
            for metric in RANKED_METRICS:
                entrants = [
                    place
                    for nation, place in report.top(metric, top).items()
                    if not _placed(earlier, nation, metric, top)
                    and (later is None or _placed(later, nation, metric, top))
                ]
                leavers = [
                    place
                    for nation, place in earlier.top(metric, top).items()
                    if not _placed(report, nation, metric, top)
                    and (later is None or not _placed(later, nation, metric, top))
                ]
                cited = {
                    place.nation.entity_id: change
                    for place in (*entrants, *leavers)
                    if (change := changes.get((key, metric, place.nation.entity_id))) is not None
                }
                entrants = [place for place in entrants if place.nation.entity_id in cited]
                leavers = [place for place in leavers if place.nation.entity_id in cited]
                if not entrants and not leavers:
                    continue
                built.append(
                    build.event(
                        nation_kinds.RANKING_CHANGED,
                        id_parts=[metric],
                        constituents=list(cited.values()),
                        roles=[
                            *((Role.BENEFICIARY, place.nation) for place in entrants),
                            *((Role.LOSER, place.nation) for place in leavers),
                        ],
                        join=Join.ENTITY,
                        attributes=(
                            ("metric", metric),
                            ("top", top),
                            ("entrants", tuple(_entry(place) for place in entrants)),
                            ("leavers", tuple(_entry(place) for place in leavers)),
                        ),
                        open=later is None,
                    )
                )
        return built


AssetRule = (
    MilitaryBuildupRule | NavyEstablishedRule | SpaceProgramGrowthRule | SpaceDefencesEstablishedRule | RankingRule
)


def asset_rules(settings: NarrativeSettings) -> tuple[AssetRule, ...]:
    return (
        MilitaryBuildupRule(settings.nation_metrics, settings.geopolitics),
        NavyEstablishedRule(settings.geopolitics),
        SpaceProgramGrowthRule(settings.nation_metrics),
        SpaceDefencesEstablishedRule(),
        RankingRule(settings.nation_metrics),
    )
