"""The military, space-support and ranking rules over synthetic analyzer events and situation reports."""

from __future__ import annotations

from collections.abc import Sequence

from tests.narrative.support import atomic, nation, nation_row, situation, unification
from tinarrative.config import GeopoliticsSettings, NarrativeSettings, NationMetricsSettings
from tinarrative.kinds import attributes, describe_event
from tinarrative.kinds.military import APPEARED, DEMOBILIZATION, DISAPPEARED, MILITARY_BUILDUP, NAVY_ESTABLISHED
from tinarrative.kinds.nations import (
    RANK_CHANGED,
    RANKING_CHANGED,
    SPACE_ASSETS_CHANGED,
    SPACE_DEFENCES_ESTABLISHED,
    SPACE_PROGRAM_GROWTH,
)
from tinarrative.model.entities import EntityRef
from tinarrative.model.events import Event, Role, Significance
from tinarrative.model.kinds import EventKind
from tinarrative.model.values import FrozenMap, Observed
from tinarrative.narrative import aggregate, narrative_rules
from tinarrative.narrative.situation import NationSituation, SituationReport

K0 = "2032-01-01T00:00:00"
K1 = "2032-04-01T00:00:00"
K2 = "2032-07-01T00:00:00"
KEYS = (K0, K1, K2)
PREVIOUS = {K1: K0, K2: K1}
NORTH = nation("20", "Northland")
SOUTH = nation("21", "Southland")


def army(key: str, number: int, deployment: str = "Standard", kind: EventKind = APPEARED) -> Event:
    return atomic(
        f"{kind.event_type}/army:{number}",
        key,
        not_before=PREVIOUS[key],
        entities=(nation(str(number)),),
        attributes=attributes(
            kind, side="after" if kind is APPEARED else "before", home_nation=NORTH, deployment_type=deployment
        ),
    )


def space(key: str, statistic: str, before: float, after: float, territory: float = 0.0) -> Event:
    return atomic(
        f"{SPACE_ASSETS_CHANGED.event_type}/nation:20/{statistic}",
        key,
        not_before=PREVIOUS[key],
        entities=(NORTH,),
        attributes=attributes(
            SPACE_ASSETS_CHANGED,
            statistic=statistic,
            direction="growth" if after > before else "decline",
            before=before,
            after=after,
            relative_change=None if before == 0 else (after - before) / abs(before),
            territory_delta=territory,
            territory_share=territory / (after - before),
            regions_gained=(),
            regions_lost=(),
            interval_days=None,
        ),
    )


def rank(key: str, subject: EntityRef, before: int | None, after: int | None, metric: str = "GDP") -> Event:
    return atomic(
        f"{RANK_CHANGED.event_type}/{subject.entity_id}/{metric}",
        key,
        not_before=PREVIOUS[key],
        entities=(subject,),
        attributes=attributes(
            RANK_CHANGED,
            metric=metric,
            before_rank=before,
            after_rank=after,
            before=1.0 if before is not None else None,
            after=2.0 if after is not None else None,
        ),
        significance=Significance.TRIVIAL,
    )


def rows(north: dict[str, Observed], south: dict[str, Observed] | None = None) -> list[NationSituation]:
    """NORTH ranks below SOUTH by GDP and strength unless ``north`` says otherwise."""
    north_values: dict[str, Observed] = {"gdp": 10.0, "strength": 10.0, "regions": 1, **north}
    south_values: dict[str, Observed] = {"gdp": 100.0, "strength": 100.0, "regions": 1, **(south or {})}
    return [nation_row(NORTH, **north_values), nation_row(SOUTH, **south_values)]  # type: ignore[arg-type]


def reports(*north: dict[str, Observed], south: Sequence[dict[str, Observed]] = ()) -> list[SituationReport]:
    """One report per key, NORTH's values from ``north`` (and SOUTH's from ``south``), in order."""
    return [
        situation(key, nations=rows(values, south[index] if index < len(south) else None))
        for index, (key, values) in enumerate(zip(KEYS, north, strict=False))
    ]


def built(
    stream: Sequence[Event], situations: Sequence[SituationReport], kind: EventKind, **settings: object
) -> list[Event]:
    geopolitics = {key: value for key, value in settings.items() if key == "top_gdp_nations"}
    metrics = {key: value for key, value in settings.items() if key != "top_gdp_nations"}
    narrative = NarrativeSettings(
        geopolitics=GeopoliticsSettings(**geopolitics),  # type: ignore[arg-type]
        nation_metrics=NationMetricsSettings(**metrics),  # type: ignore[arg-type]
    )
    return [
        event
        for event in aggregate(stream, situations, narrative_rules(narrative))
        if event.event_type == kind.event_type
    ]


def test_standard_armies_growing_by_the_minimum_over_chained_appearances_are_a_buildup() -> None:
    stream = [army(K1, 110), army(K2, 111), army(K2, 112), army(K2, 113, "Naval")]
    situations = reports({"armies": 2}, {"armies": 3}, {"armies": 5})
    (buildup,) = built(stream, situations, MILITARY_BUILDUP, top_gdp_nations=1)
    assert buildup.significance is Significance.MAJOR and buildup.open
    assert buildup.intervals == (K1, K2)
    assert len(buildup.constituents) == 3  # the naval army is not a standard one
    assert dict(buildup.attributes) == {"before": 2, "after": 5, "gdp_rank": 2, "strength_rank": 2}
    assert describe_event(buildup) == "Northland (nation:20) built up its standard armies: 2 -> 5"


def test_a_top_nation_by_strength_is_promoted_and_one_army_is_no_buildup() -> None:
    situations = reports({"armies": 2, "strength": 500.0}, {"armies": 4, "strength": 500.0})
    (buildup,) = built([army(K1, 110), army(K1, 111)], situations, MILITARY_BUILDUP, top_gdp_nations=1)
    assert buildup.significance is Significance.CAMPAIGN_DEFINING and buildup.open  # K1 is the last interval
    assert built([army(K1, 110)], reports({"armies": 2}, {"armies": 3}), MILITARY_BUILDUP) == []
    assert built([army(K1, 110)], reports({"armies": 2}, {"armies": 4}), MILITARY_BUILDUP, buildup_min_armies=3) == []


def test_standard_armies_shrinking_are_a_demobilization() -> None:
    stream = [army(K1, 110, kind=DISAPPEARED), army(K1, 111, kind=DISAPPEARED)]
    (demobilization,) = built(stream, reports({"armies": 4}, {"armies": 2}), DEMOBILIZATION, top_gdp_nations=1)
    assert dict(demobilization.attributes)["after"] == 2
    assert describe_event(demobilization) == "Northland (nation:20) demobilized its standard armies: 4 -> 2"


def test_a_first_naval_army_establishes_a_navy() -> None:
    situations = reports({"navies": 0}, {"navies": 1}, {"navies": 2})
    (navy,) = built([army(K1, 110, "Naval"), army(K2, 111, "Naval")], situations, NAVY_ESTABLISHED, top_gdp_nations=1)
    assert navy.intervals == (K1,) and navy.significance is Significance.MAJOR and not navy.open
    assert dict(navy.attributes) == {"navies": 1, "gdp_rank": 2, "strength_rank": 2}
    assert describe_event(navy) == "Northland (nation:20) established a navy (1 naval army)"
    assert built([army(K1, 110, "Standard")], situations, NAVY_ESTABLISHED) == []


def test_chained_boost_growth_is_a_space_program_major_when_the_nation_enters_the_top() -> None:
    stream = [space(K1, "boost", 5.0, 8.0), space(K2, "boost", 8.0, 20.0, 12.0), space(K2, "missionControl", 2.0, 4.0)]
    situations = reports(
        {"boost": 5.0, "mission_control": 2.0},
        {"boost": 8.0},
        {"boost": 20.0, "mission_control": 4.0},
        south=[{"boost": 10.0}] * 3,
    )
    (program,) = built(stream, situations, SPACE_PROGRAM_GROWTH, ranking_top_n=1)
    assert program.significance is Significance.MAJOR and program.open
    attributes = dict(program.attributes)
    assert (attributes["boost_before"], attributes["boost_after"], attributes["boost_rank"]) == (5.0, 20.0, 1)
    assert (attributes["mission_control_before"], attributes["mission_control_after"]) == (2.0, 4.0)
    assert (attributes["boost_territory_share"], attributes["mission_control_territory_share"]) == (0.8, 0.0)
    assert attributes["entered_top"] is True
    assert describe_event(program) == (
        "Northland (nation:20) space program grew: boost 5.0 -> 20.0, mission control 2.0 -> 4.0"
    )
    (minor,) = built(stream, situations, SPACE_PROGRAM_GROWTH, ranking_top_n=2)
    assert minor.significance is Significance.MINOR


def test_first_space_defences_are_established_and_later_ones_are_not() -> None:
    stream = [space(K1, "spaceDefences", 0, 2), space(K2, "spaceDefences", 2, 4)]
    (defences,) = built(stream, reports({}, {}, {}), SPACE_DEFENCES_ESTABLISHED)
    assert defences.intervals == (K1,) and defences.significance is Significance.MAJOR
    assert describe_event(defences) == "Northland (nation:20) established space defences (2 regions)"


def test_a_top_change_confirmed_by_the_next_report_lists_entrants_and_leavers() -> None:
    stream = [rank(K1, NORTH, 2, 1), rank(K1, SOUTH, 1, 2)]
    situations = reports({}, {"gdp": 200.0}, {"gdp": 200.0})
    (ranking,) = built(stream, situations, RANKING_CHANGED, ranking_top_n=1)
    assert ranking.significance is Significance.MAJOR and not ranking.open
    assert ranking.roles == ((Role.BENEFICIARY, NORTH), (Role.LOSER, SOUTH))
    attributes = dict(ranking.attributes)
    assert (attributes["metric"], attributes["top"]) == ("GDP", 1)
    assert attributes["entrants"] == (FrozenMap((("nation", NORTH), ("rank", 1), ("value", 200.0))),)
    assert attributes["leavers"] == (FrozenMap((("nation", SOUTH), ("rank", 1), ("value", 100.0))),)
    assert describe_event(ranking) == "Top 1 by GDP changed: entered Northland (nation:20); left Southland (nation:21)"
    # Two places of ten: the membership of the top ten did not change.
    assert built(stream, situations, RANKING_CHANGED) == []


def test_a_top_change_the_next_report_reverses_is_dropped_and_the_last_one_is_open() -> None:
    reverted = reports({}, {"gdp": 200.0}, {})
    assert built([rank(K1, NORTH, 2, 1), rank(K1, SOUTH, 1, 2)], reverted, RANKING_CHANGED, ranking_top_n=1) == []
    (latest,) = built([rank(K2, NORTH, 2, 1)], reports({}, {}, {"gdp": 200.0}), RANKING_CHANGED, ranking_top_n=1)
    assert latest.open and latest.intervals == (K2,)
    assert describe_event(latest) == "Top 1 by GDP changed: entered Northland (nation:20)"


def test_a_tie_across_the_top_boundary_is_in_neither_and_zero_is_never_in_the_top() -> None:
    tied = {"mission_control": 2.0}
    situations = reports(tied, {"mission_control": 3.0}, {"mission_control": 3.0}, south=[tied] * 3)
    stream = [rank(K1, NORTH, 2, 1, "mission_control"), rank(K1, SOUTH, 1, 2, "mission_control")]
    # NORTH held the first place by ID while tied, so it did not enter; SOUTH never held it clearly, nor left.
    assert built(stream, situations, RANKING_CHANGED, ranking_top_n=1) == []
    zero = reports({"boost": 0.0}, {"boost": 0.0}, {"boost": 0.0}, south=[{"boost": 0.0}] * 3)
    assert built([rank(K1, NORTH, 2, 1, "boost")], zero, RANKING_CHANGED, ranking_top_n=1) == []


def test_a_merged_nation_leaving_a_top_is_the_merger_and_an_entrant_is_still_reported() -> None:
    merger = unification(K1, NORTH, SOUTH, not_before=K0)
    stream = [merger, rank(K1, NORTH, 2, 1), rank(K1, SOUTH, 1, 2)]
    (ranking,) = built(stream, reports({}, {"gdp": 200.0}, {"gdp": 200.0}), RANKING_CHANGED, ranking_top_n=1)
    assert ranking.roles == ((Role.BENEFICIARY, NORTH),)
    assert dict(ranking.attributes)["leavers"] == ()
    assert rank(K1, SOUTH, 1, 2).id not in ranking.constituents
    only_leaver = [unification(K1, SOUTH, NORTH, not_before=K0), rank(K1, NORTH, 1, 2)]
    situations = reports({"gdp": 200.0}, {}, {})
    assert built(only_leaver, situations, RANKING_CHANGED, ranking_top_n=1) == []


def test_assets_a_merger_moves_are_no_growth_or_buildup_of_their_own() -> None:
    merger = unification(K1, NORTH, SOUTH, not_before=K0)
    growth = [space(K1, "boost", 5.0, 8.0, 3.0)]
    assert built([merger, *growth], reports({}, {}, {}), SPACE_PROGRAM_GROWTH) == []
    assert built([merger, space(K2, "boost", 5.0, 8.0)], reports({}, {}, {}), SPACE_PROGRAM_GROWTH) != []
    armies = [army(K1, 110), army(K1, 111)]
    assert built([merger, *armies], reports({"armies": 2}, {"armies": 4}), MILITARY_BUILDUP) == []
    assert built([merger, army(K1, 110, "Naval")], reports({"navies": 0}, {"navies": 1}), NAVY_ESTABLISHED) == []
