"""Nation space-support assets: the relative threshold and floors, a rise from zero, the territory share, skips."""

import pytest

from tests.analyzers.support import AFTER, BEFORE, analyze, nation_ref, region_ref, snapshot, state
from tinarrative.analyzers.politics import NationSpaceAssetsAnalyzer
from tinarrative.analyzers.politics.nation_space import SPACE_ASSETS_CHANGED, is_space_change
from tinarrative.analyzers.render import describe_event
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import SourceRole
from tinarrative.model.snapshot import EntityState
from tinarrative.model.values import Observed

ANALYZER = NationSpaceAssetsAnalyzer()
NATION, REGION = EntityDomain.NATION, EntityDomain.REGION


def region(key: str, save: str, owner: str, boost: float = 10.0, control: int = 2, **fields: Observed) -> EntityState:
    values: dict[str, Observed] = {
        "nation": nation_ref(owner),
        "boostPerYear_dekatons": boost,
        "missionControl": control,
        "antiSpaceDefenses": False,
        "numSTOFighters": 0,
    }
    values.update(fields)
    return state(REGION, key, save, **values)


def nation(key: str, save: str, regions: tuple[str, ...]) -> EntityState:
    return state(NATION, key, save, regions=tuple(region_ref(item) for item in regions))


@pytest.mark.parametrize(
    ("statistic", "before", "after", "counts"),
    [
        ("boost", 20.0, 24.0, False),  # below the floor of 5
        ("boost", 100.0, 120.0, False),  # 20 %, below the relative threshold
        ("boost", 100.0, 125.0, True),
        ("boost", 0.0, 5.0, True),
        ("missionControl", 4.0, 5.0, False),
        ("missionControl", 4.0, 6.0, True),
        ("spaceDefences", 0.0, 1.0, True),
        ("spaceDefences", 8.0, 9.0, False),
    ],
)
def test_a_change_needs_the_relative_threshold_and_the_floor(
    statistic: str, before: float, after: float, counts: bool
) -> None:
    assert is_space_change(statistic, before, after) is counts


def test_held_regions_growing_boost_is_growth_with_no_territory_share() -> None:
    before = snapshot(
        BEFORE, nation("20", BEFORE, ("40", "41")), region("40", BEFORE, "20"), region("41", BEFORE, "20")
    )
    after = snapshot(
        AFTER, nation("20", AFTER, ("40", "41")), region("40", AFTER, "20", 20.0), region("41", AFTER, "20")
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.id == f"{SPACE_ASSETS_CHANGED}/nation:20/boost"
    attributes = dict(event.attributes)
    assert attributes["statistic"] == "boost" and attributes["direction"] == "growth"
    assert (attributes["before"], attributes["after"], attributes["relative_change"]) == (20.0, 30.0, 0.5)
    assert (attributes["territory_delta"], attributes["territory_share"]) == (0.0, 0.0)
    assert [(source.role, str(source.change.entity_id)) for source in event.sources] == [
        (SourceRole.PRIMARY, "region:40")
    ]
    assert describe_event(event) == "Fixture nation 20 (nation:20) boost growth: 20.0 -> 30.0"


def test_a_region_lost_carries_the_drop() -> None:
    before = snapshot(
        BEFORE,
        nation("20", BEFORE, ("40", "41")),
        nation("21", BEFORE, ("42",)),
        region("40", BEFORE, "20", 10.0, 1),
        region("41", BEFORE, "20", 30.0, 1),
        region("42", BEFORE, "21", 1.0, 1),
    )
    after = snapshot(
        AFTER,
        nation("20", AFTER, ("40",)),
        nation("21", AFTER, ("41", "42")),
        region("40", AFTER, "20", 10.0, 1),
        region("41", AFTER, "21", 30.0, 1),
        region("42", AFTER, "21", 1.0, 1),
    )
    events = {event.id: event for event in analyze(ANALYZER, before, after)}
    drop = dict(events[f"{SPACE_ASSETS_CHANGED}/nation:20/boost"].attributes)
    assert (drop["direction"], drop["before"], drop["after"]) == ("decline", 40.0, 10.0)
    assert (drop["territory_delta"], drop["territory_share"]) == (-30.0, 1.0)
    assert [str(ref.entity_id) for ref in drop["regions_lost"]] == ["region:41"]  # type: ignore[union-attr]
    gain = dict(events[f"{SPACE_ASSETS_CHANGED}/nation:21/boost"].attributes)
    assert (gain["before"], gain["after"], gain["territory_share"]) == (1.0, 31.0, 1.0)
    cited = events[f"{SPACE_ASSETS_CHANGED}/nation:20/boost"].sources
    assert [(source.role, source.change.field) for source in cited] == [(SourceRole.CORROBORATING, "nation")]


def test_first_space_defences_rise_from_zero() -> None:
    before = snapshot(
        BEFORE, nation("20", BEFORE, ("40", "41")), region("40", BEFORE, "20"), region("41", BEFORE, "20")
    )
    after = snapshot(
        AFTER,
        nation("20", AFTER, ("40", "41")),
        region("40", AFTER, "20", antiSpaceDefenses=True),
        region("41", AFTER, "20", numSTOFighters=2),
    )
    (event,) = analyze(ANALYZER, before, after)
    attributes = dict(event.attributes)
    assert (attributes["statistic"], attributes["before"], attributes["after"]) == ("spaceDefences", 0, 2)
    assert attributes["relative_change"] is None
    assert sorted(source.change.field or "" for source in event.sources) == ["antiSpaceDefenses", "numSTOFighters"]


def test_placeholders_and_unknown_values_are_skipped() -> None:
    before = snapshot(BEFORE, nation("20", BEFORE, ()), region("40", BEFORE, "21", boost="n/a"))  # type: ignore[arg-type]
    after = snapshot(AFTER, nation("20", AFTER, ()), region("40", AFTER, "21", boost=50.0))
    assert analyze(ANALYZER, before, after) == []
