"""The game's own notification log (``TINotificationQueueState.notificationSummaryQueue``).

Each added entry is an objective ``notification.<templateName>`` event dated by its own ``dateTime``. The log is
player-centric and pruned (``domain-field-map.md``), so an absent entry proves nothing and a removed one is reported
literally, never assumed pruned. The summary text is campaign content: carried as an attribute, never rendered or
logged.
"""

from __future__ import annotations

from ...kinds import campaign
from ...kinds.campaign import NOTIFICATION_PREFIX, entry_kind
from ...model.changes import ChangeKind, RecordsDetail, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId, EntityRef
from ...model.events import Confidence, Event, EventSource, SourceRole
from ...model.records import NotificationEntry, RecordSet
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed
from ..common import (
    EventBuilder,
    Lookup,
    Side,
    classify,
    confidence_for,
    is_unresolved,
    primary,
    transition_attributes,
)

DOMAIN = EntityDomain.NOTIFICATION_QUEUE
LOG = "notificationSummaryQueue"

PREFIX = NOTIFICATION_PREFIX


class NotificationAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        build = EventBuilder(before, after, lookup)
        events: list[Event] = []

        for change in index.presence(DOMAIN):
            events.append(_presence(change, lookup, build))
        for change in diff.changes:
            if change.domain != DOMAIN.value or change.field is None or change.entity_id is None:
                continue
            if change.field == LOG and change.kind is ChangeKind.RECORDS and isinstance(change.detail, RecordsDetail):
                events.extend(_log_events(change, change.detail, lookup, build))
            else:
                event = _value_changed(change, lookup, build)
                if event is not None:
                    events.append(event)
        return events


def _owner(change: StateChange, lookup: Lookup) -> tuple[EntityId, EntityRef | None]:
    owner_id = change.entity_id
    assert owner_id is not None
    return owner_id, lookup.ref(owner_id)


def _source(change: StateChange, record_set: RecordSet | None, entry: NotificationEntry) -> EventSource:
    location = record_set.entry_location(entry) if record_set is not None else None
    member = entry.template if isinstance(entry.template, str) else None
    return EventSource(change, SourceRole.PRIMARY, member, location)


def _entry_attributes(entry: NotificationEntry) -> tuple[tuple[str, Observed], ...]:
    return (
        ("template", entry.template),
        ("summary", entry.summary),
        ("outcome", entry.outcome),
        ("subject", entry.subject),
        ("alien_related", entry.alien_related),
        ("news_feed_factions", entry.news_feed_factions),
        ("summary_log_factions", entry.summary_log_factions),
    )


def _confidence(entry: NotificationEntry) -> Confidence:
    return Confidence.LOW if is_unresolved(entry.subject) else Confidence.HIGH


def _log_events(change: StateChange, detail: RecordsDetail, lookup: Lookup, build: EventBuilder) -> list[Event]:
    """One event per entry added (dated by the entry), removed or changed (both dated by the interval)."""
    owner_id, owner = _owner(change, lookup)
    after_set = lookup.record_set(owner_id, LOG, Side.AFTER)
    before_set = lookup.record_set(owner_id, LOG, Side.BEFORE)
    events: list[Event] = []
    for entry in detail.added:
        if not isinstance(entry, NotificationEntry):
            continue
        events.append(
            build.event(
                entry_kind(entry.template),
                id_parts=(owner_id, entry.index),  # the index tells identical entries apart
                sources=(_source(change, after_set, entry),),
                entities=(owner, lookup.resolve(entry.subject)),
                attributes=_entry_attributes(entry),
                confidence=_confidence(entry),
                recorded_on=entry.date,
            )
        )
    for entry in detail.removed:
        if not isinstance(entry, NotificationEntry):
            continue
        events.append(
            build.event(
                campaign.ENTRY_REMOVED,
                id_parts=(owner_id, entry.index),
                sources=(_source(change, before_set, entry),),
                entities=(owner, lookup.resolve(entry.subject)),
                attributes=(*_entry_attributes(entry), ("logged_on", entry.date)),
                confidence=_confidence(entry),
            )
        )
    for old, new in detail.changed:
        if not isinstance(old, NotificationEntry) or not isinstance(new, NotificationEntry):
            continue
        events.append(
            build.event(
                campaign.ENTRY_CHANGED,
                id_parts=(owner_id, new.index),
                sources=(_source(change, after_set, new),),
                entities=(owner, lookup.resolve(old.subject), lookup.resolve(new.subject)),
                attributes=(
                    *_entry_attributes(new),
                    ("logged_on", new.date),
                    ("before_subject", old.subject),
                    ("before_outcome", old.outcome),
                    ("before_alien_related", old.alien_related),
                    ("before_news_feed_factions", old.news_feed_factions),
                    ("before_summary_log_factions", old.summary_log_factions),
                ),
                confidence=_confidence(new),
            )
        )
    return events


def _presence(change: StateChange, lookup: Lookup, build: EventBuilder) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    owner_id, owner = _owner(change, lookup)
    side = Side.AFTER if appeared else Side.BEFORE
    return build.event(
        campaign.QUEUE_APPEARED if appeared else campaign.QUEUE_DISAPPEARED,
        id_parts=(owner_id,),
        sources=(primary(change),),
        entities=(owner,),
        attributes=(("side", side.value),),
    )


def _value_changed(change: StateChange, lookup: Lookup, build: EventBuilder) -> Event | None:
    """Any other field of the singleton, literally; ``None`` on a schema gap."""
    transition = classify(change.before, change.after)
    if transition is None:
        return None
    owner_id, owner = _owner(change, lookup)
    return build.event(
        campaign.QUEUE_VALUE_CHANGED,
        id_parts=(owner_id, change.field),
        sources=(primary(change),),
        entities=(owner,),
        attributes=(("field", change.field), *transition_attributes(change, transition)),
        confidence=confidence_for(transition),
    )
