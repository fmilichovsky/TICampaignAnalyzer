"""The military, space-support and ranking narrative rules of architecture 11.3.

``MilitaryBuildupRule`` chains a nation's army appearances, disappearances and deployment changes within
``BUILDUP_WINDOW_DAYS``; a run whose standard armies (the situation reports' ``armies``, before its first interval and
after its last) moved by ``buildup_min_armies`` or more is a ``nation.military_buildup`` or a
``nation.demobilization``. ``NavyEstablishedRule`` builds ``nation.navy_established`` where a report's ``navies``
goes from zero to more. Both are major, promoted one level for a nation among the ``top_gdp_nations`` by ``GDP`` or
by the strength estimate.

``SpaceProgramGrowthRule`` chains a nation's ``nation.space_assets_changed`` growth of boost or mission control within
``space_assets_window_days`` into one ``nation.space_program_growth``, with the share of each statistic's growth that
regions changing hands carried: minor, major when the nation enters the top ``ranking_top_n`` by boost or mission
control over the run. ``SpaceDefencesEstablishedRule`` builds ``nation.space_defences_established`` from a
``spaceDefences`` rise from zero, major.

``RankingRule`` builds one ``world.ranking_changed`` per interval and ranked metric whose top ``ranking_top_n``
(at most ``RANKED_PLACES``) changed membership between the interval's reports, from the ``nation.rank_changed``
events of the nations entering and leaving it. A nation enters from a place outside the top into clear membership
(``top_members``: above zero and above the first value outside it) and leaves from clear membership to a place
outside, so a tie across the boundary (many nations share small mission control values) never enters or leaves. An
entry the next report reverses is dropped; with no report after the interval it is kept and the development is
``open``. Major.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
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
from ..analyzers.politics.nation_rank import RANK_CHANGED, RANKED_PLACES
from ..analyzers.politics.nation_space import (
    BOOST_STATISTIC,
    GROWTH,
    MISSION_CONTROL_STATISTIC,
    SPACE_ASSETS_CHANGED,
    SPACE_DEFENCES_STATISTIC,
)
from ..config import GeopoliticsSettings, NarrativeSettings, NationMetricsSettings
from ..model.entities import EntityId, EntityRef
from ..model.events import Event, Role, Significance
from ..model.values import FrozenMap, Observed
from .aggregation import Join, NarrativeBuilder, interval_reports
from .chronology import interval_of
from .geopolitics import gdp_rank, strength_rank
from .nation_metrics import PROMOTED
from .rulekit import by_subject, by_type, chained, intervals_of, ref_attribute, sorted_keys, subject
from .situation import NationSituation, SituationReport

MILITARY_BUILDUP = "nation.military_buildup"
DEMOBILIZATION = "nation.demobilization"
NAVY_ESTABLISHED = "nation.navy_established"
SPACE_PROGRAM_GROWTH = "nation.space_program_growth"
SPACE_DEFENCES_ESTABLISHED = "nation.space_defences_established"
RANKING_CHANGED = "world.ranking_changed"
NATION_ARMIES_CHANGED = "nation.armies_changed"
BUILDUP_WINDOW_DAYS = 365
"""Army changes of one nation this soon after the previous join one buildup or demobilization."""
SPACE_METRICS = ((BOOST_STATISTIC, BOOST_METRIC), (MISSION_CONTROL_STATISTIC, MISSION_CONTROL_METRIC))
"""Each grown ``nation.space_assets_changed`` statistic and the metric it is ranked by."""

_REPORTED: dict[str, Callable[[NationSituation], Observed]] = {
    GDP: lambda item: dict(item.statistics).get(GDP),
    STRENGTH: lambda item: item.strength,
    BOOST_METRIC: lambda item: item.boost,
    MISSION_CONTROL_METRIC: lambda item: item.mission_control,
}
"""Each ranked metric as a situation report states it."""


def _number(value: Observed) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _row(report: SituationReport, nation_id: EntityId) -> NationSituation | None:
    return next((item for item in report.nations if item.nation.entity_id == nation_id), None)


def _ordered(report: SituationReport, metric: str) -> list[tuple[float, NationSituation]]:
    """The report's nations holding regions with a known value of ``metric``, largest first, ties by ID: the places
    ``nation.rank_changed`` reports."""
    value = _REPORTED[metric]
    known = [
        (number, item)
        for item in report.nations
        if isinstance(item.regions, int) and item.regions > 0 and (number := _number(value(item))) is not None
    ]
    return sorted(known, key=lambda pair: (-pair[0], pair[1].nation.entity_id.sort_key))


def report_rank(report: SituationReport, nation_id: EntityId, metric: str) -> int | None:
    """The nation's place by ``metric`` in the report (1 is the largest)."""
    ordered = _ordered(report, metric)
    return next((place for place, (_, item) in enumerate(ordered, start=1) if item.nation.entity_id == nation_id), None)


@dataclass(frozen=True)
class _Place:
    nation: EntityRef
    rank: int
    value: float


def top_members(report: SituationReport, metric: str, top: int) -> dict[EntityId, _Place]:
    """The nations clearly in the report's top ``top`` by ``metric``: within it, above zero and above the first value
    outside it, so a tie across the boundary (many nations share small mission control values) is in neither."""
    ordered = _ordered(report, metric)
    outside = ordered[top][0] if len(ordered) > top else None
    return {
        item.nation.entity_id: _Place(item.nation, place, value)
        for place, (value, item) in enumerate(ordered[:top], start=1)
        if value > 0 and (outside is None or value > outside)
    }


def _in_top(rank: Observed, top: int) -> bool:
    return isinstance(rank, int) and not isinstance(rank, bool) and rank <= top


def _promoted(level: Significance, report: SituationReport, nation_id: EntityId, top: int) -> Significance:
    if _in_top(gdp_rank(report, nation_id), top) or _in_top(strength_rank(report, nation_id), top):
        return PROMOTED[level]
    return level


def _home(event: Event) -> EntityRef | None:
    """The nation an army event belongs to: its ``home_nation``; a nation list event's own subject."""
    if event.event_type == NATION_ARMIES_CHANGED:
        return subject(event)
    return ref_attribute(event, "home_nation")


def _of_kind(event: Event, kind: str) -> bool:
    """Whether an army event concerns an army of deployment ``kind``; a nation list event always may."""
    if event.event_type in (APPEARED, DISAPPEARED):
        return event.attribute("deployment_type") == kind
    if event.event_type == DEPLOYMENT_TYPE_CHANGED:
        return kind in (event.attribute("before"), event.attribute("after"))
    return True


def _by_home(events: Sequence[Event]) -> dict[EntityId, list[Event]]:
    grouped: dict[EntityId, list[Event]] = defaultdict(list)
    for event in events:
        home = _home(event)
        if home is not None:
            grouped[home.entity_id].append(event)
    return grouped


@dataclass(frozen=True)
class MilitaryBuildupRule:
    """``nation.military_buildup`` / ``nation.demobilization``: a nation's standard armies grew or shrank."""

    settings: NationMetricsSettings
    geopolitics: GeopoliticsSettings
    name: str = MILITARY_BUILDUP
    order: int = 0
    window_days: int | None = BUILDUP_WINDOW_DAYS

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        reports = interval_reports(situations)
        last_key = next(reversed(reports), None)
        candidates = [
            event
            for event in by_type(stream, APPEARED, DISAPPEARED, DEPLOYMENT_TYPE_CHANGED, NATION_ARMIES_CHANGED)
            if _of_kind(event, STANDARD)
        ]
        grouped = _by_home(candidates)
        built = []
        for nation_id in sorted_keys(grouped):
            for run in chained(grouped[nation_id], BUILDUP_WINDOW_DAYS):
                keys = intervals_of(run)
                first, last = reports.get(keys[0]), reports.get(keys[-1])
                start = _row(first[0], nation_id) if first is not None else None
                end = _row(last[1], nation_id) if last is not None else None
                if last is None or start is None or end is None:
                    continue
                before, after = start.armies, end.armies
                if not isinstance(before, int) or not isinstance(after, int):
                    continue
                if abs(after - before) < self.settings.buildup_min_armies:
                    continue
                nation = end.nation
                level = _promoted(Significance.MAJOR, last[1], nation_id, self.geopolitics.top_gdp_nations)
                built.append(
                    build.event(
                        MILITARY_BUILDUP if after > before else DEMOBILIZATION,
                        id_parts=[nation_id],
                        constituents=run,
                        roles=[(Role.ACTOR, nation)],
                        join=Join.ENTITY,
                        attributes=(
                            ("before", before),
                            ("after", after),
                            ("gdp_rank", gdp_rank(last[1], nation_id)),
                            ("strength_rank", strength_rank(last[1], nation_id)),
                        ),
                        significance=level,
                        open=keys[-1] == last_key,
                    )
                )
        return built


@dataclass(frozen=True)
class NavyEstablishedRule:
    """``nation.navy_established``: a nation without a naval army has one in the next report."""

    geopolitics: GeopoliticsSettings
    name: str = NAVY_ESTABLISHED
    order: int = 0
    window_days: int | None = 0

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        candidates = [
            event
            for event in by_type(stream, APPEARED, DEPLOYMENT_TYPE_CHANGED, NATION_ARMIES_CHANGED)
            if _of_kind(event, NAVAL)
        ]
        grouped = _by_home(candidates)
        built = []
        for key, (earlier, later) in interval_reports(situations).items():
            for item in later.nations:
                nation_id = item.nation.entity_id
                previous = _row(earlier, nation_id)
                if previous is None or previous.navies != 0 or not isinstance(item.navies, int) or item.navies == 0:
                    continue
                cited = [event for event in grouped.get(nation_id, []) if interval_of(event.id) == key]
                if not cited:
                    continue
                built.append(
                    build.event(
                        NAVY_ESTABLISHED,
                        id_parts=[nation_id],
                        constituents=cited,
                        roles=[(Role.ACTOR, item.nation)],
                        join=Join.ENTITY,
                        attributes=(
                            ("navies", item.navies),
                            ("gdp_rank", gdp_rank(later, nation_id)),
                            ("strength_rank", strength_rank(later, nation_id)),
                        ),
                        significance=_promoted(Significance.MAJOR, later, nation_id, self.geopolitics.top_gdp_nations),
                        open=False,
                    )
                )
        return built


@dataclass(frozen=True)
class SpaceProgramGrowthRule:
    """``nation.space_program_growth``: a nation's boost or mission control grew, once or in a chain."""

    settings: NationMetricsSettings
    name: str = SPACE_PROGRAM_GROWTH
    order: int = 0

    @property
    def window_days(self) -> int:
        return self.settings.space_assets_window_days

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        reports = interval_reports(situations)
        last_key = next(reversed(reports), None)
        growth = [
            event
            for event in by_type(stream, SPACE_ASSETS_CHANGED)
            if event.attribute("direction") == GROWTH
            and event.attribute("statistic") in (BOOST_STATISTIC, MISSION_CONTROL_STATISTIC)
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
                    after_rank = report_rank(last[1], nation_id, metric)
                    entered = entered or (
                        nation_id in top_members(last[1], metric, top)
                        and nation_id not in top_members(first[0], metric, top)
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
                        SPACE_PROGRAM_GROWTH,
                        id_parts=[nation_id],
                        constituents=run,
                        roles=[(Role.ACTOR, nation)],
                        join=Join.ENTITY,
                        attributes=(*attributes, ("entered_top", entered)),
                        significance=Significance.MAJOR if entered else Significance.MINOR,
                        open=keys[-1] == last_key,
                    )
                )
        return built


def _territory_share(moves: Sequence[Event]) -> float | None:
    """The share of the summed change of ``moves`` that regions changing hands carried; ``None`` without a change."""
    deltas = [_number(event.attribute("territory_delta")) for event in moves]
    changes = [
        (after - before)
        for event in moves
        if (before := _number(event.attribute("before"))) is not None
        and (after := _number(event.attribute("after"))) is not None
    ]
    total = sum(changes)
    if not moves or len(changes) != len(moves) or None in deltas or total == 0:
        return None
    return sum(delta for delta in deltas if delta is not None) / total


@dataclass(frozen=True)
class SpaceDefencesEstablishedRule:
    """``nation.space_defences_established``: a nation's first regions with space defences or STO fighters."""

    name: str = SPACE_DEFENCES_ESTABLISHED
    order: int = 0
    window_days: int | None = 0

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        built = []
        for event in by_type(stream, SPACE_ASSETS_CHANGED):
            nation = subject(event)
            if (
                nation is None
                or event.attribute("statistic") != SPACE_DEFENCES_STATISTIC
                or event.attribute("before") != 0
            ):
                continue
            built.append(
                build.event(
                    SPACE_DEFENCES_ESTABLISHED,
                    id_parts=[nation.entity_id],
                    constituents=[event],
                    roles=[(Role.ACTOR, nation)],
                    join=Join.ENTITY,
                    attributes=(("regions", event.attribute("after")),),
                    significance=Significance.MAJOR,
                    open=False,
                )
            )
        return built


def _placed(report: SituationReport, nation_id: EntityId, metric: str, top: int) -> bool:
    """Whether the nation's place in the report is within the top ``top``, tied or not."""
    return _in_top(report_rank(report, nation_id, metric), top)


def _entry(place: _Place) -> FrozenMap:
    return FrozenMap((("nation", place.nation), ("rank", place.rank), ("value", place.value)))


@dataclass(frozen=True)
class RankingRule:
    """``world.ranking_changed``: nations entered or left the top ``ranking_top_n`` by one metric in one interval."""

    settings: NationMetricsSettings
    name: str = RANKING_CHANGED
    order: int = 0
    window_days: int | None = 0

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        reports = interval_reports(situations)
        following = {id(report): later for report, later in zip(situations, situations[1:], strict=False)}
        top = min(self.settings.ranking_top_n, RANKED_PLACES)
        changes: dict[tuple[str, str, EntityId], Event] = {}
        for event in by_type(stream, RANK_CHANGED):
            metric, nation = event.attribute("metric"), subject(event)
            if isinstance(metric, str) and nation is not None:
                changes[(interval_of(event.id), metric, nation.entity_id)] = event
        built = []
        for key, (earlier, report) in reports.items():
            later = following.get(id(report))
            for metric in RANKED_METRICS:
                entrants = [
                    place
                    for nation, place in top_members(report, metric, top).items()
                    if not _placed(earlier, nation, metric, top)
                    and (later is None or _placed(later, nation, metric, top))
                ]
                leavers = [
                    place
                    for nation, place in top_members(earlier, metric, top).items()
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
                        RANKING_CHANGED,
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
                        significance=Significance.MAJOR,
                        open=later is None,
                    )
                )
        return built


AssetRule = (
    MilitaryBuildupRule | NavyEstablishedRule | SpaceProgramGrowthRule | SpaceDefencesEstablishedRule | RankingRule
)


def asset_rules(settings: NarrativeSettings) -> tuple[AssetRule, ...]:
    """The military, space-support and ranking rules under ``settings``."""
    return (
        MilitaryBuildupRule(settings.nation_metrics, settings.geopolitics),
        NavyEstablishedRule(settings.geopolitics),
        SpaceProgramGrowthRule(settings.nation_metrics),
        SpaceDefencesEstablishedRule(),
        RankingRule(settings.nation_metrics),
    )
