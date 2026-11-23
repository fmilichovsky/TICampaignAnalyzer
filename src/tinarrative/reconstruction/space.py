"""Reconstruction rules for space: hab established, first hab on a body, hab destroyed, space losses.

The space analyzers only report presence and log entries; these rules name the narrative event. The joins and their
evidence are in ``docs/game-data-notes/higher-level-event-sources.md`` (space joins, hab lifecycle).

- ``hab.established``: a hab's core completed (a hab appears at launch, long before); high, dated by the core's
  completion when that falls inside the interval.
- ``faction.first_hab_on_body``: habs of a faction are established on a body where it had no working hab; high. A
  ``First*Base*`` milestone is cited only when it is unambiguous (labels name places, not body IDs).
- ``hab.destroyed``: a vanished hab joined to destruction log entries by faction, hab type and body; high when
  one entry matches, else medium (``ambiguous``) or low; a ``LogHabDestroyed`` dated like an entry is only cited.
- ``faction.space_losses``: the victim's vanished ships whose names its destroyer's ``Kills`` gained, and the habs
  of non-ambiguous ``hab.destroyed``; high (ADR-0023).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from ..analyzers.campaign.global_values import MILESTONE_RECORDED
from ..analyzers.campaign.notifications import PREFIX as NOTIFICATION_PREFIX
from ..analyzers.common import EventBuilder, Lookup, Side
from ..kinds import space
from ..model.changes import ChangeKind, RecordsDetail, StateDiff
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import Confidence, Event, EventSource, SourceRole
from ..model.records import KeyedEntry
from ..model.snapshot import SaveSnapshot
from ..model.values import Observed
from .common import ObjectiveIndex, Support, inferred

HAB_ESTABLISHED = space.HAB_ESTABLISHED.event_type
FIRST_HAB_ON_BODY = space.FACTION_FIRST_HAB_ON_BODY.event_type
HAB_DESTROYED = space.HAB_DESTROYED.event_type
SPACE_LOSSES = space.FACTION_SPACE_LOSSES.event_type
RULE_TYPES = (HAB_ESTABLISHED, FIRST_HAB_ON_BODY, HAB_DESTROYED, SPACE_LOSSES)
__all__ = ["FIRST_HAB_ON_BODY", "HAB_DESTROYED", "HAB_ESTABLISHED", "RULE_TYPES", "SPACE_LOSSES", "space_events"]

CORE_COMPLETED = "anyCoreCompleted"
CORE_DATES = ("corePriorCompletionDate", "coreCompletionDate")
"""Candidate completion dates; the prior one is the first core's when an upgrade began in the same interval."""

HAB_DESTROYED_NOTIFICATION = NOTIFICATION_PREFIX + "LogHabDestroyed"
KILLS_FIELD = "Kills"
"""``TIFactionState.Kills``: victim faction -> display names of destroyed assets (compared, never copied)."""
MILESTONE_PREFIX = "First"
MILESTONE_BASE = "Base"
"""First-base milestone labels start with ``First`` and contain ``Base`` (``FirstBaseOnLuna``, ``FirstMercuryBase``)."""

DestructionKey = tuple[EntityId, str, EntityId]
"""Owning faction, hab type and body: what a destruction log entry and a vanished hab share."""


class SpaceContext:
    """The interval's objective events indexed for the space rules, with the diff and snapshot lookups."""

    def __init__(self, events: Iterable[Event], before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> None:
        self.objective = ObjectiveIndex(events)
        self.index = diff.index
        self.lookup = Lookup(before, after)
        self.build = EventBuilder(before, after, self.lookup)
        self.before = before

    def of_type(self, event_type: str) -> tuple[Event, ...]:
        return self.objective.of_type(event_type)

    def faction_of(self, entity_id: EntityId, side: Side) -> EntityId | None:
        faction = self.lookup.ref_field(entity_id, "faction", side)
        return faction.entity_id if faction is not None else None

    def ref(self, entity_id: EntityId, fallback: EntityRef | None = None) -> EntityRef | None:
        return self.lookup.ref(entity_id) or fallback


def space_events(events: Iterable[Event], before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
    """Every space inference of one interval (unsorted)."""
    context = SpaceContext(events, before, after, diff)
    foundings = _foundings(context)
    destroyed = _destroyed_habs(context)
    return [
        *(_established(context, founding) for founding in foundings),
        *_first_habs(context, foundings),
        *destroyed,
        *_space_losses(context, destroyed),
    ]


def _subject(event: Event) -> EntityRef:
    return event.entities[0]


# --- hab.established --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Founding:
    """A hab whose core began to work in the interval; ``evidence`` is the objective event both space rules cite."""

    evidence: Event
    date: str | None
    """The core's completion date, or ``None`` when it falls outside the interval."""

    @property
    def hab(self) -> EntityRef:
        return _subject(self.evidence)


def _foundings(context: SpaceContext) -> list[_Founding]:
    """A core completed on a hab seen before, or a hab appeared with a working core (launched and built in one go)."""
    evidence = [
        event
        for event in context.of_type(space.HAB_CORE_COMPLETED_CHANGED.event_type)
        if event.attribute("before") is False and event.attribute("after") is True
    ]
    for event in context.of_type(space.HAB_APPEARED.event_type):
        state = context.lookup.state(_subject(event).entity_id, Side.AFTER)
        if state is not None and state.get(CORE_COMPLETED) is True:
            evidence.append(event)
    return [_Founding(event, _completion_date(context, _subject(event).entity_id)) for event in evidence]


def _established(context: SpaceContext, founding: _Founding) -> Event:
    hab = founding.hab
    faction = context.lookup.ref_field(hab.entity_id, "faction", Side.AFTER)
    body = context.lookup.ref_field(hab.entity_id, "barycenter", Side.AFTER)
    return inferred(
        context.build,
        space.HAB_ESTABLISHED,
        id_parts=(hab.entity_id,),
        primary=(founding.evidence,),
        support=Support(),
        entities=(hab, faction, body),
        attributes=(("faction", faction), ("body", body)),
        confidence=Confidence.HIGH,
        recorded_on=founding.date,
    )


def _completion_date(context: SpaceContext, hab_id: EntityId) -> str | None:
    """The earliest core completion date inside the interval; ``None`` dates the event by the interval."""
    state = context.lookup.state(hab_id, Side.AFTER)
    low, high = context.build.not_before, context.build.observed
    if state is None or not isinstance(high, str):
        return None
    dates = []
    for name in CORE_DATES:
        value = state.get(name)
        if name == "coreCompletionDate" and state.get("coreConstructionCompleted") is not True:
            continue
        if isinstance(value, str) and value <= high and (not isinstance(low, str) or value > low):
            dates.append(value)
    return min(dates, default=None)


# --- faction.first_hab_on_body ---------------------------------------------------------------------------------


def _first_habs(context: SpaceContext, foundings: Sequence[_Founding]) -> list[Event]:
    """Keyed on working habs: a hab still in transit or under construction is no presence."""
    held: set[tuple[EntityId, EntityId]] = set()
    occupied: set[EntityId] = set()
    for hab in context.before.habs:
        owner, place = hab.get("faction"), hab.get("barycenter")
        if isinstance(place, EntityRef) and hab.get(CORE_COMPLETED) is True:
            occupied.add(place.entity_id)
            if isinstance(owner, EntityRef):
                held.add((owner.entity_id, place.entity_id))

    groups: dict[tuple[EntityId, EntityId], list[_Founding]] = defaultdict(list)
    bodies: dict[EntityId, EntityRef] = {}
    for founding in foundings:
        hab_id = founding.hab.entity_id
        faction = context.faction_of(hab_id, Side.AFTER)
        body = context.lookup.ref_field(hab_id, "barycenter", Side.AFTER)
        if faction is None or body is None or (faction, body.entity_id) in held:
            continue
        groups[(faction, body.entity_id)].append(founding)
        bodies[body.entity_id] = body

    firsts_overall: dict[EntityId, int] = defaultdict(int)
    for faction, body_id in groups:
        if body_id not in occupied:
            firsts_overall[faction] += 1
    milestones: dict[EntityId, list[Event]] = defaultdict(list)
    for event in context.of_type(MILESTONE_RECORDED):
        label, faction_ref = event.attribute("milestone"), event.attribute("faction")
        if isinstance(label, str) and label.startswith(MILESTONE_PREFIX) and MILESTONE_BASE in label:
            if isinstance(faction_ref, EntityRef):
                milestones[faction_ref.entity_id].append(event)

    inferred_events: list[Event] = []
    for (faction, body_id), founded in sorted(
        groups.items(), key=lambda item: (item[0][0].sort_key, item[0][1].sort_key)
    ):
        overall = body_id not in occupied
        cited = tuple(milestones[faction]) if overall and firsts_overall[faction] == 1 else ()
        habs = tuple(sorted((founding.hab for founding in founded), key=lambda ref: ref.entity_id.sort_key))
        dates = [founding.date for founding in founded if founding.date is not None]
        first = min(dates) if len(dates) == len(founded) else None  # one hab dated only by the interval: so is this
        body = bodies[body_id]
        inferred_events.append(
            inferred(
                context.build,
                space.FACTION_FIRST_HAB_ON_BODY,
                id_parts=(faction, body_id),
                primary=[founding.evidence for founding in founded],
                support=Support(events=cited),
                entities=(context.ref(faction), body, *habs),
                attributes=(
                    ("body", body),
                    ("habs", habs),
                    ("hab_count", len(habs)),
                    ("first_of_any_faction", overall),
                    ("milestones", tuple(sorted(str(event.attribute("milestone")) for event in cited))),
                ),
                confidence=Confidence.HIGH,
                recorded_on=first,
            )
        )
    return inferred_events


# --- hab.destroyed ----------------------------------------------------------------------------------------------


@dataclass
class _DestructionGroup:
    habs: list[Event] = field(default_factory=list)
    entries: list[Event] = field(default_factory=list)


def _destruction_key(context: SpaceContext, event: Event) -> DestructionKey | None:
    """The key of a vanished hab (read from the earlier snapshot) or of a destruction entry; ``None`` if unknown."""
    if event.event_type == space.HAB_DISAPPEARED.event_type:
        hab_id = _subject(event).entity_id
        faction = context.faction_of(hab_id, Side.BEFORE)
        state = context.lookup.state(hab_id, Side.BEFORE)
        hab_type = state.get("habType") if state is not None else None
        body = context.lookup.ref_field(hab_id, "barycenter", Side.BEFORE)
    else:
        faction = event.sources[0].change.entity_id  # the faction owning the log
        hab_type = event.attribute("hab_type")
        space_body = event.attribute("space_body")
        body = space_body if isinstance(space_body, EntityRef) else None
    if faction is None or not isinstance(hab_type, str) or body is None:
        return None
    return (faction, hab_type, body.entity_id)


def _destroyed_habs(context: SpaceContext) -> list[Event]:
    groups: dict[DestructionKey, _DestructionGroup] = defaultdict(_DestructionGroup)
    for event in context.of_type(space.HAB_DISAPPEARED.event_type):
        key = _destruction_key(context, event)
        if key is not None:
            groups[key].habs.append(event)
    for event in context.of_type(space.FACTION_HAB_DESTRUCTION_RECORDED.event_type):
        key = _destruction_key(context, event)
        if key is not None and key in groups:
            groups[key].entries.append(event)
    notifications: dict[str, list[Event]] = defaultdict(list)
    for event in context.of_type(HAB_DESTROYED_NOTIFICATION):
        if isinstance(event.date, str):
            notifications[event.date].append(event)

    inferred_events: list[Event] = []
    for key, group in groups.items():
        if not group.entries:
            continue  # nothing records a destruction: the hab stays ``hab.disappeared``
        habs = sorted(group.habs, key=lambda event: _subject(event).entity_id.sort_key)
        entries = sorted(group.entries, key=lambda event: event.id)
        notes = _corroborating(entries, notifications)
        if len(habs) == 1 and len(entries) == 1:
            inferred_events.append(_destroyed(context, key, habs[0], entries[0], notes))
            continue
        for hab in habs:
            inferred_events.append(_ambiguous_destroyed(context, key, hab, entries, len(habs), notes))
    return inferred_events


def _corroborating(entries: Sequence[Event], notifications: Mapping[str, Sequence[Event]]) -> tuple[Event, ...]:
    """The ``LogHabDestroyed`` notifications dated like one of ``entries``; cited, never used to pick a hab."""
    dates = {date for entry in entries if isinstance(date := entry.attribute("recorded_on"), str)}
    return tuple(sorted((event for date in dates for event in notifications.get(date, ())), key=lambda e: e.id))


def _signals(notes: Sequence[Event]) -> tuple[str, ...]:
    return ("destruction_log", "notification") if notes else ("destruction_log",)


def _destroyed(context: SpaceContext, key: DestructionKey, hab: Event, entry: Event, notes: Sequence[Event]) -> Event:
    faction, hab_type, body_id = key
    destroyer = entry.attribute("destroyer")
    body = entry.attribute("space_body")
    return inferred(
        context.build,
        space.HAB_DESTROYED,
        id_parts=(_subject(hab).entity_id,),
        primary=(hab,),
        support=Support(events=(entry, *notes)),
        entities=(_subject(hab), context.ref(faction), _named(context, body), _named(context, destroyer)),
        attributes=(
            ("hab_type", hab_type),
            ("body", _named(context, body) or body),
            ("destroyer", _named(context, destroyer) or destroyer),
            ("recorded_on", entry.attribute("recorded_on")),
            ("signals", _signals(notes)),
            ("ambiguous", False),
        ),
        confidence=Confidence.LOW if entry.confidence is Confidence.LOW else Confidence.HIGH,
        recorded_on=entry.attribute("recorded_on"),
    )


def _ambiguous_destroyed(
    context: SpaceContext,
    key: DestructionKey,
    hab: Event,
    entries: Sequence[Event],
    vanished: int,
    notes: Sequence[Event],
) -> Event:
    """A hab one of several entries may record: medium when the entries cover every vanished hab, low otherwise."""
    faction, hab_type, body_id = key
    destroyers = _unique_refs(_named(context, entry.attribute("destroyer")) for entry in entries)
    body = entries[0].attribute("space_body")
    dates = tuple(sorted(str(entry.attribute("recorded_on")) for entry in entries))
    return inferred(
        context.build,
        space.HAB_DESTROYED,
        id_parts=(_subject(hab).entity_id,),
        primary=(hab,),
        support=Support(events=(*entries, *notes)),
        entities=(_subject(hab), context.ref(faction), _named(context, body), *destroyers),
        attributes=(
            ("hab_type", hab_type),
            ("body", _named(context, body) or body),
            ("destroyers", destroyers),
            ("recorded_dates", dates),
            ("candidates", len(entries)),
            ("vanished", vanished),
            ("signals", _signals(notes)),
            ("ambiguous", True),
        ),
        confidence=Confidence.MEDIUM if len(entries) >= vanished else Confidence.LOW,
    )


# --- faction.space_losses ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Gained:
    """What one destroyer's ``Kills`` list gained against one victim in the interval, with the citation."""

    destroyer: EntityId
    victim: EntityRef
    names: Counter[str]
    """Display names by count; compared in memory only, never copied (free text)."""
    source: EventSource


def _gained(context: SpaceContext) -> list[_Gained]:
    found: list[_Gained] = []
    for change in context.index.fields(EntityDomain.FACTION, KILLS_FIELD):
        if change.kind is not ChangeKind.RECORDS or not isinstance(change.detail, RecordsDetail):
            continue
        destroyer = change.entity_id
        assert destroyer is not None
        record_set = context.lookup.record_set(destroyer, KILLS_FIELD, Side.AFTER)
        grown: list[tuple[KeyedEntry, Counter[str]]] = [
            (entry, Counter(_names(entry.value)))
            for entry in change.detail.added
            if isinstance(entry, KeyedEntry) and isinstance(entry.value, tuple)
        ]
        for old, new in change.detail.changed:
            if isinstance(old, KeyedEntry) and isinstance(new, KeyedEntry):
                if isinstance(old.value, tuple) and isinstance(new.value, tuple):
                    grown.append((new, Counter(_names(new.value)) - Counter(_names(old.value))))
        for entry, names in grown:
            victim = entry.key
            if not names or not isinstance(victim, EntityRef) or victim.entity_id == destroyer:
                continue
            location = record_set.entry_location(entry) if record_set is not None else None
            found.append(_Gained(destroyer, victim, names, EventSource(change, SourceRole.PRIMARY, victim, location)))
    return found


def _names(value: tuple[Observed, ...]) -> list[str]:
    return [item for item in value if isinstance(item, str)]


@dataclass
class _Losses:
    """What one destroyer took from one victim: tied ships, tied habs and the ``Kills`` entries that tied the ships."""

    ships: list[Event] = field(default_factory=list)
    habs: list[Event] = field(default_factory=list)
    kills: list[EventSource] = field(default_factory=list)


def _space_losses(context: SpaceContext, destroyed: Sequence[Event]) -> list[Event]:
    pairs: dict[tuple[EntityId, EntityId], _Losses] = defaultdict(_Losses)
    victims: dict[EntityId, EntityRef] = {}

    vanished: dict[tuple[EntityId, str], list[Event]] = defaultdict(list)
    for event in context.of_type(space.SHIP_DISAPPEARED.event_type):
        owner = event.entities[2] if len(event.entities) > 2 else None
        name = _subject(event).name
        if owner is not None and name is not None:
            vanished[(owner.entity_id, name)].append(event)

    gained = _gained(context)
    destroyers: dict[tuple[EntityId, str], set[EntityId]] = defaultdict(set)
    for entry in gained:
        victims[entry.victim.entity_id] = entry.victim
        for name in entry.names:
            destroyers[(entry.victim.entity_id, name)].add(entry.destroyer)
    for entry in gained:
        victim = entry.victim.entity_id
        for name, count in entry.names.items():
            ships = vanished.get((victim, name))
            if not ships or destroyers[(victim, name)] != {entry.destroyer}:
                continue  # nothing vanished under that name, or several destroyers gained it: none is credited
            tied = sorted(ships, key=lambda event: event.id)[:count]
            losses = pairs[(entry.destroyer, victim)]
            losses.ships.extend(tied)
            if entry.source not in losses.kills:
                losses.kills.append(entry.source)

    for hab in destroyed:
        by, owner = hab.attribute("destroyer"), hab.entities[1] if len(hab.entities) > 1 else None
        if hab.attribute("ambiguous") is not False or not isinstance(by, EntityRef) or owner is None:
            continue
        if by.entity_id == owner.entity_id:
            continue  # a faction's own hab is no one's loss to credit, as with self-keyed Kills
        pairs[(by.entity_id, owner.entity_id)].habs.append(hab)
        victims.setdefault(owner.entity_id, owner)

    inferred_events: list[Event] = []
    for (destroyer, victim), losses in sorted(pairs.items(), key=lambda item: tuple(k.sort_key for k in item[0])):
        if not (losses.ships or losses.habs):
            continue
        inferred_events.append(_losses_event(context, destroyer, victims[victim], losses))
    return inferred_events


def _losses_event(context: SpaceContext, destroyer: EntityId, victim: EntityRef, losses: _Losses) -> Event:
    victim_ref = context.lookup.resolve(victim) or victim
    ships = sorted(losses.ships, key=lambda event: _subject(event).entity_id.sort_key)
    ship_refs = tuple(_subject(event) for event in ships)
    hab_events = [
        context.objective.by_id[item]
        for hab in losses.habs
        for item in hab.constituents
        if item in context.objective.by_id
    ]
    disappeared = [event for event in hab_events if event.event_type == space.HAB_DISAPPEARED.event_type]
    entries = [event for event in hab_events if event.event_type != space.HAB_DISAPPEARED.event_type]
    hab_refs = tuple(sorted((_subject(event) for event in disappeared), key=lambda ref: ref.entity_id.sort_key))
    return inferred(
        context.build,
        space.FACTION_SPACE_LOSSES,
        id_parts=(destroyer, victim.entity_id),
        primary=(*ships, *disappeared),
        primary_changes=tuple(losses.kills),
        support=Support(events=tuple(entries)),
        entities=(context.ref(destroyer), victim_ref, *ship_refs, *hab_refs),
        attributes=(
            ("victim", victim_ref),
            ("ships_lost", len(ship_refs)),
            ("habs_lost", len(hab_refs)),
            ("ships", ship_refs),
            ("habs", hab_refs),
        ),
        confidence=Confidence.HIGH,
    )


def _named(context: SpaceContext, value: Observed) -> EntityRef | None:
    """The reference ``value`` carries, with its entity's display name when that entity is normalized."""
    return context.lookup.resolve(value)


def _unique_refs(values: Iterable[Observed]) -> tuple[EntityRef, ...]:
    refs = {value.entity_id: value for value in values if isinstance(value, EntityRef)}
    return tuple(refs[key] for key in sorted(refs, key=lambda entity_id: entity_id.sort_key))
