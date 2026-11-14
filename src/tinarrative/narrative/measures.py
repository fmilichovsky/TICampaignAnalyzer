"""The stake measure registry: each measure's reference, label and description, and the score clamp (ADR-0011).

Settings change shares; the registry calibrates the scale. No reference is a setting. The stakes and kinds that use a
measure are derived (a kind's ``stake``, its implementation in ``significance``, its measure), never declared here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from ..model.kinds import StakeMeasure

__all__ = ["MEASURES", "SCALE_MAX", "SCALE_MIN", "MeasureSpec"]

SCALE_MIN: Final = -20
"""The stake lowers a score by at most this many points."""
SCALE_MAX: Final = 15
"""The stake raises a score by at most this many points."""


@dataclass(frozen=True)
class MeasureSpec:
    """One stake measure's calibration."""

    reference: float
    """The share at which a stake leaves a score at its base; each tenfold share above or below moves it ten points."""
    label: str
    """A short name for the measure, as a reader sees it."""
    description: str
    """What the share is a share of, in a reader's words."""


MEASURES: Mapping[StakeMeasure, MeasureSpec] = {
    StakeMeasure.POWER: MeasureSpec(
        reference=0.01,
        label="Nation power",
        description=(
            "A nation's power share: its weighted shares of world GDP, population and strength; also the unit of "
            "every nation-scaled event type."
        ),
    ),
    StakeMeasure.POPULATION: MeasureSpec(
        reference=0.01,
        label="Population",
        description="A share of world population: the territory a region or territory event moved.",
    ),
    StakeMeasure.ORGANIZATION: MeasureSpec(
        reference=0.01,
        label="Organization",
        description="An organization's tier, raised to the tier exponent, over the total of all organizations.",
    ),
    StakeMeasure.HAB: MeasureSpec(
        reference=0.015,
        label="Hab",
        description="A hab's tier² over the human habs' total, which has a floor.",
    ),
    StakeMeasure.FLEET: MeasureSpec(
        reference=0.01,
        label="Fleet",
        description="A ship's or fleet's dry mass over the human ships' total, which has a floor.",
    ),
    StakeMeasure.BATTLE: MeasureSpec(
        reference=0.0033,
        label="Battle",
        description="A combat's contested mass over the world's weighted ship mass.",
    ),
    StakeMeasure.FACTION: MeasureSpec(
        reference=1 / 7,  # an even split among the seven human factions
        label="Faction",
        description="A faction's weight in the world: its Earth share blended with its space share.",
    ),
    StakeMeasure.NUCLEAR: MeasureSpec(
        reference=0.01,
        label="Nuclear share",
        description="A nuclear arc's net move over the world's warheads at the arc's larger end.",
    ),
}
"""Every stake measure's calibration, one entry each."""
