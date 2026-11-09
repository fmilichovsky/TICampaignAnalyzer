"""Nation population beyond territory: the residual, the interval-scaled threshold, detonations, causes and skips."""

import pytest

from tests.analyzers.support import AFTER, BEFORE, analyze, nation_ref, region_ref, snapshot, state
from tinarrative.analyzers.politics import NationPopulationAnalyzer
from tinarrative.analyzers.politics.nation_population import (
    POPULATION_CHANGED,
    POPULATION_DROP_FLOOR,
    population_limit,
)
from tinarrative.kinds import describe_event
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Event, SourceRole
from tinarrative.model.snapshot import EntityState
from tinarrative.model.values import FrozenMap, Observed, freeze

ANALYZER = NationPopulationAnalyzer()
NATION, REGION = EntityDomain.NATION, EntityDomain.REGION
NORTH, SOUTH = nation_ref("20"), nation_ref("21")
GDP_TRACKER = "tracker_GDPChangeReason_AllTime"


def region(key: str, save: str, owner: object, population: Observed, detonations: int = 0) -> EntityState:
    return state(REGION, key, save, nation=owner, populationInMillions=population, nuclearDetonations=detonations)  # type: ignore[arg-type]


def nation(key: str, save: str, regions: tuple[str, ...], **fields: Observed) -> EntityState:
    return state(NATION, key, save, regions=tuple(region_ref(item) for item in regions), **fields)


def north_events(*events: Event) -> list[Event]:
    return [event for event in events if event.entities[0].entity_id == NORTH.entity_id]


def test_the_residual_takes_out_the_regions_gained_and_lost() -> None:
    before = snapshot(
        BEFORE,
        nation("20", BEFORE, ("40", "41"), **{GDP_TRACKER: freeze({"GDPReason_PopulationChange": -1.0})}),
        nation("21", BEFORE, ("42",)),
        region("40", BEFORE, NORTH, 80.0),
        region("41", BEFORE, NORTH, 20.0),
        region("42", BEFORE, SOUTH, 50.0),
    )
    after = snapshot(
        AFTER,
        nation(
            "20",
            AFTER,
            ("40", "42"),
            **{GDP_TRACKER: freeze({"GDPReason_PopulationChange": -4.0, "GDPReason_Other": 1.0})},
        ),
        nation("21", AFTER, ("41",)),
        region("40", AFTER, NORTH, 60.0, detonations=2),
        region("41", AFTER, SOUTH, 20.0),
        region("42", AFTER, NORTH, 50.0),
    )
    (event,) = north_events(*analyze(ANALYZER, before, after))
    assert event.event_type == POPULATION_CHANGED and event.id == "nation.population_changed/nation:20"
    attributes = dict(event.attributes)
    assert attributes["before"] == 100.0 and attributes["after"] == 110.0
    assert attributes["residual"] == 80.0 and attributes["relative_change"] == pytest.approx(-0.2)
    assert attributes["direction"] == "drop"
    assert [ref.entity_id for ref in attributes["nuked_regions"]] == [region_ref("40").entity_id]  # type: ignore[union-attr]
    assert attributes["causes"] == FrozenMap((("GDPReason_PopulationChange", -3.0),))
    assert SourceRole.PRIMARY in {source.role for source in event.sources}
    assert describe_event(event) == "Fixture nation 20 (nation:20) population drop: 100.0 -> 110.0 (residual 80.0)"


def test_the_threshold_scales_with_the_interval() -> None:
    assert population_limit(None) == POPULATION_DROP_FLOOR
    assert population_limit(30) == POPULATION_DROP_FLOOR
    assert population_limit(730.5) == pytest.approx(0.2)


def test_routine_change_is_not_reported_and_growth_is() -> None:
    def pair(after_population: float) -> list[Event]:
        before = snapshot(BEFORE, nation("20", BEFORE, ("40",)), region("40", BEFORE, NORTH, 100.0))
        after = snapshot(AFTER, nation("20", AFTER, ("40",)), region("40", AFTER, NORTH, after_population))
        return analyze(ANALYZER, before, after)

    assert pair(97.0) == []
    (event,) = pair(110.0)
    assert event.attribute("direction") == "growth" and event.attribute("nuked_regions") == ()
    assert event.attribute("causes") == FrozenMap()


def test_placeholders_and_unknown_populations_are_skipped() -> None:
    before = snapshot(BEFORE, nation("20", BEFORE, ()), region("40", BEFORE, NORTH, 100.0))
    after = snapshot(AFTER, nation("20", AFTER, ()), region("40", AFTER, NORTH, 50.0))
    assert analyze(ANALYZER, before, after) == []
    before = snapshot(BEFORE, nation("20", BEFORE, ("40",)), region("40", BEFORE, NORTH, 100.0))
    after = snapshot(AFTER, nation("20", AFTER, ("40",)), region("40", AFTER, NORTH, "many"))
    assert analyze(ANALYZER, before, after) == []
