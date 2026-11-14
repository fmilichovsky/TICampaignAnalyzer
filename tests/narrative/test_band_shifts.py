"""The band-shift rules over synthetic band crossings and situation reports."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from tests.narrative.support import (
    WORLD_POWER,
    atomic,
    declared_attributes,
    faction,
    nation,
    nation_row,
    powered,
    situation,
    unification,
    war,
    with_rest,
)
from tinarrative.analyzers.politics.bands import crossed
from tinarrative.config import GeopoliticsSettings, NarrativeSettings, NationMetricsSettings, SignificanceSettings
from tinarrative.kinds import attributes as kind_attributes
from tinarrative.kinds import describe_event
from tinarrative.kinds.control import NATION_CONTROL_CHANGED
from tinarrative.kinds.nations import BAND_CROSSED, STATISTIC_SHIFTED
from tinarrative.kinds.wars import ARC
from tinarrative.model.events import Event, EventStatus, Role, Significance, SignificanceBasis
from tinarrative.model.kinds import StakeMeasure
from tinarrative.model.values import FrozenMap, Observed
from tinarrative.narrative import Join, NarrativeBuilder, aggregate, narrative_rules
from tinarrative.narrative.nation_metrics import BAND_SHIFTS, BandShiftRule
from tinarrative.narrative.situation import SituationReport

K0 = "2032-01-01T00:00:00"
K1 = "2032-04-01T00:00:00"
K2 = "2032-07-01T00:00:00"
PREVIOUS = {K1: K0, K2: K1}
NORTH = nation("20", "Northland")
SOUTH = nation("21", "Southland")
EXILE = nation("22", "Exileland")
LANDED = 3
RESISTANCE = faction("15", "Resistance")
SCALING = SignificanceSettings()


def crossing(
    key: str,
    statistic: str,
    before: float,
    after: float,
    *,
    rest: float | None = None,
    subject: object = NORTH,
) -> Event:
    move = crossed(statistic, before, after)
    assert move is not None
    attributes: list[tuple[str, Observed]] = [
        ("statistic", statistic),
        ("before", before),
        ("after", after),
        ("from_band", move.from_band),
        ("to_band", move.to_band),
        ("bands_crossed", move.bands_crossed),
        ("margin", move.margin),
        ("interval_days", None),
    ]
    if rest is not None:
        reason = f"{statistic.capitalize()}Reason_MovementToRestValue"
        attributes.append(("causes", FrozenMap(((reason, rest),))))
    return atomic(
        f"{BAND_CROSSED.event_type}/{subject.entity_id}/{statistic}",  # type: ignore[attr-defined]
        key,
        not_before=PREVIOUS[key],
        entities=(subject,),  # type: ignore[arg-type]
        attributes=kind_attributes(BAND_CROSSED, attributes),
        significance=Significance.TRIVIAL,
    )


def reports(*values: Observed, statistic: str = "unrest") -> list[SituationReport]:
    """One report per key K0, K1, K2 with NORTH's ``statistic`` at each value; no nation has a known power share."""
    return [
        situation(
            key,
            nations=[
                nation_row(NORTH, statistics={statistic: value}, regions=LANDED),
                nation_row(SOUTH, gdp=100.0, regions=LANDED),
            ],
        )
        for key, value in zip((K0, K1, K2), values, strict=False)
    ]


def power_reports(*values: Observed, statistic: str, weight: float) -> list[SituationReport]:
    """As ``reports``, with NORTH's power share ``weight`` over 1000 and a landless EXILE ten times larger."""
    exile = nation_row(EXILE, gdp=10 * WORLD_POWER, population=10 * WORLD_POWER, strength=10 * WORLD_POWER, regions=0)
    return [
        situation(key, nations=[*with_rest([powered(NORTH, weight, statistics={statistic: value})]), exile])
        for key, value in zip((K0, K1, K2), values, strict=False)
    ]


def built(stream: Sequence[Event], situations: Sequence[SituationReport], **settings: object) -> list[Event]:
    narrative = NarrativeSettings(
        geopolitics=GeopoliticsSettings(**{k: v for k, v in settings.items() if k != "band_hold_days"}),  # type: ignore[arg-type]
        nation_metrics=NationMetricsSettings(**{k: v for k, v in settings.items() if k == "band_hold_days"}),  # type: ignore[arg-type]
    )
    events = aggregate(stream, situations, narrative_rules(narrative))
    return [event for event in events if event.event_type in {kind.event_type for kind in BAND_SHIFTS.values()}]


def test_a_held_unrest_crossing_is_a_shift_named_by_the_game_bands() -> None:
    event = crossing(K1, "unrest", 2.5, 4.75, rest=0.5)
    (shift,) = built([event], reports(2.5, 4.75, 5.0))
    assert shift.event_type == "nation.unrest_shift"
    assert shift.constituents == (event.id,) and shift.status is EventStatus.OBJECTIVE
    assert [(role, ref.entity_id) for role, ref in shift.roles] == [(Role.ACTOR, NORTH.entity_id)]
    assert (shift.attribute("from_band"), shift.attribute("to_band"), shift.attribute("bands_crossed")) == (
        "Subversion",
        "Insurgency",
        2,
    )
    assert shift.significance is Significance.MAJOR and shift.open is False
    assert describe_event(shift) == "Northland (nation:20) unrest: Subversion -> Insurgency"


def test_a_war_arc_explains_an_unrest_shift_for_its_nation_and_interval() -> None:
    class WarArcRule:
        name = ARC.event_type
        emitted_types = frozenset({ARC.event_type})
        reads: frozenset[str] = frozenset()
        explains: frozenset[str] = frozenset()
        window_days = None

        def apply(
            self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
        ) -> list[Event]:
            fighting = next(event for event in stream if event.event_type == "war.last_fighting_changed")
            return [
                build.event(
                    ARC,
                    id_parts=["war:1"],
                    constituents=[fighting],
                    roles=[(Role.ACTOR, NORTH)],
                    join=Join.ENTITY,
                    attributes=declared_attributes(ARC.event_type, ()),
                )
            ]

    event = crossing(K1, "unrest", 2.5, 4.75, rest=0.5)
    fighting = atomic("war.last_fighting_changed", K1, entities=(war("1"),))
    rule = BandShiftRule("unrest", NationMetricsSettings(), GeopoliticsSettings())

    result = aggregate([event, fighting], reports(2.5, 4.75, 5.0), [WarArcRule(), rule])

    assert [item.event_type for item in result] == [ARC.event_type]


def test_an_unrest_crossing_the_rest_value_explains_is_dropped() -> None:
    event = crossing(K1, "unrest", 2.5, 3.5, rest=0.75)
    assert built([event], reports(2.5, 3.5, 3.5)) == []
    kept = crossing(K1, "unrest", 2.5, 3.5, rest=0.25)
    (shift,) = built([kept], reports(2.5, 3.5, 3.5))
    assert shift.significance is Significance.MINOR


def test_a_crossing_that_reverts_by_the_next_report_is_dropped() -> None:
    event = crossing(K1, "democracy", 5.5, 6.5)
    assert built([event], reports(5.5, 6.5, 5.9, statistic="democracy")) == []
    (shift,) = built([event], reports(5.5, 6.5, 6.1, statistic="democracy"))
    assert shift.event_type == "nation.government_shift" and shift.significance is Significance.MAJOR


def test_a_crossing_in_the_last_interval_is_kept_and_open() -> None:
    event = crossing(K2, "inequality", 3.5, 4.5)
    (shift,) = built([event], reports(3.0, 3.5, 4.5, statistic="inequality"))
    assert shift.open is True and shift.significance is Significance.MINOR


def test_only_a_report_within_the_hold_can_refute_a_crossing() -> None:
    event = crossing(K1, "democracy", 5.5, 6.5)
    assert built([event], reports(5.5, 6.5, 5.9, statistic="democracy")) == []
    (shift,) = built([event], reports(5.5, 6.5, 5.9, statistic="democracy"), band_hold_days=60)
    assert shift.open is False


def test_cohesion_needs_two_bands_or_an_extreme_after_the_rest_value() -> None:
    one = crossing(K1, "cohesion", 4.5, 5.5, rest=0.0)
    assert built([one], reports(4.5, 5.5, 5.5, statistic="cohesion")) == []
    two = crossing(K1, "cohesion", 4.5, 6.5, rest=0.0)
    (shift,) = built([two], reports(4.5, 6.5, 6.5, statistic="cohesion"))
    assert shift.event_type == "nation.cohesion_shift" and shift.significance is Significance.MINOR
    widened = crossing(K1, "cohesion", 4.5, 5.5, rest=-1.0)
    assert built([widened], reports(4.5, 5.5, 5.5, statistic="cohesion")) == []
    explained = crossing(K1, "cohesion", 4.5, 6.5, rest=1.5)
    assert built([explained], reports(4.5, 6.5, 6.5, statistic="cohesion")) == []
    extreme = crossing(K1, "cohesion", 1.5, 0.5, rest=0.0)
    (fragmented,) = built([extreme], reports(1.5, 0.5, 0.5, statistic="cohesion"))
    assert fragmented.attribute("to_band") == "Fragmented" and fragmented.significance is Significance.MAJOR


@pytest.mark.parametrize(
    ("statistic", "before", "after"),
    [
        ("unrest", 0.5, 2.0),
        ("democracy", 1.0, 2.5),
        ("education", 4.5, 5.5),
        ("cohesion", 0.5, 1.5),
        ("inequality", 1.5, 2.5),
        ("militaryTechLevel", 3.5, 4.5),
    ],
)
def test_a_shift_scales_with_its_nations_power_share_and_a_landless_nation_dilutes_none(
    statistic: str, before: float, after: float
) -> None:
    event = crossing(K1, statistic, before, after, rest=0.0 if statistic in {"unrest", "cohesion"} else None)

    (great,) = built([event], power_reports(before, after, after, statistic=statistic, weight=400.0))
    (micro,) = built([event], power_reports(before, after, after, statistic=statistic, weight=0.1))

    assert great.significance_basis is not None and micro.significance_basis is not None
    level = Significance.of(great.significance_basis.base)
    assert great.significance_basis == SignificanceBasis(
        base=level.base, measure=StakeMeasure.POWER, share=0.4, scale=SCALING.scale_max, entities=(NORTH,)
    )
    assert great.significance.rank == level.rank + 1
    assert micro.significance_basis.scale == SCALING.scale_min and micro.significance.rank == level.rank - 1


def test_an_event_naming_the_nation_in_the_interval_explains_the_shift() -> None:
    control = atomic(
        f"faction.nation_control_changed/{NORTH.entity_id}/executive",
        K1,
        not_before=K0,
        entities=(NORTH, RESISTANCE),
        attributes=kind_attributes(
            NATION_CONTROL_CHANGED,
            scope="executive",
            before=None,
            after=RESISTANCE,
            shares_before=FrozenMap(()),
            shares_after=FrozenMap(()),
            point_count_before=0,
            point_count_after=0,
            points_moved=0,
            cause="Politics",
            recorded_on=None,
            new_executive=None,
            seat=None,
            population=None,
        ),
        status=EventStatus.INFERRED,
    )
    event = crossing(K1, "democracy", 5.5, 6.5)
    situations = reports(5.5, 6.5, 6.5, statistic="democracy")
    assert built([event], situations) != []
    assert built([control, event], situations) == []
    elsewhere = crossing(K1, "democracy", 5.5, 6.5, subject=SOUTH)
    assert [shift.event_type for shift in built([control, elsewhere], plain_reports())] == ["nation.government_shift"]


def test_a_merger_explains_the_band_shifts_of_both_nations() -> None:
    merger = unification(K1, SOUTH, NORTH, not_before=K0)
    situations = reports(5.5, 6.5, 6.5, statistic="democracy")
    assert built([merger, crossing(K1, "democracy", 5.5, 6.5)], situations) == []


def plain_reports() -> list[SituationReport]:
    return [situation(key, nations=[SOUTH]) for key in (K0, K1)]


def test_metric_shifts_of_the_nation_explain_their_bands() -> None:
    event = crossing(K1, "democracy", 5.5, 6.5)
    statistic = atomic(
        f"{STATISTIC_SHIFTED.event_type}/{NORTH.entity_id}/democracy",
        K1,
        not_before=K0,
        entities=(NORTH,),
        attributes=kind_attributes(
            STATISTIC_SHIFTED,
            statistic="democracy",
            before=5.5,
            after=6.5,
            relative_change=1 / 5.5,
            interval_days=None,
        ),
        significance=Significance.TRIVIAL,
    )
    (shift,) = built([event, statistic], reports(5.5, 6.5, 6.5, statistic="democracy"))
    (entry,) = shift.attribute("metric_shifts")  # type: ignore[misc]
    assert dict(entry.items)["from_band"] == "Anocracy" and dict(entry.items)["to_band"] == "Flawed Democracy"
