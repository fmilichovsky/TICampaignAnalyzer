"""The nation metric narrative rules: band shifts, population collapse, per-capita GDP trajectory, nuclear arcs.

No rule names why a value changed: the causes stay evidence for the narrator.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..analyzers.politics.bands import BANDS, crossed, rest_value_delta
from ..analyzers.politics.nation_economy import MONTHS_PER_QUARTER, TREND_QUARTERS
from ..analyzers.politics.nation_population import DROP
from ..config import GeopoliticsSettings, NarrativeSettings, NationMetricsSettings
from ..kinds import campaign as campaign_kinds
from ..kinds import nations as nation_kinds
from ..kinds.control import TAKEOVER
from ..kinds.nations import (
    BREAKAWAY,
    CESSION,
    COHESION_SHIFT,
    ECONOMIC_TRAJECTORY,
    EDUCATION_SHIFT,
    EXPANSION,
    GOVERNMENT_SHIFT,
    INEQUALITY_SHIFT,
    MERGER,
    MILTECH_SHIFT,
    NUCLEAR_ARMAMENT,
    NUCLEAR_BUILDUP,
    NUCLEAR_DISARMAMENT,
    POPULATION_COLLAPSE,
    RELEASE,
    UNREST_SHIFT,
)
from ..kinds.wars import WAR_ARC
from ..model.entities import EntityId
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind
from ..model.values import FrozenMap, Observed
from .aggregation import Join, NarrativeBuilder, interval_reports
from .chronology import interval_of
from .geopolitics import (
    MergerParties,
    bounded_shifts,
    gdp_rank,
    metric_shifts,
    strength_rank,
)
from .rulekit import (
    by_subject,
    by_type,
    chained,
    earliest,
    intervals_of,
    last_date,
    latest,
    overlaps,
    refs_attribute,
    shifted,
    sorted_keys,
    subject,
    within,
)
from .situation import SituationReport
from .stream import EventStream

BAND_CROSSED = nation_kinds.BAND_CROSSED.event_type
NUCLEAR_STRIKES_CHANGED = campaign_kinds.NUCLEAR_STRIKES_CHANGED.event_type
NUCLEAR_ARC = "nation.nuclear_arc"
NUCLEAR_WEAPONS = "numNuclearWeapons"
NUCLEAR_SHARE = 0.5
"""A buildup gains, and a disarmament loses, at least this share of the arsenal it started from."""
LARGE_ARSENAL = 10
"""Dismantling an arsenal at least this large to zero is campaign defining."""
TREND_WINDOW_DAYS = round(TREND_QUARTERS * MONTHS_PER_QUARTER * 365.25 / 12)

BAND_SHIFTS: Mapping[str, EventKind] = {
    "unrest": UNREST_SHIFT,
    "democracy": GOVERNMENT_SHIFT,
    "education": EDUCATION_SHIFT,
    "cohesion": COHESION_SHIFT,
    "inequality": INEQUALITY_SHIFT,
    "militaryTechLevel": MILTECH_SHIFT,
}

SHIFT_EXPLAINERS = frozenset(kind.event_type for kind in (TAKEOVER, EXPANSION, CESSION, MERGER, RELEASE, BREAKAWAY))
"""Their metric shifts explain the affected nations' band changes."""
REST_VALUE_FILTERED = frozenset({"unrest", "cohesion"})
"""The game converges these towards a rest value; a crossing that drift alone explains is not a story."""
UNREST_SEVERE = 4.5
"""The lower bound of Insurgency."""
COHESION_EXTREMES = (1.0, 9.0)
"""Fragmented below the first, Hegemonic and Monolithic from the second."""
ALWAYS_MAJOR = frozenset({"democracy", "education", "militaryTechLevel"})

PROMOTED = {
    Significance.TRIVIAL: Significance.MINOR,
    Significance.MINOR: Significance.MAJOR,
    Significance.MAJOR: Significance.CAMPAIGN_DEFINING,
    Significance.CAMPAIGN_DEFINING: Significance.CAMPAIGN_DEFINING,
}


def _number(value: Observed) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _crosses(boundary: float, before: float, after: float) -> bool:
    return (before < boundary) != (after < boundary)


@dataclass(frozen=True)
class BandShiftRule:
    """``nation.<statistic>_shift``: a nation's ``statistic`` moved into another game band, and held there.

    Cohesion bands are one unit wide, so a cohesion crossing must also move two bands or cross an extreme. A report
    after ``band_hold_days`` cannot refute a crossing: a band held that long is a story even if it reverts.
    """

    statistic: str
    settings: NationMetricsSettings
    geopolitics: GeopoliticsSettings
    reads: frozenset[str] = frozenset()

    @property
    def explains(self) -> frozenset[str]:
        return SHIFT_EXPLAINERS | (
            frozenset({WAR_ARC.event_type}) if self.statistic in {"unrest", "cohesion"} else frozenset()
        )

    @property
    def name(self) -> str:
        return BAND_SHIFTS[self.statistic].event_type

    @property
    def emitted_types(self) -> frozenset[str]:
        return frozenset({self.name})

    @property
    def window_days(self) -> int:
        return self.settings.band_hold_days

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        crossings = [event for event in by_type(stream, BAND_CROSSED) if event.attribute("statistic") == self.statistic]
        explainers = by_type(stream, *self.explains)
        reports = interval_reports(situations)
        following = {id(report): later for report, later in zip(situations, situations[1:], strict=False)}
        built = []
        for crossing in crossings:
            nation = subject(crossing)
            before, after = _number(crossing.attribute("before")), _number(crossing.attribute("after"))
            pair = reports.get(interval_of(crossing.id))
            if nation is None or before is None or after is None or pair is None:
                continue
            boundary = _boundary(self.statistic, before, after)
            if not self._standalone(crossing, before, after):
                continue
            later = following.get(id(pair[1]))
            if (
                later is not None
                and within(latest(crossing), _date(later), self.settings.band_hold_days)
                and not _holds(later, nation.entity_id, self.statistic, before, boundary)
            ):
                continue
            if _explained(crossing, nation.entity_id, explainers):
                continue
            rank = gdp_rank(pair[1], nation.entity_id)
            level = self._level(before, after)
            if rank is not None and rank <= self.geopolitics.top_gdp_nations:
                level = PROMOTED[level]
            roles = [(Role.ACTOR, nation)]
            shifts = metric_shifts(stream, [nation.entity_id], [interval_of(crossing.id)])
            built.append(
                build.event(
                    BAND_SHIFTS[self.statistic],
                    id_parts=[nation.entity_id],
                    constituents=[crossing],
                    roles=roles,
                    join=Join.ENTITY,
                    attributes=(
                        ("statistic", self.statistic),
                        ("before", before),
                        ("after", after),
                        ("from_band", crossing.attribute("from_band")),
                        ("to_band", crossing.attribute("to_band")),
                        ("bands_crossed", crossing.attribute("bands_crossed")),
                        ("gdp_rank", rank),
                        *bounded_shifts(shifts, roles, self.geopolitics.metric_shifts_max),
                    ),
                    significance=level,
                    open=later is None,
                )
            )
        return built

    def _standalone(self, crossing: Event, before: float, after: float) -> bool:
        if self.statistic not in REST_VALUE_FILTERED:
            return True
        causes = crossing.attribute("causes")
        rest = rest_value_delta(causes) if isinstance(causes, FrozenMap) else 0.0
        filtered = crossed(self.statistic, before, after - rest)
        if filtered is None or (after > before) != (after - rest > before):
            return False
        if self.statistic != "cohesion":
            return True
        move = crossed(self.statistic, before, after)
        extreme = any(
            _crosses(boundary, before, after) and _crosses(boundary, before, after - rest)
            for boundary in COHESION_EXTREMES
        )
        return extreme or (move is not None and min(move.bands_crossed, filtered.bands_crossed) >= 2)

    def _level(self, before: float, after: float) -> Significance:
        move = crossed(self.statistic, before, after)
        bands = move.bands_crossed if move is not None else 0
        if self.statistic in ALWAYS_MAJOR:
            major = True
        elif self.statistic == "unrest":
            major = bands >= 2 or _crosses(UNREST_SEVERE, before, after)
        elif self.statistic == "cohesion":
            major = any(_crosses(boundary, before, after) for boundary in COHESION_EXTREMES)
        else:
            major = bands >= 2
        return Significance.MAJOR if major else Significance.MINOR


def _date(report: SituationReport) -> str | None:
    return report.date if isinstance(report.date, str) else None


def _boundary(statistic: str, before: float, after: float) -> float:
    move = crossed(statistic, before, after)
    return move.boundary if move is not None else after


def _holds(report: SituationReport, nation_id: EntityId, statistic: str, before: float, boundary: float) -> bool:
    item = next((item for item in report.nations if item.nation.entity_id == nation_id), None)
    value = _number(dict(item.statistics).get(statistic)) if item is not None else None
    return value is not None and _crosses(boundary, before, value)


def _explained(crossing: Event, nation_id: EntityId, explainers: Sequence[Event]) -> bool:
    key = interval_of(crossing.id)
    return any(
        key in explainer.intervals and any(ref.entity_id == nation_id for _, ref in explainer.roles)
        for explainer in explainers
    )


@dataclass(frozen=True)
class PopulationCollapseRule:
    """``nation.population_collapse``: a nation's population fell beyond what territory explains, in one interval."""

    settings: GeopoliticsSettings
    name: str = POPULATION_COLLAPSE.event_type
    emitted_types: frozenset[str] = frozenset({POPULATION_COLLAPSE.event_type})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    window_days: int | None = 0

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        reports = interval_reports(situations)
        strikes = by_type(stream, NUCLEAR_STRIKES_CHANGED)
        parties = MergerParties.of(stream)
        built = []
        for drop in by_type(stream, nation_kinds.POPULATION_CHANGED.event_type):
            nation = subject(drop)
            if nation is None or drop.attribute("direction") != DROP or parties.absorbed(nation, drop):
                continue
            key = interval_of(drop.id)
            nuclear = [strike for strike in strikes if interval_of(strike.id) == key]
            nuked = refs_attribute(drop, "nuked_regions")
            pair = reports.get(key)
            roles = [(Role.ACTOR, nation)]
            shifts = metric_shifts(stream, [nation.entity_id], [key])
            built.append(
                build.event(
                    POPULATION_COLLAPSE,
                    id_parts=[nation.entity_id],
                    constituents=[drop],
                    corroborating=nuclear,
                    roles=roles,
                    join=Join.ENTITY,
                    attributes=(
                        ("before", drop.attribute("before")),
                        ("after", drop.attribute("after")),
                        ("residual", drop.attribute("residual")),
                        ("relative_change", drop.attribute("relative_change")),
                        ("nuked_regions", nuked),
                        ("causes", drop.attribute("causes")),
                        ("gdp_rank", gdp_rank(pair[1], nation.entity_id) if pair is not None else None),
                        *bounded_shifts(shifts, roles, self.settings.metric_shifts_max),
                    ),
                    significance=Significance.CAMPAIGN_DEFINING if nuked or nuclear else Significance.MAJOR,
                    open=False,
                )
            )
        return built


@dataclass(frozen=True)
class EconomicTrajectoryRule:
    """``nation.economic_trajectory``: a nation's per-capita GDP boomed or slumped over years.

    The span starts on the first trend's ``window_start``, which can lie before the first save
    (``before_sequence``).
    """

    settings: GeopoliticsSettings
    name: str = ECONOMIC_TRAJECTORY.event_type
    emitted_types: frozenset[str] = frozenset({ECONOMIC_TRAJECTORY.event_type})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    window_days: int | None = TREND_WINDOW_DAYS

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        reports = interval_reports(situations)
        last_key = next(reversed(reports), None)
        parties = MergerParties.of(stream)
        trends = [
            event
            for event in by_type(stream, nation_kinds.PCGDP_TREND.event_type)
            if not parties.absorbed(subject(event), event)
        ]
        grouped = by_subject(trends)
        built = []
        for nation_id in sorted_keys(grouped):
            for run in _trend_runs(grouped[nation_id]):
                first, last = run[0], run[-1]
                nation = subject(first)
                start, end = _number(first.attribute("before")), _number(last.attribute("after"))
                if nation is None or start is None or end is None or start == 0:
                    continue
                pair = reports.get(interval_of(last.id))
                rank = gdp_rank(pair[1], nation_id) if pair is not None else None
                level = Significance.MAJOR
                if rank is not None and rank <= self.settings.top_gdp_nations:
                    level = PROMOTED[level]
                window_start = first.attribute("window_start")
                built.append(
                    build.event(
                        ECONOMIC_TRAJECTORY,
                        id_parts=[nation_id, first.attribute("quarter")],
                        constituents=run,
                        roles=[(Role.ACTOR, nation)],
                        join=Join.ENTITY,
                        attributes=(
                            ("direction", first.attribute("direction")),
                            ("start_quarter", _quarter(first) - TREND_QUARTERS),
                            ("end_quarter", _quarter(last)),
                            ("first_value", start),
                            ("last_value", end),
                            ("ratio", end / start),
                            ("before_sequence", any(event.attribute("before_sequence") is True for event in run)),
                            ("gdp_rank", rank),
                        ),
                        significance=level,
                        open=interval_of(last.id) == last_key,
                        starts_on=window_start if isinstance(window_start, str) else None,
                    )
                )
        return built


def _quarter(event: Event) -> int:
    value = event.attribute("quarter")
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _trend_runs(events: Sequence[Event]) -> list[list[Event]]:
    runs: list[list[Event]] = []
    for event in sorted(events, key=_quarter):
        previous = runs[-1][-1] if runs else None
        if (
            previous is not None
            and previous.attribute("direction") == event.attribute("direction")
            and _quarter(event) - _quarter(previous) <= TREND_QUARTERS
        ):
            runs[-1].append(event)
        else:
            runs.append([event])
    return runs


@dataclass(frozen=True)
class NuclearArcRule:
    """``nation.nuclear_armament`` / ``nuclear_buildup`` / ``nuclear_disarmament``: a nation's arsenal shifts, chained.

    The size of the move is the run's first ``before`` to its last ``after``; a smaller net move stays context.
    """

    settings: NationMetricsSettings
    geopolitics: GeopoliticsSettings
    name: str = NUCLEAR_ARC
    emitted_types: frozenset[str] = frozenset(
        {NUCLEAR_ARMAMENT.event_type, NUCLEAR_BUILDUP.event_type, NUCLEAR_DISARMAMENT.event_type}
    )
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()

    @property
    def window_days(self) -> int:
        return self.settings.nuclear_window_days

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        days = self.settings.nuclear_window_days
        reports = interval_reports(situations)
        parties = MergerParties.of(stream)
        shifts = [
            event
            for event in by_type(stream, nation_kinds.STATISTIC_SHIFTED.event_type)
            if event.attribute("statistic") == NUCLEAR_WEAPONS and not parties.merged(subject(event), event)
        ]
        programs = by_subject(
            event
            for event in by_type(stream, nation_kinds.NUCLEAR_PROGRAM_CHANGED.event_type)
            if event.attribute("after") is True
        )
        grouped = by_subject(shifts)
        built = []
        for nation_id in sorted_keys(grouped):
            for run in chained(grouped[nation_id], days):
                first, last = run[0], run[-1]
                nation = subject(first)
                start, end = _number(first.attribute("before")), _number(last.attribute("after"))
                pair = reports.get(intervals_of(run)[-1])
                if nation is None or start is None or end is None or pair is None:
                    continue
                report = pair[1]
                corroborating: list[Event] = []
                if start == 0 < end:
                    event_type = NUCLEAR_ARMAMENT.event_type
                    rank = gdp_rank(report, nation_id)
                    top = rank is not None and rank <= self.geopolitics.top_gdp_nations
                    level = Significance.CAMPAIGN_DEFINING if top else Significance.MAJOR
                    low = shifted(earliest(first), -days)
                    corroborating = [
                        event for event in programs.get(nation_id, []) if overlaps(event, low, latest(last))
                    ]
                elif 0 < start < end and (
                    end - start >= self.settings.nuclear_buildup_min or end - start >= NUCLEAR_SHARE * start
                ):
                    event_type, level = NUCLEAR_BUILDUP.event_type, Significance.MAJOR
                elif start > end and start - end >= NUCLEAR_SHARE * start:
                    event_type = NUCLEAR_DISARMAMENT.event_type
                    dismantled = end == 0 and start >= LARGE_ARSENAL
                    level = Significance.CAMPAIGN_DEFINING if dismantled else Significance.MAJOR
                else:
                    continue
                built.append(
                    build.event(
                        event_type,
                        id_parts=[nation_id],
                        constituents=run,
                        corroborating=corroborating,
                        roles=[(Role.ACTOR, nation)],
                        join=Join.ENTITY,
                        attributes=(
                            ("before", start),
                            ("after", end),
                            ("gdp_rank", gdp_rank(report, nation_id)),
                            ("strength_rank", strength_rank(report, nation_id)),
                        ),
                        significance=level,
                        open=within(latest(last), last_date(situations), days),
                    )
                )
        return built


def nation_metric_rules(
    settings: NarrativeSettings,
) -> tuple[BandShiftRule | PopulationCollapseRule | EconomicTrajectoryRule | NuclearArcRule, ...]:
    return (
        *(BandShiftRule(statistic, settings.nation_metrics, settings.geopolitics) for statistic in BANDS),
        PopulationCollapseRule(settings.geopolitics),
        EconomicTrajectoryRule(settings.geopolitics),
        NuclearArcRule(settings.nation_metrics, settings.geopolitics),
    )
