"""The nation metric narrative rules of architecture 11.3: a nation moving into another of the game's value bands.

``BandShiftRule`` builds one development per ``nation.band_crossed`` of its statistic that is a story on its own,
named by the game's band labels (``analyzers.politics.bands``). A crossing is a story when:

- it survives the *rest-value filter* where the game converges the statistic towards a rest value (unrest,
  cohesion): the later value minus the interval's ``*MovementToRestValue`` cause delta is still past the boundary.
  Cohesion bands are one unit wide, so a cohesion crossing also has to move two bands, with and without the rest
  value, or cross an extreme;
- it holds: when the report after the crossing's interval is dated within ``band_hold_days`` of the crossing, the
  nation's value there is still on the new side of the boundary. A later report cannot refute it (a band held that
  long is a story even if it reverts), and a crossing in the last interval has none yet: it is kept and ``open``;
- no development already carries it: a takeover, expansion, cession, release or breakaway naming the nation in the
  same interval states the shift in its ``metric_shifts`` (and a ``war.arc`` does for unrest and cohesion).

A shift of a nation among the ``top_gdp_nations`` by ``GDP`` is promoted one level. No rule names why the band
changed: the causes stay evidence for the narrator.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..analyzers.politics.bands import BANDS, crossed, rest_value_delta
from ..config import GeopoliticsSettings, NarrativeSettings, NationMetricsSettings
from ..model.entities import EntityId
from ..model.events import Event, Role, Significance
from ..model.values import FrozenMap, Observed
from .aggregation import Join, NarrativeBuilder, interval_reports
from .chronology import interval_of
from .geopolitics import (
    BREAKAWAY,
    CESSION,
    EXPANSION,
    RELEASE,
    TAKEOVER,
    WAR_ARC,
    bounded_shifts,
    gdp_rank,
    metric_shifts,
)
from .rulekit import by_type, latest, subject, within
from .situation import SituationReport

BAND_CROSSED = "nation.band_crossed"

BAND_SHIFTS: Mapping[str, str] = {
    "unrest": "nation.unrest_shift",
    "democracy": "nation.government_shift",
    "education": "nation.education_shift",
    "cohesion": "nation.cohesion_shift",
    "inequality": "nation.inequality_shift",
    "militaryTechLevel": "nation.miltech_shift",
}
"""The development type of each banded statistic."""

SHIFT_CARRIERS = frozenset({TAKEOVER, EXPANSION, CESSION, RELEASE, BREAKAWAY})
"""Developments whose ``metric_shifts`` already state a band shift of their nations."""
WAR_CARRIED = frozenset({"unrest", "cohesion"})
"""Statistics a war moves, so a ``war.arc`` naming the nation carries their shifts too."""
REST_VALUE_FILTERED = frozenset({"unrest", "cohesion"})
"""Statistics the game converges towards a rest value, so their crossings pass the rest-value filter."""
UNREST_SEVERE = 4.5
"""The lower bound of Insurgency: entering or leaving it or worse is a major unrest shift."""
COHESION_EXTREMES = (1.0, 9.0)
"""Fragmented below the first, Hegemonic and Monolithic from the second: cohesion crossing one is a story."""
ALWAYS_MAJOR = frozenset({"democracy", "education", "militaryTechLevel"})

_PROMOTED = {
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

    One development per qualifying ``nation.band_crossed``, by entity; the levels are in ``_level``.
    """

    statistic: str
    settings: NationMetricsSettings
    geopolitics: GeopoliticsSettings
    order: int = 2

    @property
    def name(self) -> str:
        return BAND_SHIFTS[self.statistic]

    @property
    def window_days(self) -> int:
        return self.settings.band_hold_days

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        crossings = [event for event in by_type(stream, BAND_CROSSED) if event.attribute("statistic") == self.statistic]
        carriers = by_type(stream, *SHIFT_CARRIERS, *((WAR_ARC,) if self.statistic in WAR_CARRIED else ()))
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
            if _carried(crossing, nation.entity_id, carriers):
                continue
            rank = gdp_rank(pair[1], nation.entity_id)
            level = self._level(before, after)
            if rank is not None and rank <= self.geopolitics.top_gdp_nations:
                level = _PROMOTED[level]
            roles = [(Role.ACTOR, nation)]
            shifts = metric_shifts(stream, [nation.entity_id], [interval_of(crossing.id)])
            built.append(
                build.event(
                    self.name,
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
    """Whether the nation's value in ``report`` is still on the far side of ``boundary`` from ``before``."""
    item = next((item for item in report.nations if item.nation.entity_id == nation_id), None)
    value = _number(dict(item.statistics).get(statistic)) if item is not None else None
    return value is not None and _crosses(boundary, before, value)


def _carried(crossing: Event, nation_id: EntityId, carriers: Sequence[Event]) -> bool:
    key = interval_of(crossing.id)
    return any(
        key in carrier.intervals and any(ref.entity_id == nation_id for _, ref in carrier.roles) for carrier in carriers
    )


def nation_metric_rules(settings: NarrativeSettings) -> tuple[BandShiftRule, ...]:
    """One band-shift rule per banded statistic, under ``settings``."""
    return tuple(BandShiftRule(statistic, settings.nation_metrics, settings.geopolitics) for statistic in BANDS)
