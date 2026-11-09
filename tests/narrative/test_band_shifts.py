"""The band-shift rules over synthetic band crossings and situation reports."""

from __future__ import annotations

from collections.abc import Sequence

from tests.narrative.support import (
    UNKNOWN,
    atomic,
    control_attributes,
    faction,
    nation,
    nation_row,
    situation,
    unification,
    war,
)
from tinarrative.analyzers.politics.bands import crossed
from tinarrative.config import GeopoliticsSettings, NarrativeSettings, NationMetricsSettings
from tinarrative.kinds import attributes, describe_event
from tinarrative.kinds.control import NATION_CONTROL_CHANGED
from tinarrative.kinds.wars import WAR_LAST_FIGHTING_CHANGED
from tinarrative.model.events import Event, EventStatus, Role, Significance
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
RESISTANCE = faction("15", "Resistance")


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
    ]
    if rest is not None:
        reason = f"{statistic.capitalize()}Reason_MovementToRestValue"
        attributes.append(("causes", FrozenMap(((reason, rest),))))
    return atomic(
        f"nation.band_crossed/{subject.entity_id}/{statistic}",  # type: ignore[attr-defined]
        key,
        not_before=PREVIOUS[key],
        entities=(subject,),  # type: ignore[arg-type]
        attributes=attributes,
        significance=Significance.TRIVIAL,
    )


def reports(*values: Observed, statistic: str = "unrest", gdp: Observed = UNKNOWN) -> list[SituationReport]:
    """One report per key K0, K1, K2 with NORTH's ``statistic`` at each value; NORTH unranked unless ``gdp`` is given
    (SOUTH has 100)."""
    return [
        situation(
            key, nations=[nation_row(NORTH, gdp=gdp, statistics={statistic: value}), nation_row(SOUTH, gdp=100.0)]
        )
        for key, value in zip((K0, K1, K2), values, strict=False)
    ]


def built(stream: Sequence[Event], situations: Sequence[SituationReport], **settings: object) -> list[Event]:
    narrative = NarrativeSettings(
        geopolitics=GeopoliticsSettings(**{k: v for k, v in settings.items() if k != "band_hold_days"}),  # type: ignore[arg-type]
        nation_metrics=NationMetricsSettings(**{k: v for k, v in settings.items() if k == "band_hold_days"}),  # type: ignore[arg-type]
    )
    events = aggregate(stream, situations, narrative_rules(narrative))
    return [event for event in events if event.event_type in BAND_SHIFTS.values()]


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
        name = "war.arc"
        emitted_types = frozenset({"war.arc"})
        reads: frozenset[str] = frozenset()
        explains: frozenset[str] = frozenset()
        window_days = None

        def apply(
            self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
        ) -> list[Event]:
            fighting = next(event for event in stream if event.event_type == WAR_LAST_FIGHTING_CHANGED.event_type)
            return [
                build.event(
                    self.name,
                    id_parts=["war:1"],
                    constituents=[fighting],
                    roles=[(Role.ACTOR, NORTH)],
                    join=Join.ENTITY,
                )
            ]

    event = crossing(K1, "unrest", 2.5, 4.75, rest=0.5)
    fighting = atomic(
        WAR_LAST_FIGHTING_CHANGED.event_type,
        K1,
        entities=(war("1"),),
        attributes=attributes(WAR_LAST_FIGHTING_CHANGED, transition="changed", before=None, after=None),
    )
    rule = BandShiftRule("unrest", NationMetricsSettings(), GeopoliticsSettings())

    result = aggregate([event, fighting], reports(2.5, 4.75, 5.0), [WarArcRule(), rule])

    assert [item.event_type for item in result] == ["war.arc"]


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


def test_a_top_gdp_nation_is_promoted_one_level() -> None:
    event = crossing(K1, "unrest", 2.5, 3.5, rest=0.0)
    (shift,) = built([event], reports(2.5, 3.5, 3.5, gdp=1000.0))
    assert (shift.attribute("gdp_rank"), shift.significance) == (1, Significance.MAJOR)
    (strict,) = built([event], reports(2.5, 3.5, 3.5, gdp=50.0), top_gdp_nations=1)
    assert (strict.attribute("gdp_rank"), strict.significance) == (2, Significance.MINOR)
    miltech = crossing(K1, "militaryTechLevel", 3.5, 4.5)
    (age,) = built([miltech], reports(3.5, 4.5, 4.5, statistic="militaryTechLevel", gdp=1000.0))
    assert age.event_type == "nation.miltech_shift" and age.significance is Significance.CAMPAIGN_DEFINING


def test_an_event_naming_the_nation_in_the_interval_explains_the_shift() -> None:
    control = atomic(
        f"{NATION_CONTROL_CHANGED.event_type}/{NORTH.entity_id}/executive",
        K1,
        not_before=K0,
        entities=(NORTH, RESISTANCE),
        attributes=control_attributes("executive", None, RESISTANCE),
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
        f"nation.statistic_shifted/{NORTH.entity_id}/democracy",
        K1,
        not_before=K0,
        entities=(NORTH,),
        attributes=(("statistic", "democracy"), ("before", 5.5), ("after", 6.5), ("relative_change", 1 / 5.5)),
        significance=Significance.TRIVIAL,
    )
    (shift,) = built([event, statistic], reports(5.5, 6.5, 6.5, statistic="democracy"))
    (entry,) = shift.attribute("metric_shifts")  # type: ignore[misc]
    assert dict(entry.items)["from_band"] == "Anocracy" and dict(entry.items)["to_band"] == "Flawed Democracy"
