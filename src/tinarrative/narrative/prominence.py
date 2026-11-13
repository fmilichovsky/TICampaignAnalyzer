"""Prominence shares: each entity's share of a world total in one snapshot, the stakes of entity-scaled significance.

The atomic pass reads snapshots and the narrative rules read situation reports (``SituationReport.power_shares``); both
build the same shares here.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ..analyzers.common import Lookup, Side
from ..analyzers.politics.nation_assets import assets, strength
from ..config import PowerSettings
from ..model.entities import EntityId, EntityRef
from ..model.snapshot import SaveSnapshot
from ..model.values import Observed, number


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
    populations = {
        state.ref.entity_id: max(value, 0.0)
        for state in snapshot.regions
        if (value := number(state.get("populationInMillions"))) is not None
    }
    return _normalized(populations)


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
