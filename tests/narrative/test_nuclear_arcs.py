"""The nuclear arc rule over synthetic arsenal shifts, program flags and situation reports."""

from __future__ import annotations

import pytest

from tests.narrative.support import atomic, nation, nation_row, situation
from tinarrative.config import GeopoliticsSettings, NarrativeSettings, NationMetricsSettings
from tinarrative.kinds import attributes, describe_event
from tinarrative.kinds.nations import NUCLEAR_PROGRAM_CHANGED, STATISTIC_SHIFTED
from tinarrative.model.entities import EntityRef
from tinarrative.model.events import Event, Significance
from tinarrative.model.kinds import StakeMeasure
from tinarrative.model.values import Observed, Unknown
from tinarrative.narrative import aggregate, narrative_rules
from tinarrative.narrative.nation_metrics import NUCLEAR_ARMAMENT, NUCLEAR_BUILDUP, NUCLEAR_DISARMAMENT
from tinarrative.narrative.significance import CODE_REFERENCES
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
        situation(key, nations=[nation_row(NORTH, gdp=gdp, regions=1), nation_row(SOUTH, gdp=100.0, regions=1)])
        for key in (K0, *PREVIOUS)
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


def test_a_program_ending_is_not_cited() -> None:
    ended = program(K1, after=False)
    (arc,) = built([ended, weapons(K2, 0, 3)])
    assert ended.id not in arc.constituents


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


def test_a_disarmament_halves_the_arsenal() -> None:
    (halved,) = built([weapons(K1, 8, 4)])
    assert halved.event_type == NUCLEAR_DISARMAMENT and halved.significance is Significance.MAJOR
    assert describe_event(halved) == (
        "Northland (nation:20) dismantled its nuclear arsenal: 8.0 -> 4.0 nuclear weapons"
    )
    assert built([weapons(K1, 8, 5)]) == []


# --- Nuclear share ----------------------------------------------------------------------------------------


def arsenals(north: dict[str, Observed], south: Observed = 60) -> list[SituationReport]:
    """Reports at K0..K4: NORTH holds ``north[key]`` warheads (the previous key's count when unlisted), SOUTH
    ``south``."""
    held: Observed = Unknown()
    rows = []
    for key in (K0, *PREVIOUS):
        held = north.get(key, held)
        rows.append(
            situation(
                key,
                nations=[
                    nation_row(NORTH, gdp=1.0, regions=1, nuclear_weapons=held),
                    nation_row(SOUTH, gdp=100.0, regions=1, nuclear_weapons=south),
                ],
            )
        )
    return rows


def test_dismantling_a_large_arsenal_outranks_dismantling_a_small_one() -> None:
    (large,) = built([weapons(K1, 40, 0)], arsenals({K0: 40, K1: 0}))
    (small,) = built([weapons(K1, 8, 4)], arsenals({K0: 8, K1: 4}))
    assert large.score > small.score
    assert large.significance is Significance.CAMPAIGN_DEFINING and small.significance is Significance.MAJOR


def test_a_great_buildup_outranks_a_token_one() -> None:
    (great,) = built([weapons(K1, 20, 40)], arsenals({K0: 20, K1: 40}))
    (token,) = built([weapons(K1, 2, 3)], arsenals({K0: 2, K1: 3}))
    assert great.event_type == token.event_type == NUCLEAR_BUILDUP
    assert great.score > token.score


def test_a_one_warhead_armament_stays_major_in_a_world_at_the_reference() -> None:
    world = round(1 / CODE_REFERENCES[StakeMeasure.NUCLEAR])
    (arc,) = built([weapons(K1, 0, 1)], arsenals({K0: 0, K1: 1}, south=world - 1))
    assert arc.event_type == NUCLEAR_ARMAMENT and arc.significance is Significance.MAJOR
    assert arc.significance_basis is not None and arc.significance_basis.scale >= 0


def test_the_share_is_over_the_larger_end_of_the_arc() -> None:
    # A near-empty world at the start: the first interval's earlier report holds one warhead, the last interval's
    # later report thirty, so the share is over thirty.
    (arc,) = built([weapons(K1, 1, 10), weapons(K2, 10, 30)], arsenals({K0: 1, K1: 10, K2: 30}, south=0))
    basis = arc.significance_basis
    assert basis is not None and basis.share == pytest.approx(29 / 30, rel=1e-5)


def test_a_nation_with_an_unknown_count_is_skipped_in_the_world_total() -> None:
    (arc,) = built([weapons(K1, 20, 40)], arsenals({K0: 20, K1: 40}, south=Unknown()))
    basis = arc.significance_basis
    assert basis is not None and basis.share == 0.5


def test_the_basis_names_the_nuclear_measure_and_the_acting_nation() -> None:
    (arc,) = built([weapons(K1, 8, 4)], arsenals({K0: 8, K1: 4}))
    basis = arc.significance_basis
    assert basis is not None and basis.measure is StakeMeasure.NUCLEAR and basis.entities == (NORTH,)


def test_without_any_known_count_the_arc_is_not_scaled() -> None:
    (arc,) = built([weapons(K1, 8, 4)])
    assert arc.significance_basis is None and arc.significance is Significance.MAJOR
