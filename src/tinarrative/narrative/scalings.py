"""The scaling registry, how a share moves an event kind's level, and the score arithmetic of a scaling (ADR-0011).

No scaling is a setting.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

from ..model.events import SCORE_BANDS, SCORE_MAX, SCORE_MIN, Significance
from ..model.kinds import UNEXAMINED, Measure, Scaling

__all__ = [
    "DEFAULT_WIDTH",
    "LEVEL_POINTS",
    "SCALINGS",
    "STARTING_RISE",
    "UNEXAMINED",
    "ScalingSpec",
    "check_shares",
    "cut_off",
    "decided_outright",
    "drop_share",
    "floor",
    "midpoint",
    "own_score",
    "scale",
]

DEFAULT_WIDTH: Final = 10**2.5
"""The rise share over the drop share of a scaling that declares no drop share: ×316."""
STARTING_RISE: Final = 10**1.25
"""A starting scaling's rise share over its midpoint: the midpoint is the share that leaves a score at its base."""
LEVEL_POINTS: Final = SCORE_BANDS[Significance.MINOR][1] - SCORE_BANDS[Significance.MINOR][0] + 1
"""The points of one level: the score moves this many across the band between a drop and a rise share."""


@dataclass(frozen=True)
class ScalingSpec:
    """One scaling: the shares, relative to the level an event starts from, at which it rises and drops one level."""

    measure: Measure
    """The measure the share is read on; a kind's scaling names the measure its share reads."""
    rise: float
    """The share at which an event rises one level above the level it starts from."""
    reason: str
    """Why the rise share sits there, as a game quantity; ``UNEXAMINED`` until a review states one."""
    drop: float | None = None
    """The share at which an event drops one level; ``None`` keeps the default width (``DEFAULT_WIDTH``)."""

    def __post_init__(self) -> None:
        check_shares(self.rise, self.drop)
        if not self.reason:
            raise ValueError("a scaling states a reason, or UNEXAMINED")


def check_shares(rise: float, drop: float | None) -> None:
    """``ValueError`` unless ``rise`` is a positive finite share and ``drop``, when given, a positive share below it."""
    if not math.isfinite(rise) or rise <= 0:
        raise ValueError(f"a rise share is a positive number, not {rise!r}")
    if drop is not None and (not math.isfinite(drop) or not 0 < drop < rise):
        raise ValueError(f"a drop share is a positive number below the rise share {rise!r}, not {drop!r}")


def drop_share(rise: float, drop: float | None) -> float:
    """``drop``, else the drop share of the default width."""
    return rise / DEFAULT_WIDTH if drop is None else drop


def midpoint(rise: float, drop: float | None) -> float:
    """√(drop × rise): the share that leaves a score at its starting level's base; a readout's derived midpoint."""
    return math.sqrt(rise * drop_share(rise, drop))


def scale(share: float, rise: float, drop: float | None = None) -> int:
    """The points ``share`` moves a score from its starting level's base: ``LEVEL_POINTS`` ÷ log10(rise ÷ drop) per
    tenfold share, zero at the midpoint, a half rounded away from it, so a share on a cut-off moves past it. No share
    moves it ``-SCORE_MAX``: down to the floor."""
    if share <= 0:
        return -SCORE_MAX
    low = drop_share(rise, drop)
    centre = (math.log10(rise) + math.log10(low)) / 2
    # Rounded to 9 places first, so a share computed as a cut-off is not a hair short of it.
    points = round(LEVEL_POINTS * (math.log10(share) - centre) / (math.log10(rise) - math.log10(low)), 9)
    return int(math.copysign(math.floor(abs(points) + 0.5), points))


def cut_off(step: int, rise: float, drop: float | None = None) -> float:
    """The share at which an event moves ``step`` levels from its starting level: the rise share for 1, the drop
    share for -1, each further level as wide as the starting one."""
    if step == 0:
        raise ValueError("a cut-off is at least one level away")
    low = drop_share(rise, drop)
    width = rise / low
    return rise * width ** (step - 1) if step > 0 else low / width ** (-step - 1)


def floor(base: int) -> int:
    """The lowest score a share can move ``base`` to: the bottom of minor, or of trivial for an event that starts
    there. Size never drops an event below minor."""
    if Significance.of(base) is Significance.TRIVIAL:
        return SCORE_MIN
    return SCORE_BANDS[Significance.MINOR][0]


def decided_outright(ruled: bool, start: int) -> bool:
    """Whether a context rule decided the level outright: a rule that names trivial does, since trivial is a role and
    no share moves it."""
    return ruled and Significance.of(start) is Significance.TRIVIAL


def own_score(base: int, scales: Iterable[int]) -> int:
    """``base`` moved by the highest of ``scales``, clipped at 100 and at the ``floor``; no scale leaves the base."""
    moved = max(scales, default=None)
    return base if moved is None else max(floor(base), min(SCORE_MAX, base + moved))


def _starting(midpoint: float, measure: Measure) -> ScalingSpec:
    return ScalingSpec(measure, rise=midpoint * STARTING_RISE, reason=UNEXAMINED)


SCALINGS: Mapping[Scaling, ScalingSpec] = {
    Scaling.POWER: _starting(0.01, Measure.POWER),
    Scaling.POPULATION: _starting(0.01, Measure.POPULATION),
    Scaling.ORGANIZATION: _starting(0.01, Measure.ORGANIZATION),
    Scaling.HAB: _starting(0.015, Measure.HAB),
    Scaling.FLEET: _starting(0.01, Measure.FLEET),
    Scaling.BATTLE: _starting(0.0033, Measure.BATTLE),
    Scaling.SPACE_LOSS: _starting(0.01, Measure.SPACE_LOSS),
    Scaling.FACTION: _starting(1 / 7, Measure.FACTION),  # an even split among the seven human factions
    Scaling.NUCLEAR: _starting(0.01, Measure.NUCLEAR),
}
"""Every declared scaling, one entry each: one starting scaling per measure, each unexamined. The measures that
share a starting rise share are not merged: the equal numbers may be a coincidence."""
