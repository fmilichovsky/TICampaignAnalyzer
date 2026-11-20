"""Shares: each entity's share of a world total in one save, the shares of entity-scaled significance (ADR-0011).

``build_shares`` measures a snapshot once into a ``SaveShares``, which holds no snapshot (ADR-0012). Atomic scoring
reads the two of an interval, narrative scoring the sequence of a campaign.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import assert_never

from ..analyzers.common import Lookup, Side
from ..analyzers.politics.nation_assets import BOOST, MISSION_CONTROL, assets, refs, region_sum, strength
from ..config import PowerSettings, SignificanceSettings
from ..model.entities import EntityId, EntityRef
from ..model.kinds import Measure
from ..model.snapshot import SaveSnapshot
from ..model.values import FrozenMap, Observed, number
from ..reconstruction.common import control_points


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
    """The power share of every nation holding regions with known GDP, population and strength in ``snapshot``."""
    return _nation_power(snapshot, Lookup(snapshot, snapshot), weights)


def _nation_power(snapshot: SaveSnapshot, lookup: Lookup, weights: PowerSettings) -> dict[EntityId, float]:
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
    """Each region's share of the summed population of ``regions``, over those with a known population."""
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


# --- Space and faction shares -----------------------------------------------------------------------------
# Evidence: docs/game-data-notes/space-assets.md. Only ``w_space`` is a user setting; the rest are code constants.

HAB_FLOOR = 25.0
"""Σ tier² of human habs below which a hab share is read against this instead: keeps a share defined before humans
hold a hab, and stops one tier-1 station being half of human space."""
HAB_SATURATION = 400.0
"""Σ tier² of human habs at which space counts fully in a faction share."""
FLEET_SATURATION = 1_000_000_000.0
"""Dry mass (kg, 1,000 kt) of human ships at which space counts fully in a faction share; also the floor of a fleet
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
    """How far space counts in a faction share: ``w_space`` times how far humans have reached the saturation."""
    reached = (min(1.0, human_hab_weight / HAB_SATURATION) + min(1.0, human_mass / FLEET_SATURATION)) / 2
    return w_space * reached


def faction_share(
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


# --- The shares of a save ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class SaveShares:
    """The finished shares of one save, and what the special readings (a control point, a battle, the nuclear arc) need.

    Every field defaults to nothing, so a test builds one from plain numbers; ``build_shares`` measures a snapshot.
    """

    power: Mapping[EntityId, float] = field(default_factory=dict)
    population: Mapping[EntityId, float] = field(default_factory=dict)
    organization: Mapping[EntityId, float] = field(default_factory=dict)
    hab: Mapping[EntityId, float] = field(default_factory=dict)
    fleet: Mapping[EntityId, float] = field(default_factory=dict)
    faction: Mapping[EntityId, float] = field(default_factory=dict)
    control_points: Mapping[EntityId, int] = field(default_factory=dict)
    """The control points each nation lists; a nation without any is not a key."""
    boost: Mapping[EntityId, float] = field(default_factory=dict)  # PROTOTYPE #578
    mission_control: Mapping[EntityId, float] = field(default_factory=dict)  # PROTOTYPE #578
    world_warheads: float | None = None
    """The warheads of every nation whose count is known (ADR-0005: absent is not zero); ``None`` when none is."""
    masses: ShipMasses = field(default_factory=lambda: ShipMasses({}, {}, {}))
    """The dry masses a battle's designs are read from."""
    world_ship_mass: float = 0.0
    """Σ dry mass (kg) of every faction's ships, alien ships weighted up: the world total of a battle."""

    def of(self, measure: Measure) -> Mapping[EntityId, float]:
        """The shares of a measure; a battle share is read from a combat record and a nuclear one is an arc's net move,
        so neither has shares."""
        match measure:
            case Measure.POWER:
                return self.power
            case Measure.POPULATION:
                return self.population
            case Measure.ORGANIZATION:
                return self.organization
            case Measure.HAB:
                return self.hab
            case Measure.FLEET:
                return self.fleet
            case Measure.SPACE_LOSS:
                return {**self.fleet, **self.hab}  # ship and hab IDs never collide
            case Measure.FACTION:
                return self.faction
            case Measure.BOOST:
                return self.boost
            case Measure.MISSION_CONTROL:
                return self.mission_control
            case Measure.BATTLE:
                raise ValueError("a battle share is read from a combat record, not from shares")
            case Measure.NUCLEAR:
                raise ValueError("a nuclear share is a narrative arc's net move, not a save's shares")
            case _:
                assert_never(measure)


def build_shares(snapshot: SaveSnapshot, settings: SignificanceSettings) -> SaveShares:
    """Every share of ``snapshot``, measured once; the result holds no snapshot."""
    lookup = Lookup(snapshot, snapshot)
    power = _nation_power(snapshot, lookup, settings.power)
    masses = ship_masses(snapshot)
    weights = hab_weights(snapshot)
    hab_weight = _faction_hab_weights(snapshot, lookup)
    kinds = {state.ref.entity_id: lookup.faction_kind(state.ref.entity_id) for state in snapshot.factions}
    human = [faction for faction, kind in kinds.items() if kind != "alien"]
    human_hab = sum(hab_weight.get(faction, 0.0) for faction in human)
    human_mass = sum(masses.by_faction.get(faction, 0.0) for faction in human)
    earth = _earth_shares(snapshot, lookup, power)
    faction = {
        entity: earth[entity]
        if kind == "alien"
        else faction_share(
            earth[entity],
            hab_weight.get(entity, 0.0),
            masses.by_faction.get(entity, 0.0),
            human_hab,
            human_mass,
            settings.w_space,
        )
        for entity, kind in kinds.items()
    }
    warheads = [count for state in snapshot.nations if (count := number(state.get("numNuclearWeapons"))) is not None]
    return SaveShares(
        power=power,
        population=region_shares(snapshot),
        organization=organization_shares(snapshot, settings.tier_exponent),
        hab={hab: hab_share(weight, human_hab) for hab, weight in weights.items()},
        fleet={asset: fleet_share(mass, human_mass) for asset, mass in masses.by_asset.items()},
        faction=faction,
        control_points={
            state.ref.entity_id: len(listed)
            for state in snapshot.nations
            if isinstance(listed := state.get("controlPoints"), tuple) and listed
        },
        boost=_space_support_shares(snapshot, lookup, BOOST),
        mission_control=_space_support_shares(snapshot, lookup, MISSION_CONTROL),
        world_warheads=math.fsum(warheads) if warheads else None,
        masses=masses,
        world_ship_mass=sum(
            masses.by_faction.get(entity, 0.0) * (ALIEN_MASS_WEIGHT if kind == "alien" else 1.0)
            for entity, kind in kinds.items()
        ),
    )


def _space_support_shares(snapshot: SaveSnapshot, lookup: Lookup, name: str) -> dict[EntityId, float]:
    """PROTOTYPE #578: each nation's summed region field ``name`` over every nation's; unknown sums count nothing."""
    held: dict[EntityId, float] = {}
    for state in snapshot.nations:
        regions = refs(state.get("regions"))
        if regions is None:
            continue
        value = region_sum(lookup, regions, name, Side.AFTER)
        if isinstance(value, float) and value > 0:
            held[state.ref.entity_id] = value
    return _normalized(held)


def _faction_hab_weights(snapshot: SaveSnapshot, lookup: Lookup) -> dict[EntityId, float]:
    """Σ tier² of the habs each faction owns; a hab without a faction of the snapshot counts for no one."""
    held: defaultdict[EntityId, float] = defaultdict(float)
    for hab in snapshot.habs:
        owner = hab.get("faction")
        tier = number(hab.get("tier"))
        if isinstance(owner, EntityRef) and lookup.state(owner.entity_id, Side.AFTER) is not None and tier is not None:
            held[owner.entity_id] += max(tier, 0.0) ** 2
    return dict(held)


def _earth_shares(
    snapshot: SaveSnapshot, lookup: Lookup, power: Mapping[EntityId, float]
) -> defaultdict[EntityId, float]:
    """Each faction's Earth share: each nation's power share times the faction's share of that nation's control
    points; uncontrolled and unresolved points belong to no one."""
    earth: defaultdict[EntityId, float] = defaultdict(float)
    for nation in snapshot.nations:
        share = power.get(nation.ref.entity_id)
        points = control_points(lookup, nation.ref.entity_id, Side.AFTER)
        if share is None or not points:
            continue
        held: Counter[EntityId] = Counter()
        for point in points:
            state = lookup.state(point.entity_id, Side.AFTER)
            controller = state.get("faction") if state is not None else None
            resolved = lookup.resolve(controller) if isinstance(controller, EntityRef) else None
            if resolved is not None:
                held[resolved.entity_id] += 1
        for faction, count in held.items():
            earth[faction] += share * count / len(points)
    return earth
