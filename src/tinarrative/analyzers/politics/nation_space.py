"""A nation's space-support assets moving: boost, mission control and the regions with space defences.

The statistics are sums over the nation's regions (``nation_assets``): ``boost`` (``boostPerYear_dekatons``),
``missionControl`` and ``spaceDefences``, the regions with ``antiSpaceDefenses`` or STO fighters. Boost and mission
control grow slowly except with territory (``docs/game-data-notes/nation-metrics.md``, "Space-support assets"), so a
change counts when it reaches ``RELATIVE_THRESHOLD`` of the earlier value and the statistic's absolute floor; a rise
from zero counts once it reaches the floor.

A region changing hands moves its assets with it. ``territory_delta`` is the later value of the regions gained minus
that of the regions lost (both read in the later save, as ``nation_population`` does), and ``territory_share`` that
delta over the whole change: 1 when territory explains it all, beyond 1 or below 0 when the held regions moved the
other way. Regions moved are the ``nation`` changes of regions in the diff. Placeholder nations are skipped.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from ...model.changes import StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId, EntityRef
from ...model.events import Event, EventSource, SourceRole
from ...model.snapshot import SaveSnapshot
from ...model.values import Unknown
from ..common import ChangeIndex, EventBuilder, Lookup, Side, primary
from .nation_assets import BOOST, MISSION_CONTROL, SPACE_DEFENCES, STO_FIGHTERS, defended, refs, region_sum
from .nation_metrics import interval_days, placeholder
from .nation_population import moved, region_moves

SPACE_ASSETS_CHANGED = "nation.space_assets_changed"
BOOST_STATISTIC = "boost"
MISSION_CONTROL_STATISTIC = "missionControl"
SPACE_DEFENCES_STATISTIC = "spaceDefences"
RELATIVE_THRESHOLD = 0.25
FLOORS: Mapping[str, float] = {BOOST_STATISTIC: 5.0, MISSION_CONTROL_STATISTIC: 2.0, SPACE_DEFENCES_STATISTIC: 1.0}
"""The smallest absolute change that counts, per statistic (boost in dekatons a year)."""
FIELDS: Mapping[str, tuple[str, ...]] = {
    BOOST_STATISTIC: (BOOST,),
    MISSION_CONTROL_STATISTIC: (MISSION_CONTROL,),
    SPACE_DEFENCES_STATISTIC: (SPACE_DEFENCES, STO_FIGHTERS),
}
"""The region fields each statistic is read from."""
GROWTH = "growth"
DECLINE = "decline"


def _defended_count(lookup: Lookup, regions: tuple[EntityId, ...], side: Side) -> float | Unknown:
    flags = [defended(lookup.state(region, side)) for region in regions]
    if any(flag is None for flag in flags):
        return Unknown()
    return sum(flag is True for flag in flags)


def _reader(statistic: str) -> Callable[[Lookup, tuple[EntityId, ...], Side], float | Unknown]:
    if statistic == SPACE_DEFENCES_STATISTIC:
        return _defended_count
    (name,) = FIELDS[statistic]
    return lambda lookup, regions, side: region_sum(lookup, regions, name, side)


def is_space_change(statistic: str, before: float, after: float) -> bool:
    change = abs(after - before)
    if change < FLOORS[statistic]:
        return False
    return before == 0 or change / abs(before) >= RELATIVE_THRESHOLD


class NationSpaceAssetsAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = ChangeIndex(diff)
        lookup = Lookup(before, after)
        build = EventBuilder(before, after)
        days = interval_days(before, after)
        moves = region_moves(index)
        events: list[Event] = []
        for nation in _affected(index, moves, lookup):
            if placeholder(nation, lookup):
                continue
            for statistic in FIELDS:
                event = _space_change(nation, statistic, moves.get(nation, []), days, index, lookup, build)
                if event is not None:
                    events.append(event)
        return events


def _affected(index: ChangeIndex, moves: Mapping[EntityId, list[StateChange]], lookup: Lookup) -> list[EntityId]:
    """The nations whose regions changed an asset field or hands, in ID order."""
    nations = set(moves)
    for name in (BOOST, MISSION_CONTROL, SPACE_DEFENCES, STO_FIGHTERS):
        for change in index.fields(EntityDomain.REGION, name):
            if change.entity_id is None:
                continue
            for side in (Side.BEFORE, Side.AFTER):
                owner = lookup.ref_field(change.entity_id, "nation", side)
                if owner is not None:
                    nations.add(owner.entity_id)
    return sorted(nations, key=lambda nation: nation.sort_key)


def _held(nation: EntityId, side: Side, lookup: Lookup) -> tuple[EntityId, ...] | None:
    state = lookup.state(nation, side)
    return refs(state.get("regions")) if state is not None else None


def _space_change(
    nation: EntityId,
    statistic: str,
    moves: list[StateChange],
    days: float | None,
    index: ChangeIndex,
    lookup: Lookup,
    build: EventBuilder,
) -> Event | None:
    held_before, held_after = _held(nation, Side.BEFORE, lookup), _held(nation, Side.AFTER, lookup)
    if held_before is None or held_after is None:
        return None
    read = _reader(statistic)
    before, after = read(lookup, held_before, Side.BEFORE), read(lookup, held_after, Side.AFTER)
    gained = read(lookup, tuple(moved(moves, nation, Side.AFTER)), Side.AFTER)
    lost = read(lookup, tuple(moved(moves, nation, Side.BEFORE)), Side.AFTER)
    if (
        isinstance(before, Unknown)
        or isinstance(after, Unknown)
        or isinstance(gained, Unknown)
        or isinstance(lost, Unknown)
        or not is_space_change(statistic, before, after)
    ):
        return None
    sources = [
        primary(change)
        for region in sorted(set(held_before) | set(held_after), key=lambda region: region.sort_key)
        for name in FIELDS[statistic]
        if (change := index.field(region, name)) is not None
    ]
    sources.extend(EventSource(change, SourceRole.CORROBORATING) for change in moves)
    if not sources:
        return None
    territory = gained - lost
    return build.event(
        SPACE_ASSETS_CHANGED,
        id_parts=(nation, statistic),
        sources=sources,
        entities=(lookup.ref(nation),),
        attributes=(
            ("statistic", statistic),
            ("direction", GROWTH if after > before else DECLINE),
            ("before", before),
            ("after", after),
            ("relative_change", None if before == 0 else (after - before) / abs(before)),
            ("territory_delta", territory),
            ("territory_share", territory / (after - before)),
            ("regions_gained", _region_refs(moved(moves, nation, Side.AFTER), lookup)),
            ("regions_lost", _region_refs(moved(moves, nation, Side.BEFORE), lookup)),
            ("interval_days", days),
        ),
    )


def _region_refs(regions: list[EntityId], lookup: Lookup) -> tuple[EntityRef, ...]:
    return tuple(ref for region in regions if (ref := lookup.ref(region)) is not None)
