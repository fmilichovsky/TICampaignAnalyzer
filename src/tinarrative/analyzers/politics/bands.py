"""The game's value bands of the nation statistics (Peaceful ... Civil War) and margin-guarded crossings.

Boundaries are published game vocabulary, not read from a save; provenance in
``docs/game-data-notes/nation-metrics.md`` ("Value bands"). A crossing counts only when the value ends ``MARGINS``
beyond the last boundary crossed, so a hair's move across a boundary is noise.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass

from ...model.values import FrozenMap

BANDS: Mapping[str, tuple[tuple[float, str], ...]] = {
    "unrest": (
        (-math.inf, "Peaceful"),
        (1.5, "Subversion"),
        (3.0, "Strife"),
        (4.5, "Insurgency"),
        (6.0, "Guerilla War"),
        (7.5, "Insurrection"),
        (9.0, "Civil War"),
    ),
    "democracy": (
        (-math.inf, "Totalitarian"),
        (2.0, "Authoritarian"),
        (4.0, "Anocracy"),
        (6.0, "Flawed Democracy"),
        (8.0, "Full Democracy"),
    ),
    "education": ((-math.inf, "Limited"), (5.0, "Developing"), (8.0, "Advanced")),
    "cohesion": (
        (-math.inf, "Fragmented"),
        (1.0, "Fractured"),
        (2.0, "Sectarian"),
        (3.0, "Polarized"),
        (4.0, "Competitive"),
        (5.0, "Diverse"),
        (6.0, "Integrated"),
        (7.0, "Homogenous"),
        (8.0, "Dominated"),
        (9.0, "Hegemonic"),
        (10.0, "Monolithic"),
    ),
    "inequality": (
        (-math.inf, "Very Low"),
        (2.0, "Low"),
        (3.0, "Moderate"),
        (4.0, "High"),
        (5.0, "Very High"),
        (6.0, "Extreme"),
    ),
    "militaryTechLevel": (
        (-math.inf, "Industrial"),
        (3.0, "Atomic"),
        (4.0, "Information"),
        (5.0, "Robotics"),
        (6.0, "Invasion"),
        (7.0, "Fusion"),
    ),
}
"""Per banded statistic, its bands in ascending order as ``(lower bound, label)``; the first is unbounded below."""

BAND_MARGIN = 0.25
MILTECH_MARGIN = 0.1
"""Military tech moves in smaller steps than the 0-10 scores, so its margin is smaller."""

MARGINS: Mapping[str, float] = {statistic: BAND_MARGIN for statistic in BANDS} | {"militaryTechLevel": MILTECH_MARGIN}
"""How far beyond the last boundary it crossed a value must end for the crossing to count."""

TOLERANCE = 1e-9
"""Float slack on the margin: a move of exactly the margin (5.0 to 4.9) can compute a hair short of it."""

REST_VALUE_SUFFIX = "_MovementToRestValue"
"""The cause reason of the game converging a statistic towards its rest value (``UnrestReason_MovementToRestValue``)."""


@dataclass(frozen=True)
class Crossing:
    """A move between two bands of one statistic."""

    from_band: str
    to_band: str
    bands_crossed: int
    """The number of boundaries crossed, whatever the direction."""
    boundary: float
    """The last boundary crossed, the one nearest the later value."""
    margin: float
    """How far beyond ``boundary`` the later value ends."""


def _index(statistic: str, value: float) -> int:
    return bisect_right([bound for bound, _ in BANDS[statistic]], value) - 1


def band(statistic: str, value: float) -> str:
    return BANDS[statistic][_index(statistic, value)][1]


UNREST_SEVERE = 4.5
"""The lower bound of Insurgency."""
COHESION_EXTREMES = (1.0, 9.0)
"""Fragmented below the first, Hegemonic and Monolithic from the second."""
ALWAYS_MAJOR = frozenset({"democracy", "education", "militaryTechLevel"})
"""The statistics whose every band shift is major."""


def crosses(boundary: float, before: float, after: float) -> bool:
    """Whether a move from ``before`` to ``after`` passes ``boundary``."""
    return (before < boundary) != (after < boundary)


def crossed(statistic: str, before: float, after: float) -> Crossing | None:
    """The band move from ``before`` to ``after``; ``None`` when both are in one band."""
    start, end = _index(statistic, before), _index(statistic, after)
    if start == end:
        return None
    bands = BANDS[statistic]
    boundary = bands[end][0] if end > start else bands[end + 1][0]
    return Crossing(bands[start][1], bands[end][1], abs(end - start), boundary, abs(after - boundary))


def margin_crossing(statistic: str, before: float, after: float) -> Crossing | None:
    """The crossing when it clears the statistic's margin, else ``None``."""
    crossing = crossed(statistic, before, after)
    return crossing if crossing is not None and crossing.margin >= MARGINS[statistic] - TOLERANCE else None


def rest_value_delta(causes: FrozenMap) -> float:
    """The delta under the rest-value reason of a cause-delta map (0 when absent)."""
    return sum(
        value
        for reason, value in causes.items
        if reason.endswith(REST_VALUE_SUFFIX) and isinstance(value, int | float) and not isinstance(value, bool)
    )
