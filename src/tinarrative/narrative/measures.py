"""The measure registry: each measure's reference, label and description, and the score clamp (ADR-0011).

Settings change shares; the registry calibrates the scale. No reference is a setting. The shares and kinds that use a
measure are derived (a kind's ``share``, its implementation in ``significance``, its measure), never declared here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from ..model.kinds import Measure

__all__ = ["MEASURES", "SCALE_MAX", "SCALE_MIN", "MeasureSpec"]

SCALE_MIN: Final = -20
"""The share lowers a score by at most this many points."""
SCALE_MAX: Final = 15
"""The share raises a score by at most this many points."""


@dataclass(frozen=True)
class MeasureSpec:
    """One measure's calibration."""

    reference: float
    """The share at which a share leaves a score at its base; each tenfold share above or below moves it ten points."""
    label: str
    """A short name for the measure, as a reader sees it."""
    description: str
    """What the share is a share of, in a reader's words."""


MEASURES: Mapping[Measure, MeasureSpec] = {
    Measure.POWER: MeasureSpec(
        reference=0.01,
        label="Nation power",
        description=(
            "A nation's power share: its weighted shares of world GDP, population and strength; also the unit of "
            "every nation-scaled event type."
        ),
    ),
    Measure.POPULATION: MeasureSpec(
        reference=0.01,
        label="Population",
        description="A share of world population: the territory a region or territory event moved.",
    ),
    Measure.ORGANIZATION: MeasureSpec(
        reference=0.01,
        label="Organization",
        description="An organization's tier, raised to the tier exponent, over the total of all organizations.",
    ),
    Measure.HAB: MeasureSpec(
        reference=0.015,
        label="Hab",
        description="A hab's tier² over the human habs' total, which has a floor.",
    ),
    Measure.FLEET: MeasureSpec(
        reference=0.01,
        label="Fleet",
        description="A ship's or fleet's dry mass over the human ships' total, which has a floor.",
    ),
    Measure.BATTLE: MeasureSpec(
        reference=0.0033,
        label="Battle",
        description="A combat's contested mass over the world's weighted ship mass.",
    ),
    Measure.SPACE_LOSS: MeasureSpec(
        reference=0.01,
        label="Space loss",
        description=(
            "The dry mass of the ships and the tier² of the habs a faction lost, over the human ships' and habs' "
            "totals, which have floors."
        ),
    ),
    Measure.FACTION: MeasureSpec(
        reference=1 / 7,  # an even split among the seven human factions
        label="Faction",
        description="A faction's weight in the world: its Earth share blended with its space share.",
    ),
    Measure.NUCLEAR: MeasureSpec(
        reference=0.01,
        label="Nuclear share",
        description="A nuclear arc's net move over the world's warheads at the arc's larger end.",
    ),
    # PROTOTYPE #578: unexamined starting references for the space program draft share.
    Measure.BOOST: MeasureSpec(
        reference=0.01,
        label="Boost",
        description="A nation's share of world boost: the summed boost of its regions over every nation's.",
    ),
    Measure.MISSION_CONTROL: MeasureSpec(
        reference=0.01,
        label="Mission control",
        description="A nation's share of world mission control: its regions' over every nation's.",
    ),
}
"""Every measure's calibration, one entry each."""
