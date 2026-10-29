"""Nation population moving beyond what territory explains, with the nuclear detonations and tracked causes.

Population is the sum over the nation's regions, so the *residual* (later population minus regions gained plus
regions lost, both read in the later save) separates real growth or decline from territory changing hands. The
threshold is a hypothesis until a depopulation is observed (``docs/game-data-notes/nation-metrics.md``,
"Population"). Whether a drop is a collapse is the narrative stage's call. Placeholder nations are skipped.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from ...model.changes import StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId, EntityRef
from ...model.events import Event, EventSource, SourceRole
from ...model.snapshot import SaveSnapshot
from ...model.values import FieldValue, FrozenMap, Unknown
from ..common import ChangeIndex, EventBuilder, Lookup, Side, primary
from .nation_metrics import TRACKERS, cause_deltas, interval_days, number, placeholder

POPULATION_CHANGED = "nation.population_changed"
POPULATION = "populationInMillions"
DETONATIONS = "nuclearDetonations"
DAYS_PER_YEAR = 365.25
POPULATION_DROP_FLOOR = 0.05
"""The smallest residual move that counts, whatever the interval."""
POPULATION_DROP_RATE_PER_YEAR = 0.10
"""The residual move per year that counts over a long interval, far above the routine rate."""
POPULATION_CAUSES = {"GDP": "GDPReason_PopulationChange", "education": "EducationReason_PopulationLoss"}
"""Per statistic with a cause tracker (``nation_metrics.TRACKERS``), the reason that names a population change."""
DROP = "drop"
GROWTH = "growth"


def population_limit(days: float | None) -> float:
    """The relative residual move needed over ``days``, in either direction (``None``: the floor alone)."""
    if days is None:
        return POPULATION_DROP_FLOOR
    return max(POPULATION_DROP_FLOOR, POPULATION_DROP_RATE_PER_YEAR * days / DAYS_PER_YEAR)


class NationPopulationAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = ChangeIndex(diff)
        lookup = Lookup(before, after)
        build = EventBuilder(before, after)
        days = interval_days(before, after)
        moves = region_moves(index)
        events: list[Event] = []
        for nation in _affected(index, moves, lookup):
            event = _population_changed(nation, moves.get(nation, []), days, index, lookup, build)
            if event is not None:
                events.append(event)
        return events


def region_moves(index: ChangeIndex) -> dict[EntityId, list[StateChange]]:
    """The region ``nation`` changes naming each nation on either side."""
    moves: dict[EntityId, list[StateChange]] = defaultdict(list)
    for change in index.fields(EntityDomain.REGION, "nation"):
        for value in (change.before, change.after):
            if isinstance(value, EntityRef):
                moves[value.entity_id].append(change)
    return moves


def _affected(index: ChangeIndex, moves: dict[EntityId, list[StateChange]], lookup: Lookup) -> list[EntityId]:
    """The nations whose regions changed population or hands, in ID order."""
    nations = set(moves)
    for change in index.fields(EntityDomain.REGION, POPULATION):
        if change.entity_id is None:
            continue
        for side in (Side.BEFORE, Side.AFTER):
            owner = lookup.ref_field(change.entity_id, "nation", side)
            if owner is not None:
                nations.add(owner.entity_id)
    return sorted(nations, key=lambda nation: nation.sort_key)


def _regions(nation: EntityId, side: Side, lookup: Lookup) -> tuple[EntityId, ...] | None:
    state = lookup.state(nation, side)
    regions = state.get("regions") if state is not None else None
    if not isinstance(regions, tuple) or not all(isinstance(region, EntityRef) for region in regions):
        return None
    return tuple(region.entity_id for region in regions if isinstance(region, EntityRef))


def moved(moves: Iterable[StateChange], nation: EntityId, side: Side) -> list[EntityId]:
    """The regions that moved to the nation (``AFTER``) or away from it (``BEFORE``)."""
    regions: list[EntityId] = []
    for change in moves:
        value = change.after if side is Side.AFTER else change.before
        if change.entity_id is not None and isinstance(value, EntityRef) and value.entity_id == nation:
            regions.append(change.entity_id)
    return regions


def _population_changed(
    nation: EntityId,
    moves: list[StateChange],
    days: float | None,
    index: ChangeIndex,
    lookup: Lookup,
    build: EventBuilder,
) -> Event | None:
    held_before, held_after = _regions(nation, Side.BEFORE, lookup), _regions(nation, Side.AFTER, lookup)
    if held_before is None or held_after is None or placeholder(nation, lookup):
        return None
    before = number(lookup.population(held_before, Side.BEFORE))
    after = number(lookup.population(held_after, Side.AFTER))
    gained = number(lookup.population(moved(moves, nation, Side.AFTER), Side.AFTER))
    lost = number(lookup.population(moved(moves, nation, Side.BEFORE), Side.AFTER))
    if before is None or after is None or gained is None or lost is None or before <= 0:
        return None
    residual = after - gained + lost
    relative = residual / before - 1
    if abs(relative) < population_limit(days):
        return None
    sources = [
        primary(change)
        for region in sorted(set(held_before) | set(held_after), key=lambda region: region.sort_key)
        if (change := index.field(region, POPULATION)) is not None
    ]
    sources.extend(EventSource(change, SourceRole.CORROBORATING) for change in moves)
    nuked: list[EntityRef] = []
    for region in sorted(set(held_before) | set(held_after), key=lambda region: region.sort_key):
        detonations = index.field(region, DETONATIONS)
        if detonations is None:
            continue
        old, new = number(detonations.before), number(detonations.after)
        if old is not None and new is not None and new > old:
            sources.append(EventSource(detonations, SourceRole.CORROBORATING))
            ref = lookup.ref(region)
            if ref is not None:
                nuked.append(ref)
    causes: list[tuple[str, FieldValue]] = []
    for statistic, reason in POPULATION_CAUSES.items():
        tracker = index.field(nation, TRACKERS[statistic])
        if tracker is None:
            continue
        deltas = cause_deltas(tracker.before, tracker.after)
        delta = dict(deltas.items).get(reason) if isinstance(deltas, FrozenMap) else None
        if delta is not None and not isinstance(delta, Unknown):
            sources.append(EventSource(tracker, SourceRole.CORROBORATING))
            causes.append((reason, delta))
    if not sources:
        return None
    return build.event(
        POPULATION_CHANGED,
        id_parts=(nation,),
        sources=sources,
        entities=(lookup.ref(nation),),
        attributes=(
            ("direction", DROP if relative < 0 else GROWTH),
            ("before", before),
            ("after", after),
            ("residual", residual),
            ("relative_change", relative),
            ("interval_days", days),
            ("nuked_regions", tuple(nuked)),
            ("causes", FrozenMap(tuple(causes))),
        ),
    )
