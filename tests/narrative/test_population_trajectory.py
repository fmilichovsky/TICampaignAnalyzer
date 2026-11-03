"""The population collapse and economic trajectory rules over synthetic analyzer events and situation reports."""

from __future__ import annotations

from collections.abc import Sequence

from tests.narrative.support import atomic, nation, nation_row, situation, unification
from tinarrative.analyzers.render import describe_event
from tinarrative.config import GeopoliticsSettings, NarrativeSettings
from tinarrative.model.events import DateBasis, Event, Significance
from tinarrative.model.values import FrozenMap, Observed
from tinarrative.narrative import aggregate, narrative_rules
from tinarrative.narrative.nation_metrics import ECONOMIC_TRAJECTORY, POPULATION_COLLAPSE, TREND_WINDOW_DAYS
from tinarrative.narrative.situation import SituationReport

K0 = "2032-01-01T00:00:00"
K1 = "2032-04-01T00:00:00"
K2 = "2032-07-01T00:00:00"
PREVIOUS = {K1: K0, K2: K1}
NORTH = nation("20", "Northland")
SOUTH = nation("21", "Southland")
REGION = nation("40", "Coast")


def population(key: str, direction: str, *, nuked: Sequence[object] = ()) -> Event:
    return atomic(
        "nation.population_changed/nation:20",
        key,
        not_before=PREVIOUS[key],
        entities=(NORTH,),
        attributes=(
            ("direction", direction),
            ("before", 100.0),
            ("after", 70.0),
            ("residual", 70.0),
            ("relative_change", -0.3),
            ("nuked_regions", tuple(nuked)),  # type: ignore[arg-type]
            ("causes", FrozenMap((("GDPReason_PopulationChange", -2.0),))),
        ),
        significance=Significance.MAJOR,
    )


def trend(
    key: str,
    quarter: int,
    direction: str,
    before: float,
    after: float,
    *,
    backstory: bool = False,
    subject: object = NORTH,
) -> Event:
    year, index = divmod(quarter, 4)
    date = f"{2026 + year}-{3 * index + 1:02d}-01T00:00:00"
    start_year, start_index = divmod(quarter - 20, 4)
    return atomic(
        f"nation.pcgdp_trend/{subject.entity_id}/{quarter}",  # type: ignore[attr-defined]
        key,
        date=date,
        date_basis=DateBasis.RECORD,
        not_before=PREVIOUS.get(key, K0),
        entities=(subject,),  # type: ignore[arg-type]
        attributes=(
            ("direction", direction),
            ("quarter", quarter),
            ("window_quarters", 20),
            ("window_start", f"{2026 + start_year}-{3 * start_index + 1:02d}-01T00:00:00"),
            ("before", before),
            ("after", after),
            ("change", after / before - 1),
            ("before_sequence", backstory),
        ),
        significance=Significance.TRIVIAL,
    )


def reports(gdp: Observed = 1.0) -> list[SituationReport]:
    """Reports at K0, K1, K2; NORTH ranks first by GDP when ``gdp`` exceeds SOUTH's 100."""
    return [situation(key, nations=[nation_row(NORTH, gdp=gdp), nation_row(SOUTH, gdp=100.0)]) for key in (K0, K1, K2)]


def built(stream: Sequence[Event], situations: Sequence[SituationReport], kind: str, **settings: object) -> list[Event]:
    narrative = NarrativeSettings(geopolitics=GeopoliticsSettings(**settings))  # type: ignore[arg-type]
    return [event for event in aggregate(stream, situations, narrative_rules(narrative)) if event.event_type == kind]


def test_a_population_drop_is_a_major_collapse_and_growth_is_none() -> None:
    (collapse,) = built([population(K1, "drop"), population(K2, "growth")], reports(), POPULATION_COLLAPSE)
    assert collapse.significance is Significance.MAJOR and not collapse.open
    assert collapse.intervals == (K1,)
    assert collapse.attribute("residual") == 70.0 and collapse.attribute("nuked_regions") == ()
    assert collapse.attribute("causes") == FrozenMap((("GDPReason_PopulationChange", -2.0),))
    assert describe_event(collapse) == "Northland (nation:20) population collapse: 100.0 -> 70.0"


def test_a_collapse_with_a_detonation_or_a_nuclear_strike_is_campaign_defining() -> None:
    (nuked,) = built([population(K1, "drop", nuked=[REGION])], reports(), POPULATION_COLLAPSE)
    assert nuked.significance is Significance.CAMPAIGN_DEFINING
    strike = atomic("campaign.nuclear_strikes_changed/campaign", K1, not_before=K0)
    (struck,) = built([population(K1, "drop"), strike], reports(), POPULATION_COLLAPSE)
    assert struck.significance is Significance.CAMPAIGN_DEFINING and strike.id in struck.constituents
    late = atomic("campaign.nuclear_strikes_changed/campaign", K2, not_before=K1)
    (other,) = built([population(K1, "drop"), late], reports(), POPULATION_COLLAPSE)
    assert other.significance is Significance.MAJOR


def test_trends_of_one_direction_chain_into_one_trajectory_spanning_the_first_window() -> None:
    first, second = trend(K1, 22, "boom", 100.0, 160.0), trend(K2, 30, "boom", 120.0, 190.0)
    (trajectory,) = built([first, second], reports(), ECONOMIC_TRAJECTORY, top_gdp_nations=1)
    assert trajectory.id == f"{ECONOMIC_TRAJECTORY}/nation:20/22@{K1}"
    assert (trajectory.start, trajectory.start_basis) == ("2026-07-01T00:00:00", DateBasis.RECORD)
    assert (trajectory.end, trajectory.end_basis) == ("2033-07-01T00:00:00", DateBasis.RECORD)
    assert dict(trajectory.attributes) == {
        "direction": "boom",
        "start_quarter": 2,
        "end_quarter": 30,
        "first_value": 100.0,
        "last_value": 190.0,
        "ratio": 1.9,
        "before_sequence": False,
        "gdp_rank": 2,
    }
    assert trajectory.significance is Significance.MAJOR and trajectory.open
    assert describe_event(trajectory) == "Northland (nation:20) per-capita GDP boom: 100.0 -> 190.0"


def test_a_change_of_direction_or_a_gap_beyond_the_window_starts_a_new_trajectory() -> None:
    stream = [
        trend(K1, 22, "boom", 100.0, 160.0),
        trend(K1, 30, "slump", 160.0, 110.0),
        trend(K2, 51, "slump", 110.0, 80.0),
        trend(K1, 22, "slump", 100.0, 70.0, subject=SOUTH),
    ]
    trajectories = built(stream, reports(), ECONOMIC_TRAJECTORY)
    runs = [(event.entities[0].entity_id.key, event.attribute("start_quarter")) for event in trajectories]
    assert sorted(runs) == [("20", 2), ("20", 10), ("20", 31), ("21", 2)]


def test_a_backstory_trajectory_of_a_top_economy_is_promoted_and_closed_before_the_last_interval() -> None:
    (trajectory,) = built(
        [trend(K1, 22, "slump", 100.0, 60.0, backstory=True)],
        reports(gdp=500.0),
        ECONOMIC_TRAJECTORY,
        top_gdp_nations=1,
    )
    assert trajectory.attribute("before_sequence") is True and trajectory.attribute("ratio") == 0.6
    assert trajectory.significance is Significance.CAMPAIGN_DEFINING and not trajectory.open
    assert TREND_WINDOW_DAYS == 1826


def test_an_absorbed_nations_population_and_trend_are_the_mergers() -> None:
    absorbed = unification(K1, SOUTH, NORTH, not_before=K0)
    assert built([absorbed, population(K1, "drop")], reports(), POPULATION_COLLAPSE) == []
    assert built([absorbed, trend(K1, 24, "slump", 2.0, 1.0)], reports(), ECONOMIC_TRAJECTORY) == []
    gainer = unification(K1, NORTH, SOUTH, not_before=K0)
    assert built([gainer, population(K1, "drop")], reports(), POPULATION_COLLAPSE) != []
