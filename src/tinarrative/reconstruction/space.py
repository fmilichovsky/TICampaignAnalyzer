"""Explicit reconstruction rules: space developments read from hab presence, destruction logs, kills and battles.

The space analyzers keep their wording rule (a hab disappears, a log entry is recorded); only the rules here name
a destruction, a first presence or a battle outcome. Evidence is cited as ``reconstruction.common`` describes.

The evidence is the investigation of 2026-10-14 recorded in ``docs/game-data-notes/higher-level-event-sources.md``
(eight private saves of two campaigns, structure and counts only), re-checked on 2026-10-18. A hab's
``barycenter`` is the body it sits on or orbits (the hab site's ``parentBody`` for 196 of 196 bases, the orbit's
``barycenter`` for 73 of 73 stations). Every ``HabDestructionLog`` entry added in an interval matched at least one
hab gone from the later save by owning faction, hab type and body, often two or three. One ``LogHabDestroyed``
notification named the vanished hab with the entry's date to the millisecond. Faction ``Kills`` lists grew by up
to 36 names in an interval in which the victim's destruction log gained 9 entries and 10 of its habs vanished.

Rules:

- ``faction.first_hab_on_body``: one per faction and body where ``hab.appeared`` events put habs of a faction
  that held none there in the earlier snapshot; high. A new ``First*Base*`` global milestone of the faction is
  cited when no faction had a hab on the body before and it is the faction's only such body in the interval
  (milestone labels name places, not body IDs).
- ``hab.destroyed``: a ``hab.disappeared`` joined to the ``faction.hab_destruction_recorded`` entries of the same
  faction, hab type and body. A ``LogHabDestroyed`` notification naming the hab and dated like one entry pins the
  pair. One entry for one hab, or a pinned pair, is high and dated by the entry; several candidates are medium
  (``ambiguous``), fewer entries than vanished habs low.
- ``faction.battle_outcome``: per killer and victim, ``Kills`` growth against the victim together with a loss of
  the victim in the interval (a vanished hab or fleet, or a destruction entry naming the killer); medium, high
  with a combat-log entry won by the killer, or with a ``LogSpaceBattleTakesPlace`` notification about a fleet of
  either side unless the combat log has the victim winning (the notification says a battle took place, not who
  won it). A faction's kills keyed by itself (observed, unexplained) are not a battle.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from ..analyzers.campaign.global_values import MILESTONE_RECORDED
from ..analyzers.campaign.notifications import PREFIX as NOTIFICATION_PREFIX
from ..analyzers.common import ChangeIndex, EventBuilder, Lookup, Side
from ..analyzers.space.combat import COMBAT_RECORDED, side_factions
from ..analyzers.space.fleets import DISAPPEARED as FLEET_DISAPPEARED
from ..analyzers.space.habs import APPEARED as HAB_APPEARED
from ..analyzers.space.habs import DESTRUCTION_RECORDED
from ..analyzers.space.habs import DISAPPEARED as HAB_DISAPPEARED
from ..model.changes import ChangeKind, RecordsDetail, StateDiff
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import Confidence, Event, EventSource, SourceRole
from ..model.records import KeyedEntry
from ..model.snapshot import SaveSnapshot
from ..model.values import Observed
from .common import ObjectiveIndex, Support, inferred

FIRST_HAB_ON_BODY = "faction.first_hab_on_body"
HAB_DESTROYED = "hab.destroyed"
BATTLE_OUTCOME = "faction.battle_outcome"
RULE_TYPES = (FIRST_HAB_ON_BODY, HAB_DESTROYED, BATTLE_OUTCOME)

HAB_DESTROYED_NOTIFICATION = NOTIFICATION_PREFIX + "LogHabDestroyed"
BATTLE_NOTIFICATION = NOTIFICATION_PREFIX + "LogSpaceBattleTakesPlace"
KILLS_FIELD = "Kills"
"""``TIFactionState.Kills``: victim faction -> display names of destroyed assets (never copied, only counted)."""
MILESTONE_PREFIX = "First"
MILESTONE_BASE = "Base"
"""Observed first-base labels: ``FirstBaseOnLuna``, ``FirstBaseOnMars``, ``FirstAsteroidBase``,
``FirstMercuryBase``, ``FirstKuiperBeltObjectBase``, ``FirstJupiterSystemBase``, ``FirstUranusSystemBase``."""

DestructionKey = tuple[EntityId, str, EntityId]
"""Owning faction, hab type and body: what a destruction log entry and a vanished hab share."""


class SpaceContext:
    """The interval's objective events indexed for the space rules, with the diff and snapshot lookups."""

    def __init__(self, events: Iterable[Event], before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> None:
        self.objective = ObjectiveIndex(events)
        self.index = ChangeIndex(diff)
        self.lookup = Lookup(before, after)
        self.build = EventBuilder(before, after)
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
    return [*_first_habs(context), *_destroyed_habs(context), *_battle_outcomes(context)]


def _subject(event: Event) -> EntityRef:
    return event.entities[0]


# --- faction.first_hab_on_body ---------------------------------------------------------------------------------


def _first_habs(context: SpaceContext) -> list[Event]:
    held: set[tuple[EntityId, EntityId]] = set()
    occupied: set[EntityId] = set()
    for hab in context.before.habs:
        owner, place = hab.get("faction"), hab.get("barycenter")
        if isinstance(place, EntityRef):
            occupied.add(place.entity_id)
            if isinstance(owner, EntityRef):
                held.add((owner.entity_id, place.entity_id))

    groups: dict[tuple[EntityId, EntityId], list[Event]] = defaultdict(list)
    bodies: dict[EntityId, EntityRef] = {}
    for event in context.of_type(HAB_APPEARED):
        hab_id = _subject(event).entity_id
        faction = context.faction_of(hab_id, Side.AFTER)
        body = context.lookup.ref_field(hab_id, "barycenter", Side.AFTER)
        if faction is None or body is None or (faction, body.entity_id) in held:
            continue
        groups[(faction, body.entity_id)].append(event)
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
    for (faction, body_id), appeared in sorted(
        groups.items(), key=lambda item: (item[0][0].sort_key, item[0][1].sort_key)
    ):
        overall = body_id not in occupied
        cited = tuple(milestones[faction]) if overall and firsts_overall[faction] == 1 else ()
        habs = tuple(
            _subject(event) for event in sorted(appeared, key=lambda event: _subject(event).entity_id.sort_key)
        )
        body = bodies[body_id]
        inferred_events.append(
            inferred(
                context.build,
                FIRST_HAB_ON_BODY,
                id_parts=(faction, body_id),
                primary=appeared,
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
    if event.event_type == HAB_DISAPPEARED:
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
    for event in context.of_type(HAB_DISAPPEARED):
        key = _destruction_key(context, event)
        if key is not None:
            groups[key].habs.append(event)
    for event in context.of_type(DESTRUCTION_RECORDED):
        key = _destruction_key(context, event)
        if key is not None and key in groups:
            groups[key].entries.append(event)
    notifications: dict[EntityId, list[Event]] = defaultdict(list)
    for event in context.of_type(HAB_DESTROYED_NOTIFICATION):
        subject = event.attribute("subject")
        if isinstance(subject, EntityRef):
            notifications[subject.entity_id].append(event)

    inferred_events: list[Event] = []
    for key, group in groups.items():
        if not group.entries:
            continue  # nothing records a destruction: the hab stays ``hab.disappeared``
        habs = sorted(group.habs, key=lambda event: _subject(event).entity_id.sort_key)
        entries = sorted(group.entries, key=lambda event: event.id)
        unpinned: list[Event] = []
        for hab in habs:
            pinned = _pin(hab, entries, notifications[_subject(hab).entity_id])
            if pinned is None:
                unpinned.append(hab)
                continue
            entry, notification = pinned
            entries.remove(entry)
            inferred_events.append(_destroyed(context, key, hab, entry, notification))
        if not entries:
            continue
        if len(unpinned) == 1 and len(entries) == 1:
            inferred_events.append(_destroyed(context, key, unpinned[0], entries[0], None))
            continue
        for hab in unpinned:
            inferred_events.append(_ambiguous_destroyed(context, key, hab, entries, len(unpinned)))
    return inferred_events


def _pin(hab: Event, entries: Sequence[Event], notifications: Sequence[Event]) -> tuple[Event, Event] | None:
    """The entry dated like a ``LogHabDestroyed`` notification naming ``hab``, with that notification."""
    for notification in sorted(notifications, key=lambda event: event.id):
        for entry in entries:
            if isinstance(notification.date, str) and entry.attribute("recorded_on") == notification.date:
                return entry, notification
    return None


def _destroyed(
    context: SpaceContext, key: DestructionKey, hab: Event, entry: Event, notification: Event | None
) -> Event:
    faction, hab_type, body_id = key
    destroyer = entry.attribute("destroyer")
    body = entry.attribute("space_body")
    signals = ("destruction_log", "notification") if notification is not None else ("destruction_log",)
    return inferred(
        context.build,
        HAB_DESTROYED,
        id_parts=(_subject(hab).entity_id,),
        primary=(hab,),
        support=Support(events=(entry,) if notification is None else (entry, notification)),
        entities=(_subject(hab), context.ref(faction), _ref(body), _ref(destroyer)),
        attributes=(
            ("hab_type", hab_type),
            ("body", body),
            ("destroyer", destroyer),
            ("recorded_on", entry.attribute("recorded_on")),
            ("signals", signals),
            ("ambiguous", False),
        ),
        confidence=Confidence.LOW if entry.confidence is Confidence.LOW else Confidence.HIGH,
        recorded_on=entry.attribute("recorded_on"),
    )


def _ambiguous_destroyed(
    context: SpaceContext, key: DestructionKey, hab: Event, entries: Sequence[Event], vanished: int
) -> Event:
    """A hab one of several entries may record: medium when the entries cover every vanished hab, low otherwise."""
    faction, hab_type, body_id = key
    destroyers = _unique_refs(entry.attribute("destroyer") for entry in entries)
    body = entries[0].attribute("space_body")
    dates = tuple(sorted(str(entry.attribute("recorded_on")) for entry in entries))
    return inferred(
        context.build,
        HAB_DESTROYED,
        id_parts=(_subject(hab).entity_id,),
        primary=(hab,),
        support=Support(events=tuple(entries)),
        entities=(_subject(hab), context.ref(faction), _ref(body), *destroyers),
        attributes=(
            ("hab_type", hab_type),
            ("body", body),
            ("destroyers", destroyers),
            ("recorded_dates", dates),
            ("candidates", len(entries)),
            ("vanished", vanished),
            ("signals", ("destruction_log",)),
            ("ambiguous", True),
        ),
        confidence=Confidence.MEDIUM if len(entries) >= vanished else Confidence.LOW,
    )


# --- faction.battle_outcome -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Kills:
    """Growth of one killer's ``Kills`` list against one victim, with the citation of that entry."""

    killer: EntityId
    victim: EntityRef
    count: int
    source: EventSource


def _kills(context: SpaceContext) -> list[_Kills]:
    found: list[_Kills] = []
    for change in context.index.fields(EntityDomain.FACTION, KILLS_FIELD):
        if change.kind is not ChangeKind.RECORDS or not isinstance(change.detail, RecordsDetail):
            continue
        killer = change.entity_id
        assert killer is not None
        record_set = context.lookup.record_set(killer, KILLS_FIELD, Side.AFTER)
        grown: list[tuple[KeyedEntry, int]] = [
            (entry, len(entry.value))
            for entry in change.detail.added
            if isinstance(entry, KeyedEntry) and isinstance(entry.value, tuple)
        ]
        for old, new in change.detail.changed:
            if isinstance(old, KeyedEntry) and isinstance(new, KeyedEntry):
                if isinstance(old.value, tuple) and isinstance(new.value, tuple):
                    grown.append((new, len(new.value) - len(old.value)))
        for entry, count in grown:
            victim = entry.key
            if count <= 0 or not isinstance(victim, EntityRef) or victim.entity_id == killer:
                continue
            location = record_set.entry_location(entry) if record_set is not None else None
            found.append(_Kills(killer, victim, count, EventSource(change, SourceRole.PRIMARY, victim, location)))
    return found


def _battle_outcomes(context: SpaceContext) -> list[Event]:
    hab_losses = _losses_by_faction(context, HAB_DISAPPEARED)
    fleet_losses = _losses_by_faction(context, FLEET_DISAPPEARED)
    destructions = context.of_type(DESTRUCTION_RECORDED)
    combats = context.of_type(COMBAT_RECORDED)
    battles = context.of_type(BATTLE_NOTIFICATION)

    inferred_events: list[Event] = []
    for kills in sorted(_kills(context), key=lambda item: (item.killer.sort_key, item.victim.entity_id.sort_key)):
        killer, victim = kills.killer, kills.victim.entity_id
        habs = hab_losses.get(victim, ())
        fleets = fleet_losses.get(victim, ())
        entries = tuple(
            event
            for event in destructions
            if event.sources[0].change.entity_id == victim and _is(event.attribute("destroyer"), killer)
        )
        if not (habs or fleets or entries):
            continue  # kills alone may be councilors or modules; no loss to tie them to
        pair = {killer, victim}
        fought = [
            event for event in combats if pair <= {ref.entity_id for ref in side_factions(event.attribute("sides"))}
        ]
        won = tuple(event for event in fought if _is(event.attribute("winner"), killer))
        lost = tuple(event for event in fought if _is(event.attribute("winner"), victim))
        notified = tuple(event for event in battles if _fleet_faction(context, event.attribute("subject")) & pair)
        signals = tuple(
            name
            for name, present in (
                ("kills", True),
                ("hab_losses", habs),
                ("fleet_losses", fleets),
                ("destruction_log", entries),
                ("combat_log", won),
                ("battle_notification", notified),
            )
            if present
        )
        inferred_events.append(
            inferred(
                context.build,
                BATTLE_OUTCOME,
                id_parts=(killer, victim),
                primary=(*habs, *fleets),
                primary_changes=(kills.source,),
                support=Support(events=entries + won + lost + notified),
                entities=(context.ref(killer), kills.victim),
                attributes=(
                    ("victim", kills.victim),
                    ("kill_count", kills.count),
                    ("habs_lost", len(habs)),
                    ("fleets_lost", len(fleets)),
                    ("destruction_entries", len(entries)),
                    ("combats_won", len(won)),
                    ("combats_lost", len(lost)),
                    ("battle_dates", tuple(sorted(str(event.date) for event in notified))),
                    ("signals", signals),
                ),
                confidence=Confidence.HIGH if won or (notified and not lost) else Confidence.MEDIUM,
            )
        )
    return inferred_events


def _losses_by_faction(context: SpaceContext, event_type: str) -> dict[EntityId, tuple[Event, ...]]:
    """The ``*.disappeared`` events of ``event_type`` by the faction owning the entity in the earlier snapshot."""
    losses: dict[EntityId, list[Event]] = defaultdict(list)
    for event in context.of_type(event_type):
        faction = context.faction_of(_subject(event).entity_id, Side.BEFORE)
        if faction is not None:
            losses[faction].append(event)
    return {faction: tuple(events) for faction, events in losses.items()}


def _fleet_faction(context: SpaceContext, subject: Observed) -> set[EntityId]:
    """The factions owning a fleet in either snapshot; empty for any other subject."""
    if not isinstance(subject, EntityRef) or subject.entity_id.domain is not EntityDomain.FLEET:
        return set()
    owners = (context.faction_of(subject.entity_id, side) for side in (Side.BEFORE, Side.AFTER))
    return {owner for owner in owners if owner is not None}


def _is(value: Observed, entity_id: EntityId) -> bool:
    return isinstance(value, EntityRef) and value.entity_id == entity_id


def _ref(value: Observed) -> EntityRef | None:
    return value if isinstance(value, EntityRef) else None


def _unique_refs(values: Iterable[Observed]) -> tuple[EntityRef, ...]:
    refs = {value.entity_id: value for value in values if isinstance(value, EntityRef)}
    return tuple(refs[key] for key in sorted(refs, key=lambda entity_id: entity_id.sort_key))
