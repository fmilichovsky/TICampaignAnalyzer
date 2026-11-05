"""A nation's place by GDP, strength estimate, boost or mission control changing within the top ``RANKED_PLACES``.

A place is relative, so the event cites the nation's own input changes as primary and those of every nation whose
order against it reversed as corroborating; with no change of its own, the others' are primary.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ...model.changes import ChangeIndex, StateChange, StateDiff
from ...model.entities import EntityId
from ...model.events import Event, EventSource, SourceRole
from ...model.snapshot import SaveSnapshot
from ..common import EventBuilder, Lookup, Side, primary
from .nation_assets import (
    ARMY_FIELDS,
    BOOST,
    GDP,
    MISSION_CONTROL,
    MISSION_CONTROL_METRIC,
    RANKED_METRICS,
    STRENGTH,
    Standing,
    refs,
    standings,
)

RANK_CHANGED = "nation.rank_changed"
RANKED_PLACES = 20
"""Places beyond this on both sides are not reported."""

_NATION_INPUTS: Mapping[str, tuple[str, ...]] = {
    GDP: (GDP, "regions"),
    STRENGTH: ("militaryTechLevel", "unrest", "numNuclearWeapons", "armies", "regions"),
    "boost": ("regions",),
    MISSION_CONTROL_METRIC: ("regions",),
}
_REGION_INPUTS: Mapping[str, tuple[str, ...]] = {
    GDP: (),
    STRENGTH: ("leadOccupier", "occupations"),
    "boost": (BOOST,),
    MISSION_CONTROL_METRIC: (MISSION_CONTROL,),
}
_ARMY_INPUTS: Mapping[str, tuple[str, ...]] = {STRENGTH: ARMY_FIELDS}


class NationRankAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        build = EventBuilder(before, after, lookup)
        earlier, later = standings(before, lookup, Side.BEFORE), standings(after, lookup, Side.AFTER)
        events: list[Event] = []
        for name in RANKED_METRICS:
            old, new = earlier[name], later[name]
            for nation in sorted(old.keys() | new.keys(), key=lambda nation: nation.sort_key):
                was, now = old.get(nation), new.get(nation)
                before_rank, after_rank = _rank(was), _rank(now)
                if before_rank == after_rank or not _listed(before_rank, after_rank):
                    continue
                event = _rank_changed(nation, name, was, now, _reversed(nation, old, new), index, lookup, build)
                if event is not None:
                    events.append(event)
        return events


def _rank(standing: Standing | None) -> int | None:
    return standing.rank if standing is not None else None


def _listed(*ranks: int | None) -> bool:
    return any(rank is not None and rank <= RANKED_PLACES for rank in ranks)


def _reversed(nation: EntityId, old: Mapping[EntityId, Standing], new: Mapping[EntityId, Standing]) -> list[EntityId]:
    """The nations ranked on both sides whose order against ``nation`` reversed."""
    if nation not in old or nation not in new:
        return []
    ahead_before = {other for other, standing in old.items() if standing.rank < old[nation].rank}
    ahead_after = {other for other, standing in new.items() if standing.rank < new[nation].rank}
    both = old.keys() & new.keys()
    return sorted((ahead_before ^ ahead_after) & both, key=lambda other: other.sort_key)


def _inputs(nation: EntityId, name: str, index: ChangeIndex, lookup: Lookup) -> list[StateChange]:
    changes = [change for field in _NATION_INPUTS[name] if (change := index.field(nation, field)) is not None]
    regions: set[EntityId] = set()
    armies: set[EntityId] = set()
    for side in (Side.BEFORE, Side.AFTER):
        state = lookup.state(nation, side)
        if state is None:
            continue
        regions.update(refs(state.get("regions")) or ())
        armies.update(refs(state.get("armies")) or ())
    changes.extend(_changes(regions, _REGION_INPUTS[name], index))
    changes.extend(_changes(armies, _ARMY_INPUTS.get(name, ()), index))
    return changes


def _changes(entities: Iterable[EntityId], names: tuple[str, ...], index: ChangeIndex) -> list[StateChange]:
    return [
        change
        for entity in sorted(entities, key=lambda entity: entity.sort_key)
        for name in names
        if (change := index.field(entity, name)) is not None
    ]


def _rank_changed(
    nation: EntityId,
    name: str,
    was: Standing | None,
    now: Standing | None,
    reversed_against: list[EntityId],
    index: ChangeIndex,
    lookup: Lookup,
    build: EventBuilder,
) -> Event | None:
    own = _inputs(nation, name, index, lookup)
    others = [change for other in reversed_against for change in _inputs(other, name, index, lookup)]
    if not own and not others:
        return None
    # Without a change of its own, the nation's place moved only because the others' values did.
    sources = [primary(change) for change in own or others]
    if own:
        sources.extend(EventSource(change, SourceRole.CORROBORATING) for change in others)
    return build.event(
        RANK_CHANGED,
        id_parts=(nation, name),
        sources=sources,
        entities=(lookup.ref(nation),),
        attributes=(
            ("metric", name),
            ("before_rank", _rank(was)),
            ("after_rank", _rank(now)),
            ("before", was.value if was is not None else None),
            ("after", now.value if now is not None else None),
        ),
    )
