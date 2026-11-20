"""A faction's literal combat log (``TIFactionState.CombatLogs``): one event per entry added or removed.

An entry is dated by its record when it carries a date, else by the interval. The same combat may be logged by
several factions, one event each; matching them is reconstruction. Removed entries are reported literally, never
assumed pruned. Ship design names are campaign content and are not decoded. ``side_dry_mass`` prices each side.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from functools import cache

from ...kinds.space import FACTION_COMBAT_ENTRY_REMOVED, FACTION_COMBAT_RECORDED
from ...model.changes import ChangeKind, RecordsDetail, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId, EntityRef
from ...model.events import Confidence, Event, EventSource, SourceRole
from ...model.records import CombatEntry, RecordSet
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed, Unknown
from ..common import EventBuilder, Lookup, Side, is_unresolved
from .masses import ShipMasses, ship_masses

LOG_FIELD = "CombatLogs"
COMBAT_RECORDED = FACTION_COMBAT_RECORDED.event_type
ENTRY_REMOVED = FACTION_COMBAT_ENTRY_REMOVED.event_type


class CombatAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        build = EventBuilder(before, after, lookup)
        events: list[Event] = []
        masses = cache(lambda: ship_masses(before))  # the earlier snapshot, priced once and only if a combat needs it
        for change in index.fields(EntityDomain.FACTION, LOG_FIELD):
            events.extend(_log_events(change, lookup, build, masses))
        return events


def side_factions(sides: Observed) -> tuple[EntityRef, ...]:
    """The faction of each side, in serialized order; none when the sides are unknown."""
    if not isinstance(sides, tuple):
        return ()
    return tuple(side[0] for side in sides if isinstance(side, tuple) and isinstance(side[0], EntityRef))


def attack_count(attacks: Observed) -> Observed:
    """The number of recorded attacks; the unknown or unexpected value itself otherwise."""
    return len(attacks) if isinstance(attacks, tuple) else attacks


def side_dry_mass(entry: CombatEntry, masses: ShipMasses) -> Observed:
    """Each side's dry mass (kg) in side order; ``Unknown`` when the record does not say enough to price it: sides or
    ships that do not read, more than two sides, or a single side with a ``HabFaction`` (it does not name the hab).

    A ship whose design and hull class have no live ship counts nothing.
    """
    if not isinstance(entry.designs, tuple) or not 1 <= len(entry.designs) <= 2:
        return Unknown()
    if len(entry.designs) == 1 and isinstance(entry.hab_faction, EntityRef):
        return Unknown()
    totals: list[float] = []
    for side in entry.designs:
        if not (isinstance(side, tuple) and isinstance(side[0], EntityRef) and isinstance(side[1], tuple)):
            return Unknown()
        parts: list[float] = []
        for ship in side[1]:
            if not (
                isinstance(ship, tuple)
                and len(ship) == 3
                and isinstance(ship[0], str)
                and isinstance(ship[1], str)
                and isinstance(ship[2], int)
            ):
                continue  # not a design triple: it prices nothing
            parts.append((masses.of(side[0].entity_id, ship[0], ship[1]) or 0.0) * ship[2])
        totals.append(math.fsum(parts))
    return tuple(totals)


def _attributes(entry: CombatEntry, masses: ShipMasses | None = None) -> tuple[tuple[str, Observed], ...]:
    priced: tuple[tuple[str, Observed], ...] = (
        (("side_dry_mass", side_dry_mass(entry, masses)),) if masses is not None else ()
    )
    return (
        ("sides", entry.sides),
        ("winner", entry.winner),
        ("hab_faction", entry.hab_faction),
        ("attack_count", attack_count(entry.attacks)),
        ("surprising", entry.surprising),
        ("recorded_on", entry.date),
        *priced,
    )


def _confidence(entry: CombatEntry) -> Confidence:
    members = (entry.sides, entry.winner, entry.hab_faction)
    return Confidence.LOW if any(is_unresolved(value) for value in members) else Confidence.HIGH


def _entities(owner: EntityRef | None, entry: CombatEntry, lookup: Lookup) -> tuple[EntityRef, ...]:
    """The owning faction, the sides, the winner and the hab faction, each once, in that order."""
    sides = tuple(lookup.resolve(faction) for faction in side_factions(entry.sides))
    refs = (owner, *sides, lookup.resolve(entry.winner), lookup.resolve(entry.hab_faction))
    unique: dict[EntityId, EntityRef] = {}
    for ref in refs:
        if ref is not None:
            unique.setdefault(ref.entity_id, ref)
    return tuple(unique.values())


def _source(change: StateChange, record_set: RecordSet | None, entry: CombatEntry) -> EventSource:
    location = record_set.entry_location(entry) if record_set is not None else None
    return EventSource(change, SourceRole.PRIMARY, None, location)


def _log_events(
    change: StateChange, lookup: Lookup, build: EventBuilder, masses: Callable[[], ShipMasses]
) -> list[Event]:
    """One event per entry added (dated by the entry, else the interval) and per entry removed (interval)."""
    if change.kind is not ChangeKind.RECORDS or not isinstance(change.detail, RecordsDetail):
        return []
    if change.entity_id is None:
        return []
    faction_id: EntityId = change.entity_id
    after_set = lookup.record_set(faction_id, LOG_FIELD, Side.AFTER)
    before_set = lookup.record_set(faction_id, LOG_FIELD, Side.BEFORE)
    any_set = after_set or before_set
    owner = lookup.ref(faction_id) or (any_set.owner if any_set is not None else None)
    events: list[Event] = []
    for entry in change.detail.added:
        if not isinstance(entry, CombatEntry):
            continue  # the diff keeps it visible
        events.append(
            build.event(
                FACTION_COMBAT_RECORDED,
                id_parts=(faction_id, entry.index),  # the index tells identical entries apart
                sources=(_source(change, after_set, entry),),
                entities=_entities(owner, entry, lookup),
                attributes=_attributes(entry, masses()),
                confidence=_confidence(entry),
                recorded_on=entry.date,
            )
        )
    for entry in change.detail.removed:
        if not isinstance(entry, CombatEntry):
            continue
        events.append(
            build.event(
                FACTION_COMBAT_ENTRY_REMOVED,
                id_parts=(faction_id, entry.index),
                sources=(_source(change, before_set, entry),),
                entities=_entities(owner, entry, lookup),
                attributes=_attributes(entry),
                confidence=_confidence(entry),
            )
        )
    return events
