"""Prominence shares: nation power, region population and organization tier, from a snapshot or a situation report."""

from __future__ import annotations

import math

import pytest

from tests.analyzers.support import AFTER, nation_ref, region_ref, snapshot, state
from tinarrative.config import PowerSettings
from tinarrative.model.entities import EntityDomain, EntityId
from tinarrative.model.snapshot import EntityState, SaveSnapshot
from tinarrative.model.values import FrozenMap, Observed, Unknown
from tinarrative.narrative.prominence import (
    nation_power,
    organization_shares,
    region_shares,
    total,
)
from tinarrative.narrative.situation import build_situation

NATION, REGION, ORG = EntityDomain.NATION, EntityDomain.REGION, EntityDomain.ORGANIZATION
THIRDS = PowerSettings()


def region(key: str, owner: str, population: Observed = 10.0) -> EntityState:
    return state(
        REGION,
        key,
        AFTER,
        nation=nation_ref(owner),
        populationInMillions=population,
        boostPerYear_dekatons=0.0,
        missionControl=0,
        antiSpaceDefenses=False,
        numSTOFighters=0,
        leadOccupier=None,
        occupations=FrozenMap(),
    )


def nation(key: str, regions: tuple[str, ...], **values: Observed) -> EntityState:
    fields: dict[str, Observed] = {"militaryTechLevel": 2.0, "unrest": 0.0, "numNuclearWeapons": 0, "GDP": 100.0}
    fields.update(values)
    return state(NATION, key, AFTER, regions=tuple(region_ref(item) for item in regions), armies=(), **fields)


def org(key: str, tier: Observed) -> EntityState:
    return state(ORG, key, AFTER, tier=tier)


def world() -> SaveSnapshot:
    """A large conventional power, a small nuclear-armed state and a third nation."""
    return snapshot(
        AFTER,
        nation("20", tuple(str(40 + index) for index in range(9)), GDP=900.0),
        *(region(str(40 + index), "20", 100.0) for index in range(9)),
        nation("21", ("50",), numNuclearWeapons=1),
        region("50", "21", 100.0),
        nation("22", ("51", "52"), GDP=300.0, unrest=1.0),
        region("51", "22", 50.0),
        region("52", "22", 50.0),
    )


def nid(key: str) -> EntityId:
    return nation_ref(key).entity_id


def test_power_shares_sum_to_one_over_the_world() -> None:
    shares = nation_power(world(), THIRDS)

    assert set(shares) == {nid("20"), nid("21"), nid("22")}
    assert math.fsum(shares.values()) == pytest.approx(1.0)


def test_power_is_the_weighted_mean_of_the_gdp_population_and_strength_shares() -> None:
    gdp_only = nation_power(world(), PowerSettings(w_gdp=1.0, w_pop=0.0, w_str=0.0))

    assert gdp_only[nid("20")] == pytest.approx(900 / 1300)
    pop_only = nation_power(world(), PowerSettings(w_gdp=0.0, w_pop=1.0, w_str=0.0))
    assert pop_only[nid("22")] == pytest.approx(100 / 1100)


def test_a_snapshot_and_its_situation_report_give_the_same_shares() -> None:
    save = world()

    from_report = build_situation(save).power_shares(THIRDS)

    assert from_report == pytest.approx(nation_power(save, THIRDS))


def test_a_nuclear_armed_small_state_gains_on_strength_but_stays_below_a_large_conventional_power() -> None:
    gdp = nation_power(world(), PowerSettings(w_gdp=1.0, w_pop=0.0, w_str=0.0))
    strength = nation_power(world(), PowerSettings(w_gdp=0.0, w_pop=0.0, w_str=1.0))
    power = nation_power(world(), THIRDS)

    # 1 region x 2 x 0.7 + 100 + 5 against 9 regions x 2 x 0.7: any arsenal outweighs a large conventional army
    assert strength[nid("21")] > strength[nid("20")]
    assert power[nid("21")] > 2 * gdp[nid("21")]
    assert power[nid("20")] > power[nid("21")]


def test_a_nation_with_an_unknown_input_or_no_region_has_no_share() -> None:
    save = snapshot(
        AFTER,
        nation("20", ("40",)),
        region("40", "20"),
        nation("21", ("41",), GDP=Unknown()),
        region("41", "21"),
        nation("22", ()),
    )

    assert nation_power(save, THIRDS) == pytest.approx({nid("20"): 1.0})


def test_negative_strength_counts_as_none() -> None:
    save = snapshot(
        AFTER,
        nation("20", ("40",)),
        region("40", "20"),
        nation("21", ("41",), unrest=10.0),
        region("41", "21"),
    )

    strength = nation_power(save, PowerSettings(w_gdp=0.0, w_pop=0.0, w_str=1.0))

    assert strength == pytest.approx({nid("20"): 1.0, nid("21"): 0.0})


def test_a_region_shares_world_population() -> None:
    shares = region_shares(world())

    assert shares[region_ref("50").entity_id] == pytest.approx(100 / 1100)
    assert math.fsum(shares.values()) == pytest.approx(1.0)


def test_tier_squared_makes_one_tier_three_outweigh_three_tier_one() -> None:
    save = snapshot(AFTER, org("70", 3), org("71", 1), org("72", 1), org("73", 1), org("74", Unknown()))
    ids = [state.ref.entity_id for state in save.organizations]

    shares = organization_shares(save, exponent=2)

    assert shares[ids[0]] == pytest.approx(9 / 12)
    assert shares[ids[0]] > total(shares, ids[1:4])
    assert ids[4] not in shares


def test_a_set_sums_the_shares_of_its_distinct_members() -> None:
    shares = nation_power(world(), THIRDS)

    side = total(shares, (nid("20"), nid("22"), nid("20"), nid("99")))

    assert side == pytest.approx(shares[nid("20")] + shares[nid("22")])
