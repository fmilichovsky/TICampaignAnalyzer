"""Prominence shares: each entity's share of a world total in one snapshot, the stakes of entity-scaled significance.

The atomic pass reads snapshots and the narrative rules read situation reports (``SituationReport.power_shares``); both
build the same shares here.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from ..analyzers.common import Lookup, Side
from ..analyzers.politics.nation_assets import assets, strength
from ..config import PowerSettings
from ..model.entities import EntityId, EntityRef
from ..model.snapshot import SaveSnapshot
from ..model.values import FrozenMap, Observed, number


@dataclass(frozen=True)
class PowerInputs:
    """One nation's world-share inputs; ``strength`` is the game's published estimate (``nation_assets.strength``)."""

    nation: EntityId
    gdp: float
    population: float
    strength: float


def power_inputs(nation: EntityId, gdp: Observed, population: Observed, estimate: Observed) -> PowerInputs | None:
    """``None`` unless all three values are numbers."""
    values = (number(gdp), number(population), number(estimate))
    if values[0] is None or values[1] is None or values[2] is None:
        return None
    # Unrest can push the estimate below zero; a share of a world total cannot be negative.
    return PowerInputs(nation, max(values[0], 0.0), max(values[1], 0.0), max(values[2], 0.0))


def power_shares(nations: Iterable[PowerInputs], weights: PowerSettings) -> dict[EntityId, float]:
    """``w_gdp·gdp_share + w_pop·pop_share + w_str·strength_share`` per nation, the shares taken over ``nations``.

    The weights are divided by their sum and a measure with a zero world total drops out, so the result sums to 1
    over ``nations`` (or is empty) and the shares of members, war sides and holdings add.
    """
    listed = list(nations)
    measures = (
        (weights.w_gdp, [item.gdp for item in listed]),
        (weights.w_pop, [item.population for item in listed]),
        (weights.w_str, [item.strength for item in listed]),
    )
    totals = [(weight, values, math.fsum(values)) for weight, values in measures]
    live = [(weight, values, world) for weight, values, world in totals if weight > 0 and world > 0]
    if not live:
        return {}
    weight_sum = math.fsum(weight for weight, _, _ in live)
    return {
        item.nation: math.fsum(weight * values[index] / world for weight, values, world in live) / weight_sum
        for index, item in enumerate(listed)
    }


def nation_power(snapshot: SaveSnapshot, weights: PowerSettings) -> dict[EntityId, float]:
    """The power share of every nation holding regions with known GDP, population and strength in ``snapshot``, as
    its situation report states them."""
    lookup = Lookup(snapshot, snapshot)
    inputs: list[PowerInputs] = []
    for state in snapshot.nations:
        regions = state.get("regions")
        if not isinstance(regions, tuple) or not regions:
            continue
        found = power_inputs(
            state.ref.entity_id,
            state.get("GDP"),
            lookup.population((ref.entity_id for ref in regions if isinstance(ref, EntityRef)), Side.AFTER),
            strength(state, assets(lookup, state, Side.AFTER)),
        )
        if found is not None:
            inputs.append(found)
    return power_shares(inputs, weights)


def region_shares(snapshot: SaveSnapshot) -> dict[EntityId, float]:
    """Each region's share of world population, over the regions with a known population."""
    return population_shares((state.ref.entity_id, state.get("populationInMillions")) for state in snapshot.regions)


def population_shares(regions: Iterable[tuple[EntityId, Observed]]) -> dict[EntityId, float]:
    """Each region's share of the summed population of ``regions``, over those with a known population; a situation
    report gives the same shares as ``region_shares`` for its snapshot."""
    return _normalized(
        {region: max(value, 0.0) for region, observed in regions if (value := number(observed)) is not None}
    )


def organization_shares(snapshot: SaveSnapshot, exponent: int) -> dict[EntityId, float]:
    """Each organization's ``tier ** exponent`` over the total of all organizations with a known tier."""
    weights = {
        state.ref.entity_id: max(value, 0.0) ** exponent
        for state in snapshot.organizations
        if (value := number(state.get("tier"))) is not None
    }
    return _normalized(weights)


def total(shares: Mapping[EntityId, float], entities: Iterable[EntityId]) -> float:
    """The summed share of the distinct ``entities`` (a war side, a federation); one without a share adds nothing."""
    return math.fsum(shares.get(entity, 0.0) for entity in set(entities))


def _normalized(values: Mapping[EntityId, float]) -> dict[EntityId, float]:
    world = math.fsum(values.values())
    return {entity: value / world for entity, value in values.items()} if world > 0 else {}


# --- Space and faction stakes -----------------------------------------------------------------------------
# Evidence: docs/game-data-notes/space-assets.md. Only ``w_space`` is a user setting; the rest are code constants.

HAB_FLOOR = 25.0
"""Σ tier² of human habs below which a hab share is read against this instead: keeps a share defined before humans
hold a hab, and stops one tier-1 station being half of human space."""
HAB_SATURATION = 400.0
"""Σ tier² of human habs at which space counts fully in a faction stake."""
FLEET_SATURATION = 1_000_000_000.0
"""Dry mass (kg, 1,000 kt) of human ships at which space counts fully in a faction stake; also the floor of a fleet
share and of the world mass of a battle."""
ALIEN_MASS_WEIGHT = 2.0
"""Alien ships count this many times their dry mass in a battle."""
CONTEST_RATIO = 2.0
"""The larger side of a battle counts for at most this multiple of the smaller side."""

PROPELLANT_KG_PER_TON = 1000.0


def dry_mass(current_mass_kg: Observed, propellant_tons: Observed) -> float | None:
    """A ship's mass without propellant, ``currentMass_kg − 1000·propellant_tons`` (the save's mass is wet and swings
    with refuelling); ``None`` unless both are numbers."""
    mass, propellant = number(current_mass_kg), number(propellant_tons)
    if mass is None or propellant is None:
        return None
    return max(mass - PROPELLANT_KG_PER_TON * propellant, 0.0)


@dataclass(frozen=True)
class ShipMasses:
    """The dry masses of the live ships of one snapshot."""

    by_design: Mapping[tuple[EntityId, str], float]
    """A ship's dry mass by its faction and design ``dataName``; ships of one design have the same. Design names are
    per faction, so two factions may reuse one."""
    by_hull: Mapping[str, float]
    """The median dry mass of the live ships of each hull class."""
    by_faction: Mapping[EntityId, float]
    """The summed dry mass of each faction's ships, those of its fleets."""
    by_asset: Mapping[EntityId, float] = field(default_factory=dict)
    """The dry mass of each ship, and of each fleet (the sum of its ships'), by ID."""

    def of(self, faction: EntityId, design: str, hull: str) -> float | None:
        """A ship of the faction's ``design``: a live one of that design, else the median of its hull class, else
        nothing."""
        found = self.by_design.get((faction, design))
        return found if found is not None else self.by_hull.get(hull)


def ship_masses(snapshot: SaveSnapshot) -> ShipMasses:
    """Every live ship with a known dry mass, in ``snapshot``; a ship whose fleet has no faction counts for no one."""
    index = snapshot.state_index
    by_design: dict[tuple[EntityId, str], float] = {}
    hulls: defaultdict[str, list[float]] = defaultdict(list)
    by_faction: defaultdict[EntityId, list[float]] = defaultdict(list)
    by_asset: defaultdict[EntityId, float] = defaultdict(float)
    for ship in snapshot.ships:
        mass = dry_mass(ship.get("currentMass_kg"), ship.get("propellant_tons"))
        fleet = ship.get("fleet")
        fleet_state = index.get(fleet.entity_id) if isinstance(fleet, EntityRef) else None
        faction = fleet_state.get("faction") if fleet_state is not None else None
        if mass is None or not isinstance(faction, EntityRef):
            continue
        by_faction[faction.entity_id].append(mass)
        by_asset[ship.ref.entity_id] = mass
        by_asset[fleet.entity_id] += mass  # type: ignore[union-attr]  # a faction implies a fleet reference
        template = ship.get("templateName")
        if not isinstance(template, str):
            continue
        by_design.setdefault((faction.entity_id, template), mass)
        faction_state = index.get(faction.entity_id)
        designs = faction_state.get("shipDesigns") if faction_state is not None else None
        design = dict(designs.items).get(template) if isinstance(designs, FrozenMap) else None
        hull = dict(design.items).get("hullName") if isinstance(design, FrozenMap) else None
        if isinstance(hull, str):
            hulls[hull].append(mass)
    return ShipMasses(
        by_design,
        {hull: statistics.median(masses) for hull, masses in hulls.items()},
        {faction: math.fsum(masses) for faction, masses in by_faction.items()},
        dict(by_asset),
    )


def hab_share(weight: float, human_weight: float) -> float:
    """``weight`` (tier²) over the human total, which is at least ``HAB_FLOOR``."""
    return weight / max(human_weight, HAB_FLOOR)


def fleet_share(mass: float, human_mass: float) -> float:
    """``mass`` (dry, kg) over the human total, which is at least ``FLEET_SATURATION``."""
    return mass / max(human_mass, FLEET_SATURATION)


def space_weight(w_space: float, human_hab_weight: float, human_mass: float) -> float:
    """How far space counts in a faction stake: ``w_space`` times how far humans have reached the saturation."""
    reached = (min(1.0, human_hab_weight / HAB_SATURATION) + min(1.0, human_mass / FLEET_SATURATION)) / 2
    return w_space * reached


def faction_stake(
    earth: float, hab_weight: float, mass: float, human_hab_weight: float, human_mass: float, w_space: float
) -> float:
    """A human faction's ``(1 − w)·earth_share + w·space_share``; ``space_share`` is the mean of its hab and fleet
    shares."""
    space = (hab_share(hab_weight, human_hab_weight) + fleet_share(mass, human_mass)) / 2
    weight = space_weight(w_space, human_hab_weight, human_mass)
    return (1 - weight) * earth + weight * space


def contested_mass(first: float, second: float) -> float:
    """The smaller side's mass plus the larger side's, capped at ``CONTEST_RATIO`` times the smaller. Symmetric: which
    side won never changes it."""
    smaller, larger = sorted((first, second))
    return smaller + min(larger, CONTEST_RATIO * smaller)


def hab_weights(snapshot: SaveSnapshot) -> dict[EntityId, float]:
    """Each hab's ``tier²``, over the habs with a known tier."""
    return {
        state.ref.entity_id: max(tier, 0.0) ** 2
        for state in snapshot.habs
        if (tier := number(state.get("tier"))) is not None
    }
