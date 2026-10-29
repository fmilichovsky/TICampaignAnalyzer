"""A nation's military and space-support assets, the game's strength estimate and the nation rankings.

Both kinds of army (``deploymentType`` ``Standard`` and ``Naval``) are listed in the nation's ``armies``; a navy is
a naval army. Boost (``boostPerYear_dekatons``), mission control (``missionControl``), space defences
(``antiSpaceDefenses``) and STO fighters (``numSTOFighters``) are region fields, summed over the nation's regions. A
region is occupied when it has a ``leadOccupier`` or a non-empty ``occupations`` map.

The strength estimate is the game's own, as published (``docs/game-data-notes/nation-metrics.md``, "Armies, navies
and a strength estimate"): unoccupied regions × military tech × 0.7, plus standard armies × military tech × 3 × their
mean remaining ``strength``, plus naval armies, minus unrest, plus 100 when the nation holds any nuclear weapon, plus
5 per weapon. No save field carries its result.

A value the snapshot does not establish is ``Unknown``, never zero: one region or army with an unreadable field makes
its sum unknown. The analyzers and the situation report read these through the same functions, so a ranking an
event states is the ranking the report shows.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from ...model.entities import EntityId, EntityRef
from ...model.snapshot import EntityState, SaveSnapshot
from ...model.values import FrozenMap, Observed, Unknown, UnknownReason
from ..common import Lookup, Side

STANDARD = "Standard"
NAVAL = "Naval"
BOOST = "boostPerYear_dekatons"
MISSION_CONTROL = "missionControl"
SPACE_DEFENCES = "antiSpaceDefenses"
STO_FIGHTERS = "numSTOFighters"
REGION_FIELDS = (BOOST, MISSION_CONTROL, SPACE_DEFENCES, STO_FIGHTERS, "leadOccupier", "occupations", "nation")
"""The region fields the assets read; a change of one may move a nation's assets or its rank."""
NATION_FIELDS = ("GDP", "militaryTechLevel", "unrest", "numNuclearWeapons", "armies", "regions")
"""The nation fields the assets, the strength estimate and the GDP rank read."""
ARMY_FIELDS = ("strength", "deploymentType")
"""The army fields the strength estimate reads."""

REGION_WEIGHT = 0.7
ARMY_WEIGHT = 3.0
NUCLEAR_BONUS = 100.0
PER_WEAPON = 5.0

GDP = "GDP"
STRENGTH = "strength"
BOOST_METRIC = "boost"
MISSION_CONTROL_METRIC = "mission_control"
RANKED_METRICS = (GDP, STRENGTH, BOOST_METRIC, MISSION_CONTROL_METRIC)
"""The metrics nations are ranked by, in the order they are reported."""


def _unparseable() -> Unknown:
    return Unknown(UnknownReason.UNPARSEABLE)


@dataclass(frozen=True)
class NationAssets:
    """One nation's armies and space-support assets on one side; each value is a number or ``Unknown``."""

    armies: int | Unknown = field(default_factory=Unknown)
    """Standard armies."""
    navies: int | Unknown = field(default_factory=Unknown)
    """Naval armies."""
    mean_army_strength: float | None | Unknown = field(default_factory=Unknown)
    """The mean remaining ``strength`` of the standard armies; ``None`` without one."""
    unoccupied_regions: int | Unknown = field(default_factory=Unknown)
    boost: float | Unknown = field(default_factory=Unknown)
    mission_control: float | Unknown = field(default_factory=Unknown)
    space_defence_regions: int | Unknown = field(default_factory=Unknown)
    """Regions with ``antiSpaceDefenses``."""
    sto_fighters: float | Unknown = field(default_factory=Unknown)
    defended_regions: int | Unknown = field(default_factory=Unknown)
    """Regions with ``antiSpaceDefenses`` or STO fighters: the ``spaceDefences`` statistic."""


def _number(value: Observed) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def refs(value: Observed) -> tuple[EntityId, ...] | None:
    """The entity IDs of a known reference list; ``None`` for an unknown value or one with an unresolved entry."""
    if not isinstance(value, tuple) or not all(isinstance(item, EntityRef) for item in value):
        return None
    return tuple(item.entity_id for item in value if isinstance(item, EntityRef))


def _unknown(value: Observed) -> Unknown:
    """The ``Unknown`` itself (an absent field stays ``missing``), or ``unparseable`` for a value of the wrong kind."""
    return value if isinstance(value, Unknown) else _unparseable()


def region_sum(lookup: Lookup, regions: tuple[EntityId, ...], name: str, side: Side) -> float | Unknown:
    """The summed numeric field ``name`` of ``regions``; unknown when any region's value is."""
    values: list[float] = []
    for region in regions:
        state = lookup.state(region, side)
        raw = state.get(name) if state is not None else Unknown()
        value = _number(raw)
        if value is None:
            return _unknown(raw)
        values.append(value)
    return math.fsum(values)


def defended(state: EntityState | None) -> bool | None:
    """Whether a region has space defences or STO fighters; ``None`` when either field is unreadable."""
    if state is None:
        return None
    flag, fighters = state.get(SPACE_DEFENCES), _number(state.get(STO_FIGHTERS))
    if not isinstance(flag, bool) or fighters is None:
        return None
    return flag or fighters > 0


def _occupied(state: EntityState | None) -> bool | None:
    if state is None:
        return None
    occupier, occupations = state.get("leadOccupier"), state.get("occupations")
    if isinstance(occupier, EntityRef) or (isinstance(occupations, FrozenMap) and occupations.items):
        return True
    if occupier is None and isinstance(occupations, FrozenMap):
        return False
    return None


def _count(flags: list[bool | None], raws: list[Observed]) -> int | Unknown:
    """The regions whose flag is true; unknown, as the first unreadable region's value is, when any flag is."""
    for flag, raw in zip(flags, raws, strict=True):
        if flag is None:
            return _unknown(raw)
    return sum(flag is True for flag in flags)


def assets(lookup: Lookup, nation: EntityState, side: Side) -> NationAssets:
    """The nation's assets as ``side`` of ``lookup`` shows them."""
    regions = refs(nation.get("regions"))
    armies = refs(nation.get("armies"))
    standard: int | Unknown = _unparseable()
    naval: int | Unknown = _unparseable()
    mean: float | None | Unknown = _unparseable()
    if armies is not None:
        kinds = [lookup.state(army, side) for army in armies]
        deployments = [state.get("deploymentType") if state is not None else None for state in kinds]
        if all(kind in (STANDARD, NAVAL) for kind in deployments):
            strengths = [
                _number(state.get("strength")) if state is not None else None
                for state, kind in zip(kinds, deployments, strict=True)
                if kind == STANDARD
            ]
            standard, naval = len(strengths), len(deployments) - len(strengths)
            known = [value for value in strengths if value is not None]
            if len(known) == len(strengths):
                mean = math.fsum(known) / len(known) if known else None
    if regions is None:
        return NationAssets(armies=standard, navies=naval, mean_army_strength=mean)
    states = [lookup.state(region, side) for region in regions]

    def raw(name: str) -> list[Observed]:
        return [state.get(name) if state is not None else Unknown() for state in states]

    flags = raw(SPACE_DEFENCES)
    return NationAssets(
        armies=standard,
        navies=naval,
        mean_army_strength=mean,
        unoccupied_regions=_count(
            [None if (busy := _occupied(state)) is None else not busy for state in states], raw("occupations")
        ),
        boost=region_sum(lookup, regions, BOOST, side),
        mission_control=region_sum(lookup, regions, MISSION_CONTROL, side),
        space_defence_regions=_count([flag if isinstance(flag, bool) else None for flag in flags], flags),
        sto_fighters=region_sum(lookup, regions, STO_FIGHTERS, side),
        defended_regions=_count([defended(state) for state in states], flags),
    )


def strength(nation: EntityState, held: NationAssets) -> float | Unknown:
    """The game's published strength estimate (module docstring); unknown, as its first unknown input, when any is."""
    inputs = {name: nation.get(name) for name in ("militaryTechLevel", "unrest", "numNuclearWeapons")}
    miltech, unrest, weapons = (_number(value) for value in inputs.values())
    regions, armies, navies, mean = held.unoccupied_regions, held.armies, held.navies, held.mean_army_strength
    unknown = next(
        (value for value in (*inputs.values(), regions, armies, navies, mean) if isinstance(value, Unknown)), None
    )
    if unknown is not None:
        return unknown
    if (
        miltech is None
        or unrest is None
        or weapons is None
        or isinstance(regions, Unknown)
        or isinstance(armies, Unknown)
        or isinstance(navies, Unknown)
        or isinstance(mean, Unknown)
    ):
        return _unparseable()
    army_term = armies * miltech * ARMY_WEIGHT * (mean or 0.0)
    nuclear = (NUCLEAR_BONUS if weapons > 0 else 0.0) + PER_WEAPON * weapons
    return regions * miltech * REGION_WEIGHT + army_term + navies - unrest + nuclear


def metric(nation: EntityState, held: NationAssets, name: str) -> float | None:
    """The nation's value of one ranked metric; ``None`` when unknown."""
    if name == GDP:
        return _number(nation.get(GDP))
    if name == STRENGTH:
        value: Observed = strength(nation, held)
    elif name == BOOST_METRIC:
        value = held.boost
    else:
        value = held.mission_control
    return _number(value)


@dataclass(frozen=True)
class Standing:
    """A nation's place by one metric (1 is the largest) and its value there."""

    rank: int
    value: float


def ranking(values: Mapping[EntityId, float]) -> dict[EntityId, Standing]:
    """Places by value, largest first, ties broken by entity ID."""
    ordered = sorted(values.items(), key=lambda item: (-item[1], item[0].sort_key))
    return {nation: Standing(position, value) for position, (nation, value) in enumerate(ordered, start=1)}


def standings(snapshot: SaveSnapshot, lookup: Lookup, side: Side) -> dict[str, dict[EntityId, Standing]]:
    """Every ranked metric's places among the snapshot's nations that hold regions and have a known value.

    ``lookup`` reads ``snapshot`` on ``side``.
    """
    values: dict[str, dict[EntityId, float]] = {name: {} for name in RANKED_METRICS}
    for nation in snapshot.nations:
        if not refs(nation.get("regions")):
            continue
        held = assets(lookup, nation, side)
        for name in RANKED_METRICS:
            value = metric(nation, held, name)
            if value is not None:
                values[name][nation.ref.entity_id] = value
    return {name: ranking(by_nation) for name, by_nation in values.items()}
