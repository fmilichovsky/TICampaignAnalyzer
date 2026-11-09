"""The campaign-wide ``TIGlobalValuesState`` singleton: milestones, nuclear strikes, sea-level rise, narrative events.

Any other change, and every removed record entry, falls back to ``campaign.global_value_changed`` so nothing is
dropped; a removed entry is never assumed pruned. ``interstateWars`` belongs to the war analyzer.
"""

from __future__ import annotations

from ...kinds import campaign
from ...model.changes import ChangeKind, RecordsDetail, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId, EntityRef
from ...model.events import Confidence, Event, EventSource, SourceRole
from ...model.records import ItemEntry, KeyedEntry, RecordEntry, RecordSet
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed, Unknown
from ..common import (
    EventBuilder,
    Lookup,
    Side,
    Transition,
    classify,
    confidence_for,
    is_unresolved,
    primary,
    transition_attributes,
    value_transition_event,
)

DOMAIN = EntityDomain.GLOBAL_VALUES

MILESTONE_RECORDED = campaign.MILESTONE_RECORDED.event_type
INTERSTATE_WARS_CHANGED = "campaign.interstate_wars_changed"
"""Emitted by the war analyzer for an ``interstateWars`` member that no war presence explains."""

INTERSTATE_WARS = "interstateWars"
MILESTONES = "globalMilestones"
NUCLEAR_STRIKES = "nuclearStrikes"
ONCE_PER_CAMPAIGN = "triggeredOncePerCampaignEvents"
ONCE_PER_TARGET = "triggeredOncePerTargetEvents"
SEA_LEVEL_RISES = {"globalSeaLevelRise1Triggered": 1, "globalSeaLevelRise2Triggered": 2}
HANDLED_ELSEWHERE = frozenset((INTERSTATE_WARS,))


class GlobalValuesAnalyzer:
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
            if change.field not in HANDLED_ELSEWHERE:
                events.extend(_field_events(change, lookup, build))
        return events


def _field_events(change: StateChange, lookup: Lookup, build: EventBuilder) -> list[Event]:
    field_name = change.field
    detail = change.detail if change.kind is ChangeKind.RECORDS and isinstance(change.detail, RecordsDetail) else None
    if detail is not None and field_name in RECORD_HANDLERS:
        events = RECORD_HANDLERS[field_name](change, detail, lookup, build)
        if detail.removed:  # entries on the earlier side only: reported literally, never explained
            events.append(_records_changed(change, lookup, build))
        return events
    if field_name == NUCLEAR_STRIKES:
        event = value_transition_event(campaign.NUCLEAR_STRIKES_CHANGED, change, lookup, build)
        return [event] if event is not None else []
    if field_name in SEA_LEVEL_RISES and change.before is False and change.after is True:
        return [_sea_level_rise(change, SEA_LEVEL_RISES[field_name], lookup, build)]
    if detail is not None:
        return [_records_changed(change, lookup, build)]
    event = _value_changed(change, lookup, build)
    return [event] if event is not None else []


def _owner(change: StateChange, lookup: Lookup) -> tuple[EntityId, EntityRef | None]:
    owner_id = change.entity_id
    assert owner_id is not None
    return owner_id, lookup.ref(owner_id)


def _entry_source(
    change: StateChange, record_set: RecordSet | None, entry: RecordEntry, member: Observed
) -> EventSource:
    location = record_set.entry_location(entry) if record_set is not None else None
    return EventSource(change, SourceRole.PRIMARY, None if isinstance(member, Unknown) else member, location)


def _refs(value: Observed, lookup: Lookup) -> list[EntityRef | None]:
    """The entities of a resolved reference or reference list; an unresolved value names none."""
    items = value if isinstance(value, tuple) else (value,)
    return [lookup.resolve(item) for item in items]


def _presence(change: StateChange, lookup: Lookup, build: EventBuilder) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    owner_id, owner = _owner(change, lookup)
    side = Side.AFTER if appeared else Side.BEFORE
    return build.event(
        campaign.GLOBAL_VALUES_APPEARED if appeared else campaign.GLOBAL_VALUES_DISAPPEARED,
        id_parts=(owner_id,),
        sources=(primary(change),),
        entities=(owner,),
        attributes=(("side", side.value),),
    )


def _milestones(change: StateChange, detail: RecordsDetail, lookup: Lookup, build: EventBuilder) -> list[Event]:
    """One event per milestone label added, and one per label recorded for a different faction than before."""
    owner_id, owner = _owner(change, lookup)
    record_set = lookup.record_set(owner_id, MILESTONES, Side.AFTER)
    events: list[Event] = []
    for entry in detail.added:
        if not isinstance(entry, KeyedEntry):
            continue
        events.append(
            build.event(
                campaign.MILESTONE_RECORDED,
                id_parts=(owner_id, entry.key),
                sources=(_entry_source(change, record_set, entry, entry.key),),
                entities=(owner, lookup.resolve(entry.value)),
                attributes=(("milestone", entry.key), ("faction", entry.value)),
                confidence=Confidence.LOW if is_unresolved(entry.value) else Confidence.HIGH,
            )
        )
    for old, new in detail.changed:
        if not isinstance(old, KeyedEntry) or not isinstance(new, KeyedEntry):
            continue
        transition = classify(old.value, new.value) or Transition.CHANGED
        events.append(
            build.event(
                campaign.MILESTONE_CHANGED,
                id_parts=(owner_id, new.key),
                sources=(_entry_source(change, record_set, new, new.key),),
                entities=(owner, lookup.resolve(old.value), lookup.resolve(new.value)),
                attributes=(
                    ("milestone", new.key),
                    ("transition", transition.value),
                    ("before", old.value),
                    ("after", new.value),
                ),
                confidence=confidence_for(transition, old.value, new.value),
            )
        )
    return events


def _once_per_campaign(change: StateChange, detail: RecordsDetail, lookup: Lookup, build: EventBuilder) -> list[Event]:
    """One event per name added to the once-per-campaign list (addressed by index: a name may repeat)."""
    owner_id, owner = _owner(change, lookup)
    record_set = lookup.record_set(owner_id, ONCE_PER_CAMPAIGN, Side.AFTER)
    return [
        build.event(
            campaign.NARRATIVE_EVENT_TRIGGERED,
            id_parts=(owner_id, "campaign", entry.index),
            sources=(_entry_source(change, record_set, entry, entry.value),),
            entities=(owner,),
            attributes=(("narrative_event", entry.value), ("scope", "campaign")),
        )
        for entry in detail.added
        if isinstance(entry, ItemEntry)
    ]


def _once_per_target(change: StateChange, detail: RecordsDetail, lookup: Lookup, build: EventBuilder) -> list[Event]:
    """One event per narrative event that gained targets: a new label, or a label whose target list grew.

    A label whose list only lost targets is reported by ``campaign.global_value_changed``.
    """
    owner_id, owner = _owner(change, lookup)
    record_set = lookup.record_set(owner_id, ONCE_PER_TARGET, Side.AFTER)
    gained: list[tuple[KeyedEntry, Observed]] = [
        (entry, entry.value) for entry in detail.added if isinstance(entry, KeyedEntry)
    ]
    lost_only: list[KeyedEntry] = []
    for old, new in detail.changed:
        if not isinstance(old, KeyedEntry) or not isinstance(new, KeyedEntry):
            continue
        if isinstance(old.value, tuple) and isinstance(new.value, tuple):
            before_ids = {item.entity_id for item in old.value if isinstance(item, EntityRef)}
            added = tuple(
                item for item in new.value if isinstance(item, EntityRef) and item.entity_id not in before_ids
            )
            if added:
                gained.append((new, added))
            else:
                lost_only.append(new)
        else:  # unresolved on one side: the targets gained are unknown
            gained.append((new, new.value))
    events = [
        build.event(
            campaign.NARRATIVE_EVENT_TRIGGERED,
            id_parts=(owner_id, "target", entry.key),
            sources=(_entry_source(change, record_set, entry, entry.key),),
            entities=(owner, *_refs(targets, lookup)),
            attributes=(("narrative_event", entry.key), ("scope", "target"), ("targets", targets)),
            confidence=Confidence.LOW if is_unresolved(targets) else Confidence.HIGH,
        )
        for entry, targets in gained
    ]
    if lost_only and not detail.removed:  # a removed entry already yields the literal record event
        events.append(_records_changed(change, lookup, build))
    return events


def _sea_level_rise(change: StateChange, stage: int, lookup: Lookup, build: EventBuilder) -> Event:
    owner_id, owner = _owner(change, lookup)
    return build.event(
        campaign.SEA_LEVEL_RISE_TRIGGERED,
        id_parts=(owner_id, stage),
        sources=(primary(change),),
        entities=(owner,),
        attributes=(("stage", stage), *transition_attributes(change, Transition.CHANGED)),
    )


def _value_changed(change: StateChange, lookup: Lookup, build: EventBuilder) -> Event | None:
    """Any other field of the singleton, literally; ``None`` on a schema gap."""
    transition = classify(change.before, change.after)
    if transition is None:
        return None
    owner_id, owner = _owner(change, lookup)
    return build.event(
        campaign.VALUE_CHANGED,
        id_parts=(owner_id, change.field),
        sources=(primary(change),),
        entities=(owner, *_refs(change.before, lookup), *_refs(change.after, lookup)),
        attributes=(("field", change.field), *transition_attributes(change, transition)),
        confidence=confidence_for(transition),
    )


def _records_changed(change: StateChange, lookup: Lookup, build: EventBuilder) -> Event:
    """A record of the singleton changed in a way no specific event explains: entry counts on each side."""
    owner_id, owner = _owner(change, lookup)
    detail = change.detail
    assert isinstance(detail, RecordsDetail)
    return build.event(
        campaign.VALUE_CHANGED,
        id_parts=(owner_id, change.field),
        sources=(primary(change),),
        entities=(owner,),
        attributes=(
            ("field", change.field),
            ("added", len(detail.added)),
            ("removed", len(detail.removed)),
            ("changed", len(detail.changed)),
            ("before", change.before),
            ("after", change.after),
        ),
    )


RECORD_HANDLERS = {
    MILESTONES: _milestones,
    ONCE_PER_CAMPAIGN: _once_per_campaign,
    ONCE_PER_TARGET: _once_per_target,
}
"""Records with specific events; each adds the literal record event itself when it leaves something unexplained."""
