"""The shared top-N promotion helpers: GDP rank, optional strength rank, one level up at most."""

from __future__ import annotations

import pytest

from tests.narrative.support import nation, nation_row, situation
from tinarrative.model.events import Significance
from tinarrative.model.values import Unknown
from tinarrative.narrative.significance import in_top_n, promoted_at_rank, promoted_by_rank

BIG, SMALL = nation("BIG"), nation("SMALL")


def report(big_gdp: float, small_gdp: float, big_strength: float = 1.0, small_strength: float = 2.0):
    return situation(
        "2027-01-01",
        nations=[
            nation_row(BIG, gdp=big_gdp, strength=big_strength),
            nation_row(SMALL, gdp=small_gdp, strength=small_strength),
        ],
    )


@pytest.mark.parametrize(("rank", "expected"), [(1, True), (2, True), (3, False), (None, False), (Unknown(), False)])
def test_in_top_n_includes_the_boundary_and_excludes_unranked(rank: object, expected: bool) -> None:
    assert in_top_n(rank, 2) is expected  # type: ignore[arg-type]


def test_a_boolean_is_not_a_rank() -> None:
    assert in_top_n(True, 2) is False


def test_promoted_at_rank_lifts_one_level_and_the_top_level_stays() -> None:
    assert promoted_at_rank(Significance.MINOR, 1, 1) is Significance.MAJOR
    assert promoted_at_rank(Significance.MINOR, 2, 1) is Significance.MINOR
    assert promoted_at_rank(Significance.CAMPAIGN_DEFINING, 1, 1) is Significance.CAMPAIGN_DEFINING


def test_gdp_rank_promotes_and_strength_only_when_asked() -> None:
    # SMALL is second by GDP but first by strength.
    current = report(big_gdp=10.0, small_gdp=5.0, big_strength=1.0, small_strength=9.0)
    assert promoted_by_rank(Significance.MAJOR, current, SMALL.entity_id, 1) is Significance.MAJOR
    assert (
        promoted_by_rank(Significance.MAJOR, current, SMALL.entity_id, 1, by_strength=True)
        is Significance.CAMPAIGN_DEFINING
    )
    assert promoted_by_rank(Significance.MAJOR, current, BIG.entity_id, 1) is Significance.CAMPAIGN_DEFINING


def test_ranking_by_both_statistics_promotes_once() -> None:
    current = report(big_gdp=10.0, small_gdp=5.0, big_strength=9.0, small_strength=1.0)
    assert promoted_by_rank(Significance.MINOR, current, BIG.entity_id, 1, by_strength=True) is Significance.MAJOR
