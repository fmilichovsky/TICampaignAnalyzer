"""Dry masses of the live ships of one snapshot: the pricing of a ship by its design (ADR-0007: snapshot context).

Evidence: docs/game-data-notes/space-assets.md. The combat analyzer prices each side of a recorded combat from the
earlier snapshot; the shares of a save sum the same masses.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field

from ...model.entities import EntityId, EntityRef
from ...model.snapshot import SaveSnapshot
from ...model.values import FrozenMap, Observed, number

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
