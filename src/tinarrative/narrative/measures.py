"""The measure registry: each measure's label and description (ADR-0011).

How a share on a measure moves a level is a scaling's (``narrative.scalings``). The shares and kinds that use a
measure are derived (a kind's ``share``, its implementation in ``significance``, its measure), never declared here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..model.kinds import Measure

__all__ = ["MEASURES", "MeasureSpec"]


@dataclass(frozen=True)
class MeasureSpec:
    """One measure, as a reader sees it."""

    label: str
    """A short name for the measure, as a reader sees it."""
    description: str
    """What the share is a share of, in a reader's words."""


MEASURES: Mapping[Measure, MeasureSpec] = {
    Measure.POWER: MeasureSpec(
        label="Nation power",
        description=(
            "A nation's power share: its weighted shares of world GDP, population and strength; also the unit of "
            "every nation-scaled event type."
        ),
    ),
    Measure.POPULATION: MeasureSpec(
        label="Population",
        description="A share of world population: the territory a region or territory event moved.",
    ),
    Measure.ORGANIZATION: MeasureSpec(
        label="Organization",
        description="An organization's tier, raised to the tier exponent, over the total of all organizations.",
    ),
    Measure.HAB: MeasureSpec(
        label="Hab",
        description="A hab's tier² over the human habs' total, which has a floor.",
    ),
    Measure.FLEET: MeasureSpec(
        label="Fleet",
        description="A ship's or fleet's dry mass over the human ships' total, which has a floor.",
    ),
    Measure.BATTLE: MeasureSpec(
        label="Battle",
        description="A combat's contested mass over the world's weighted ship mass.",
    ),
    Measure.SPACE_LOSS: MeasureSpec(
        label="Space loss",
        description=(
            "The dry mass of the ships and the tier² of the habs a faction lost, over the human ships' and habs' "
            "totals, which have floors."
        ),
    ),
    Measure.FACTION: MeasureSpec(
        label="Faction",
        description="A faction's weight in the world: its Earth share blended with its space share.",
    ),
    Measure.NUCLEAR: MeasureSpec(
        label="Nuclear share",
        description="A nuclear arc's net move over the world's warheads at the arc's larger end.",
    ),
}
"""Every measure, one entry each."""
