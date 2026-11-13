"""The nuclear arc rule over synthetic arsenal shifts, program flags and situation reports."""

from __future__ import annotations

from tests.narrative.support import atomic, nation, nation_row, situation
from tinarrative.config import GeopoliticsSettings, NarrativeSettings, NationMetricsSettings
from tinarrative.kinds import attributes, describe_event
from tinarrative.kinds.nations import NUCLEAR_PROGRAM_CHANGED, STATISTIC_SHIFTED
from tinarrative.model.entities import EntityRef
from tinarrative.model.events import Event, Significance
from tinarrative.model.values import Observed
from tinarrative.narrative import aggregate, narrative_rules
from tinarrative.narrative.nation_metrics import NUCLEAR_ARMAMENT, NUCLEAR_BUILDUP, NUCLEAR_DISARMAMENT
from tinarrative.narrative.situation import SituationReport

K0 = "2032-01-01T00:00:00"
K1 = "2032-04-01T00:00:00"
K2 = "2032-07-01T00:00:00"
K3 = "2034-01-01T00:00:00"
K4 = "2034-04-01T00:00:00"
PREVIOUS = {K1: K0, K2: K1, K3: K2, K4: K3}
NORTH = nation("20", "Northland")
SOUTH = nation("21", "Southland")
ARCS = (NUCLEAR_ARMAMENT, NUCLEAR_BUILDUP, NUCLEAR_DISARMAMENT)


def weapons(key: str, before: int, after: int, subject: EntityRef = NORTH) -> Event:
    return atomic(
        f"{STATISTIC_SHIFTED.event_type}/{subject.entity_id}/numNuclearWeapons",
        key,
        not_before=PREVIOUS[key],
        entities=(subject,),
        attributes=attributes(
            STATISTIC_SHIFTED,
            statistic="numNuclearWeapons",
            before=before,
            after=after,
            relative_change=None if before == 0 else (after - before) / abs(before),
            interval_days=None,
        ),
        significance=Significance.MAJOR,
    )


def program(key: str, after: bool = True) -> Event:
    return atomic(
        f"{NUCLEAR_PROGRAM_CHANGED.event_type}/{NORTH.entity_id}",
        key,
        not_before=PREVIOUS[key],
        entities=(NORTH,),
        attributes=attributes(NUCLEAR_PROGRAM_CHANGED, transition="changed", before=not after, after=after),
    )


def reports(gdp: Observed = 1.0) -> list[SituationReport]:
    """Reports at K0..K4; NORTH ranks first by GDP when ``gdp`` exceeds SOUTH's 100."""
    return [
        situation(key, nations=[nation_row(NORTH, gdp=gdp), nation_row(SOUTH, gdp=100.0)]) for key in (K0, *PREVIOUS)
    ]


def built(stream: list[Event], situations: list[SituationReport] | None = None, **settings: object) -> list[Event]:
    narrative = NarrativeSettings(
        geopolitics=GeopoliticsSettings(top_gdp_nations=1),
        nation_metrics=NationMetricsSettings(**settings),  # type: ignore[arg-type]
    )
    events = aggregate(stream, reports() if situations is None else situations, narrative_rules(narrative))
    return [event for event in events if event.event_type in ARCS]


def test_a_first_weapon_is_an_armament_citing_the_program_start() -> None:
    start = program(K1)
    (arc,) = built([start, weapons(K2, 0, 1)])
    assert arc.event_type == NUCLEAR_ARMAMENT and arc.significance is Significance.MAJOR
    assert set(arc.constituents) == {weapons(K2, 0, 1).id, start.id}
    assert arc.start == K0 and arc.end == K2 and not arc.open
    assert dict(arc.attributes) == {"before": 0.0, "after": 1.0, "gdp_rank": 2, "strength_rank": None}
    assert describe_event(arc) == "Northland (nation:20) armed with nuclear weapons: 0.0 -> 1.0 nuclear weapons"


def test_an_armament_of_a_top_economy_is_campaign_defining_and_a_program_ending_is_not_cited() -> None:
    ended = program(K1, after=False)
    (arc,) = built([ended, weapons(K2, 0, 3)], reports(gdp=500.0))
    assert arc.significance is Significance.CAMPAIGN_DEFINING and ended.id not in arc.constituents


def test_a_buildup_needs_the_minimum_or_half_the_arsenal() -> None:
    (absolute,) = built([weapons(K1, 20, 25)])
    assert absolute.event_type == NUCLEAR_BUILDUP and absolute.significance is Significance.MAJOR
    assert (
        describe_event(absolute) == "Northland (nation:20) built up its nuclear arsenal: 20.0 -> 25.0 nuclear weapons"
    )
    (relative,) = built([weapons(K1, 2, 3)])
    assert relative.event_type == NUCLEAR_BUILDUP
    assert built([weapons(K1, 20, 24)]) == []
    assert built([weapons(K1, 20, 24)], nuclear_buildup_min=4)[0].event_type == NUCLEAR_BUILDUP


def test_shifts_within_the_window_chain_into_one_arc_and_farther_ones_do_not() -> None:
    (chained,) = built([weapons(K1, 0, 1), weapons(K2, 1, 4)])
    assert chained.event_type == NUCLEAR_ARMAMENT and chained.attribute("after") == 4.0
    assert chained.intervals == (K1, K2)
    apart = built([weapons(K1, 0, 1), weapons(K4, 1, 3)])
    assert [(arc.event_type, arc.open) for arc in apart] == [(NUCLEAR_ARMAMENT, False), (NUCLEAR_BUILDUP, True)]


def test_a_disarmament_halves_the_arsenal_and_to_zero_from_ten_is_campaign_defining() -> None:
    (halved,) = built([weapons(K1, 8, 4)])
    assert halved.event_type == NUCLEAR_DISARMAMENT and halved.significance is Significance.MAJOR
    assert describe_event(halved) == (
        "Northland (nation:20) dismantled its nuclear arsenal: 8.0 -> 4.0 nuclear weapons"
    )
    (dismantled,) = built([weapons(K1, 12, 0)])
    assert dismantled.significance is Significance.CAMPAIGN_DEFINING
    assert built([weapons(K1, 9, 0)])[0].significance is Significance.MAJOR
    assert built([weapons(K1, 8, 5)]) == []
