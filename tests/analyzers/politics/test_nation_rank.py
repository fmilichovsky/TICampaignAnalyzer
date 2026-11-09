"""Nation rank changes: one event per nation and metric, the reported places, ``None`` ranks and the cited inputs."""

from tests.analyzers.support import AFTER, BEFORE, analyze, nation_ref, region_ref, snapshot, state
from tinarrative.analyzers.politics import NationRankAnalyzer
from tinarrative.analyzers.politics.nation_rank import RANK_CHANGED, RANKED_PLACES
from tinarrative.kinds import describe_event
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import SourceRole
from tinarrative.model.snapshot import EntityState

ANALYZER = NationRankAnalyzer()
NATION, REGION = EntityDomain.NATION, EntityDomain.REGION


def nation(key: str, save: str, gdp: float, regions: tuple[str, ...] | None = None) -> EntityState:
    held = (str(int(key) + 20),) if regions is None else regions
    return state(NATION, key, save, GDP=gdp, regions=tuple(region_ref(item) for item in held))


def region(key: str, save: str, owner: str) -> EntityState:
    return state(REGION, key, save, nation=nation_ref(owner))


def gdp_events(before: list[EntityState], after: list[EntityState]) -> dict[str, dict[str, object]]:
    events = analyze(ANALYZER, snapshot(BEFORE, *before), snapshot(AFTER, *after))
    return {
        event.id: dict(event.attributes)
        for event in events
        if event.event_type == RANK_CHANGED and event.attribute("metric") == "GDP"
    }


def test_an_overtaking_nation_and_the_one_it_passed_both_change_rank() -> None:
    before = [nation("20", BEFORE, 100.0), nation("21", BEFORE, 80.0), nation("22", BEFORE, 10.0)]
    after = [nation("20", AFTER, 100.0), nation("21", AFTER, 80.0), nation("22", AFTER, 90.0)]
    events = analyze(ANALYZER, snapshot(BEFORE, *before), snapshot(AFTER, *after))
    ranked = {event.id: event for event in events}
    assert sorted(ranked) == [f"{RANK_CHANGED}/nation:21/GDP", f"{RANK_CHANGED}/nation:22/GDP"]
    risen = ranked[f"{RANK_CHANGED}/nation:22/GDP"]
    assert dict(risen.attributes) == {
        "metric": "GDP",
        "before_rank": 3,
        "after_rank": 2,
        "before": 10.0,
        "after": 90.0,
    }
    assert [(source.role, str(source.change.entity_id)) for source in risen.sources] == [
        (SourceRole.PRIMARY, "nation:22")
    ]
    # Passed without a change of its own: the overtaking nation's GDP is the primary source.
    passed = ranked[f"{RANK_CHANGED}/nation:21/GDP"]
    assert [(source.role, str(source.change.entity_id)) for source in passed.sources] == [
        (SourceRole.PRIMARY, "nation:22")
    ]
    assert describe_event(risen) == "Fixture nation 22 (nation:22) GDP rank: 3 -> 2"


def test_a_nation_losing_its_regions_is_unranked() -> None:
    before = [nation("20", BEFORE, 100.0), nation("21", BEFORE, 80.0)]
    after = [nation("20", AFTER, 100.0), nation("21", AFTER, 80.0, regions=())]
    assert gdp_events(before, after) == {
        f"{RANK_CHANGED}/nation:21/GDP": {
            "metric": "GDP",
            "before_rank": 2,
            "after_rank": None,
            "before": 80.0,
            "after": None,
        }
    }


def test_places_beyond_the_reported_ones_are_not_events() -> None:
    count = RANKED_PLACES + 3
    before = [nation(str(100 + index), BEFORE, float(1000 - index)) for index in range(count)]
    after = [nation(str(100 + index), AFTER, float(1000 - index)) for index in range(count)]
    # The last two swap places, both beyond the reported ones.
    after[-1] = nation(after[-1].ref.entity_id.key, AFTER, float(1000 - count + 2) + 0.5)
    assert gdp_events(before, after) == {}
