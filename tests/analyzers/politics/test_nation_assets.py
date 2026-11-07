"""Nation assets: army kinds, region sums, the published strength estimate and the rankings."""

import pytest

from tests.analyzers.support import AFTER, army_ref, faction_ref, nation_ref, region_ref, snapshot, state
from tinarrative.analyzers.common import Lookup, Side
from tinarrative.analyzers.politics.nation_assets import assets, ranking, standings, strength
from tinarrative.model.entities import EntityDomain
from tinarrative.model.snapshot import EntityState, SaveSnapshot
from tinarrative.model.values import FrozenMap, Observed, Unknown, UnknownReason

NATION, REGION, ARMY = EntityDomain.NATION, EntityDomain.REGION, EntityDomain.ARMY


def region(key: str, owner: str, boost: Observed = 10.0, **fields: Observed) -> EntityState:
    values: dict[str, Observed] = {
        "nation": nation_ref(owner),
        "boostPerYear_dekatons": boost,
        "missionControl": 2,
        "antiSpaceDefenses": False,
        "numSTOFighters": 0,
        "leadOccupier": None,
        "occupations": FrozenMap(),
    }
    values.update(fields)
    return state(REGION, key, AFTER, **values)


def army(key: str, deployment: str, strength_value: Observed = 1.0) -> EntityState:
    return state(ARMY, key, AFTER, deploymentType=deployment, strength=strength_value, faction=faction_ref("15"))


def nation(key: str, regions: tuple[str, ...], armies: tuple[str, ...] = (), **fields: Observed) -> EntityState:
    values: dict[str, Observed] = {"militaryTechLevel": 2.0, "unrest": 1.0, "numNuclearWeapons": 0, "GDP": 100.0}
    values.update(fields)
    return state(
        NATION,
        key,
        AFTER,
        regions=tuple(region_ref(item) for item in regions),
        armies=tuple(army_ref(item) for item in armies),
        **values,
    )


def held(save: SaveSnapshot, key: str) -> tuple[EntityState, Lookup]:
    lookup = Lookup(save, save)
    found = lookup.state(nation_ref(key).entity_id, Side.AFTER)
    assert found is not None
    return found, lookup


def test_assets_count_army_kinds_and_sum_the_regions() -> None:
    save = snapshot(
        AFTER,
        nation("20", ("40", "41"), ("110", "111", "112")),
        region("40", "20", antiSpaceDefenses=True),
        region("41", "20", 5.5, numSTOFighters=3, leadOccupier=nation_ref("21")),
        army("110", "Standard", 1.0),
        army("111", "Standard", 0.5),
        army("112", "Naval"),
    )
    found, lookup = held(save, "20")
    result = assets(lookup, found, Side.AFTER)
    assert (result.armies, result.navies, result.mean_army_strength) == (2, 1, 0.75)
    assert (result.boost, result.mission_control, result.sto_fighters) == (15.5, 4.0, 3.0)
    assert (result.space_defence_regions, result.defended_regions, result.unoccupied_regions) == (1, 2, 1)
    # 1 unoccupied region x 2 x 0.7 + 2 armies x 2 x 3 x 0.75 + 1 navy - 1 unrest
    assert strength(found, result) == pytest.approx(1.4 + 9.0 + 1.0 - 1.0)


def test_a_partly_occupied_region_counts_its_unoccupied_share() -> None:
    save = snapshot(
        AFTER,
        nation("20", ("40", "41", "42"), unrest=0.0),
        region("40", "20", occupations=FrozenMap((("nation:21", 0.25),))),
        region("41", "20", occupations=FrozenMap((("nation:21", 0.5), ("nation:22", 0.75)))),
        region("42", "20"),
    )
    found, lookup = held(save, "20")
    result = assets(lookup, found, Side.AFTER)
    # 0.75 + 0 (over-occupied, clamped) + 1
    assert result.unoccupied_regions == pytest.approx(1.75)
    assert strength(found, result) == pytest.approx(1.75 * 2 * 0.7)


def test_an_unreadable_occupation_makes_the_estimate_unknown() -> None:
    save = snapshot(
        AFTER,
        nation("20", ("40",)),
        region("40", "20", occupations=(FrozenMap((("Key", 1),)),)),
    )
    found, lookup = held(save, "20")
    result = assets(lookup, found, Side.AFTER)
    assert result.unoccupied_regions == Unknown(UnknownReason.UNPARSEABLE)
    assert strength(found, result) == Unknown(UnknownReason.UNPARSEABLE)


def test_any_nuclear_weapon_adds_a_hundred_and_five_per_weapon() -> None:
    save = snapshot(AFTER, nation("20", ("40",), numNuclearWeapons=2, unrest=0.0), region("40", "20"))
    found, lookup = held(save, "20")
    assert strength(found, assets(lookup, found, Side.AFTER)) == pytest.approx(1.4 + 100.0 + 10.0)


def test_an_absent_region_field_stays_missing_and_makes_the_estimate_unknown() -> None:
    bare = state(REGION, "40", AFTER, nation=nation_ref("20"))
    save = snapshot(AFTER, nation("20", ("40",)), bare)
    found, lookup = held(save, "20")
    result = assets(lookup, found, Side.AFTER)
    assert result.boost == Unknown(UnknownReason.MISSING)
    assert result.space_defence_regions == Unknown(UnknownReason.MISSING)
    assert isinstance(strength(found, result), Unknown)


def test_an_army_without_a_known_deployment_leaves_the_counts_unknown() -> None:
    save = snapshot(AFTER, nation("20", ("40",), ("110",)), region("40", "20"), army("110", "Orbital"))
    found, lookup = held(save, "20")
    result = assets(lookup, found, Side.AFTER)
    assert isinstance(result.armies, Unknown) and isinstance(result.navies, Unknown)


def test_standings_rank_nations_with_regions_and_break_ties_by_id() -> None:
    save = snapshot(
        AFTER,
        nation("20", ("40",), GDP=50.0),
        nation("21", ("41",), GDP=50.0),
        nation("22", ("42",), GDP=80.0),
        nation("23", (), GDP=500.0),
        region("40", "20", 1.0),
        region("41", "21", 30.0),
        region("42", "22", 2.0),
    )
    places = standings(save, Lookup(save, save), Side.AFTER)
    assert {str(key): (item.rank, item.value) for key, item in places["GDP"].items()} == {
        "nation:22": (1, 80.0),
        "nation:20": (2, 50.0),
        "nation:21": (3, 50.0),
    }
    assert [str(key) for key, _ in sorted(places["boost"].items(), key=lambda item: item[1].rank)] == [
        "nation:21",
        "nation:22",
        "nation:20",
    ]
    assert ranking({}) == {}
