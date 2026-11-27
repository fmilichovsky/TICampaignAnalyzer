"""The scaling registry and the score arithmetic of a scaling."""

from __future__ import annotations

import math

import pytest

from tinarrative.kinds import KINDS
from tinarrative.model.events import SCORE_BANDS, SCORE_MAX, SCORE_MIN, Significance
from tinarrative.model.kinds import Measure, Scaling
from tinarrative.narrative.scalings import (
    DEFAULT_WIDTH,
    SCALINGS,
    UNEXAMINED,
    ScalingSpec,
    cut_off,
    drop_share,
    floor,
    midpoint,
    own_score,
    scale,
)
from tinarrative.narrative.significance import SHARE_IMPLEMENTATIONS

MINOR = Significance.MINOR.base
MAJOR_LOW = SCORE_BANDS[Significance.MAJOR][0]


def level(base: int, share: float, rise: float, drop: float | None = None) -> Significance:
    return Significance.of(own_score(base, (scale(share, rise, drop),)))


def test_every_scaling_has_exactly_one_registry_entry() -> None:
    assert list(SCALINGS) == list(Scaling)


def test_every_measure_has_a_starting_scaling_of_its_name() -> None:
    assert all(SCALINGS[Scaling(measure.value)].measure is measure for measure in Measure)


def test_a_kind_scaling_names_the_measure_its_share_reads() -> None:
    for kind in KINDS.values():
        assert (kind.share is None) == (kind.scaling is None), kind.event_type
        if kind.share is not None and kind.scaling is not None:
            assert SCALINGS[kind.scaling].measure is SHARE_IMPLEMENTATIONS[kind.share].measure, kind.event_type


def test_the_midpoint_leaves_the_base_and_the_rise_and_drop_shares_are_the_band_edges() -> None:
    rise = 0.1
    assert drop_share(rise, None) == pytest.approx(rise / DEFAULT_WIDTH)
    assert scale(midpoint(rise, None), rise) == 0
    assert level(MINOR, rise * 1.01, rise) is Significance.MAJOR
    assert level(MINOR, rise * 0.99, rise) is Significance.MINOR
    # The default width moves ten points per tenfold share, as the reference did.
    assert scale(midpoint(rise, None) * 10, rise) == 10


@pytest.mark.parametrize("drop", [None, 0.01])
def test_a_share_exactly_on_a_cut_off_moves_past_it_at_every_step(drop: float | None) -> None:
    rise, top = 0.1, Significance.CAMPAIGN_DEFINING.base

    assert level(MINOR, cut_off(1, rise, drop), rise, drop) is Significance.MAJOR
    assert level(MINOR, cut_off(2, rise, drop), rise, drop) is Significance.CAMPAIGN_DEFINING
    assert level(top, cut_off(-1, rise, drop), rise, drop) is Significance.MAJOR
    assert level(top, cut_off(-2, rise, drop), rise, drop) is Significance.MINOR


def test_a_rise_past_two_levels_is_as_wide_as_the_first() -> None:
    rise = 0.1
    second = cut_off(2, rise)
    assert second == pytest.approx(rise * DEFAULT_WIDTH)
    assert level(MINOR, second * 0.99, rise) is Significance.MAJOR
    assert level(MINOR, second * 1.01, rise) is Significance.CAMPAIGN_DEFINING
    trivial = Significance.TRIVIAL.base
    assert level(trivial, rise * 1.01, rise) is Significance.MINOR
    assert level(trivial, second * 1.01, rise) is Significance.MAJOR


def test_the_score_is_clipped_at_100_and_never_bounded_by_a_clamp() -> None:
    assert own_score(MINOR, (scale(1e9, 0.1),)) == SCORE_MAX
    assert scale(0.1 * DEFAULT_WIDTH**2, 0.1) > 15


def test_a_custom_drop_share_sets_the_width_and_the_rate() -> None:
    rise, drop = 0.1, 0.01
    assert scale(math.sqrt(rise * drop), rise, drop) == 0
    # 25 points per tenfold share: one level per decade.
    assert scale(math.sqrt(rise * drop) * 10, rise, drop) == 25
    assert level(Significance.MAJOR.base, drop * 0.99, rise, drop) is Significance.MINOR
    assert level(Significance.MAJOR.base, drop * 1.01, rise, drop) is Significance.MAJOR
    assert cut_off(2, rise, drop) == pytest.approx(1.0)
    assert cut_off(-2, rise, drop) == pytest.approx(0.001)


def test_size_never_drops_an_event_below_minor() -> None:
    assert floor(Significance.CAMPAIGN_DEFINING.base) == SCORE_BANDS[Significance.MINOR][0]
    assert level(MINOR, 1e-12, 0.1) is Significance.MINOR
    assert level(Significance.CAMPAIGN_DEFINING.base, 1e-12, 0.1) is Significance.MINOR
    assert own_score(MINOR, (scale(0.0, 0.1),)) == SCORE_BANDS[Significance.MINOR][0]


def test_a_trivial_base_scales_from_trivial_and_cannot_drop_below_it() -> None:
    trivial = Significance.TRIVIAL.base
    assert floor(trivial) == SCORE_MIN
    assert own_score(trivial, (scale(1e-12, 0.1),)) == SCORE_MIN


def test_a_scaling_checks_its_shares() -> None:
    with pytest.raises(ValueError, match="rise share"):
        ScalingSpec(Measure.POWER, rise=0.0, reason=UNEXAMINED)
    with pytest.raises(ValueError, match="drop share"):
        ScalingSpec(Measure.POWER, rise=0.1, reason=UNEXAMINED, drop=0.2)
    with pytest.raises(ValueError, match="one level"):
        cut_off(0, 0.1)
