"""Nation territory, structure, relations and the recorded executive change.

Events here speak about which nation a region belongs to, a nation's capital, federation, breakaway
links and relation lists, and the literal ``lastExecutiveChange`` record. They never say which faction
controls a nation: that is a reconstruction question, and control-point control is reported separately.
"""

from __future__ import annotations

from ...model.changes import ChangeKind, RecordsDetail, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityRef
from ...model.events import Confidence, Event, EventSource, SourceRole
from ...model.records import KeyedEntry, RecordSet
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed, Unknown
from ..common import (
    ChangeIndex,
    EventBuilder,
    Lookup,
    MembershipLedger,
    Side,
    classify,
    confidence_for,
    is_unresolved,
    list_changed_event,
    mirrored_sources,
    primary,
    transition_attributes,
)

REGION_NATION_CHANGED = "region.nation_changed"
CAPITAL_CHANGED = "nation.capital_changed"
RELATION_CHANGED = "nation.relation_changed"
FEDERATION_CHANGED = "nation.federation_changed"
BREAKAWAY_PARENT_CHANGED = "nation.breakaway_parent_changed"
EXECUTIVE_CHANGE_RECORDED = "nation.executive_change_recorded"
APPEARED = "nation.appeared"
DISAPPEARED = "nation.disappeared"

RELATION_FIELDS = ("allies", "rivals", "wars")
"""Nation-to-nation reference lists; an entry is expected on both nations, which is checked, not assumed."""
HANDLED_LISTS = tuple((EntityDomain.NATION, name) for name in ("regions", "breakaways", *RELATION_FIELDS))
EXECUTIVE_FIELD = "lastExecutiveChange"


def list_event_type(field_name: str) -> str:
    return f"nation.{field_name}_changed"


class NationAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = ChangeIndex(diff)
        lookup = Lookup(before, after)
        ledger = MembershipLedger(index, HANDLED_LISTS)
        build = EventBuilder(before, after)
        events: list[Event] = []

        for change in index.fields(EntityDomain.REGION, "nation"):
            events.extend(_owner_transition(REGION_NATION_CHANGED, change, "regions", lookup, ledger, build))
        for change in index.fields(EntityDomain.NATION, "breakawayParent"):
            events.extend(_owner_transition(BREAKAWAY_PARENT_CHANGED, change, "breakaways", lookup, ledger, build))
        for change in index.fields(EntityDomain.NATION, "capital"):
            events.extend(_value_transition(CAPITAL_CHANGED, change, lookup, build))
        for change in index.fields(EntityDomain.NATION, "federation"):
            events.extend(_value_transition(FEDERATION_CHANGED, change, lookup, build))
        for field_name in RELATION_FIELDS:
            events.extend(_relations(field_name, lookup, ledger, build))
        for change in index.fields(EntityDomain.NATION, EXECUTIVE_FIELD):
            event = _executive_change(change, lookup, build)
            if event is not None:
                events.append(event)
        for change in index.presence(EntityDomain.NATION):
            events.append(_presence(change, lookup, build))
        for change, member, transition in ledger.leftovers():
            assert change.field is not None
            events.append(list_changed_event(list_event_type(change.field), change, member, transition, lookup, build))
        return events


def _owner_transition(
    event_type: str, change: StateChange, list_field: str, lookup: Lookup, ledger: MembershipLedger, build: EventBuilder
) -> list[Event]:
    """A reference to an owning nation changed; the owners' lists corroborate when they mirror it."""
    transition = classify(change.before, change.after)
    if transition is None or change.entity_id is None:
        return []
    subject = change.entity_id
    return [
        build.event(
            event_type,
            id_parts=(subject,),
            sources=mirrored_sources(change, ledger, list_field, subject),
            entities=(lookup.ref(subject), lookup.resolve(change.before), lookup.resolve(change.after)),
            attributes=transition_attributes(change, transition),
            confidence=confidence_for(transition),
        )
    ]


def _value_transition(event_type: str, change: StateChange, lookup: Lookup, build: EventBuilder) -> list[Event]:
    """A single field of a nation changed; values that are not references are carried literally."""
    transition = classify(change.before, change.after)
    if transition is None or change.entity_id is None:
        return []
    subject = change.entity_id
    return [
        build.event(
            event_type,
            id_parts=(subject,),
            sources=(primary(change),),
            entities=(lookup.ref(subject), lookup.resolve(change.before), lookup.resolve(change.after)),
            attributes=transition_attributes(change, transition),
            confidence=confidence_for(transition),
        )
    ]


def _relations(field_name: str, lookup: Lookup, ledger: MembershipLedger, build: EventBuilder) -> list[Event]:
    """One event per nation pair and direction; the mirrored entry of the other nation is merged when present."""
    events: list[Event] = []
    for owner, member, transition in ledger.pending(field_name):
        own = ledger.claim(owner, field_name, member.entity_id, transition, SourceRole.PRIMARY)
        if own is None:
            continue  # consumed as the mirror of an earlier pair
        mirror = ledger.claim(member.entity_id, field_name, owner, transition, SourceRole.PRIMARY)
        pair = sorted((owner, member.entity_id), key=lambda entity_id: entity_id.sort_key)
        attributes: list[tuple[str, Observed]] = [
            ("relation", field_name),
            ("transition", transition.value),
            ("reciprocal", mirror is not None),
        ]
        if mirror is None:
            attributes.append(("listed_by", lookup.ref(owner)))
        events.append(
            build.event(
                RELATION_CHANGED,
                id_parts=(field_name, *pair, transition.value),
                sources=[own] if mirror is None else [own, mirror],
                entities=tuple(lookup.ref(entity_id) for entity_id in pair),
                attributes=attributes,
            )
        )
    return events


def _entry_values(record_set: RecordSet | None) -> dict[str, KeyedEntry]:
    if record_set is None or isinstance(record_set.entries, Unknown):
        return {}
    return {
        entry.key: entry for entry in record_set.entries if isinstance(entry, KeyedEntry) and isinstance(entry.key, str)
    }


def _value(entries: dict[str, KeyedEntry], key: str) -> Observed:
    entry = entries.get(key)
    return entry.value if entry is not None else Unknown()


def _executive_change(change: StateChange, lookup: Lookup, build: EventBuilder) -> Event | None:
    """The nation's ``lastExecutiveChange`` record differs: cite each member that changed, copy the values literally."""
    if (
        change.kind is not ChangeKind.RECORDS
        or not isinstance(change.detail, RecordsDetail)
        or change.entity_id is None
    ):
        return None
    nation_id = change.entity_id
    before_set = lookup.record_set(nation_id, EXECUTIVE_FIELD, Side.BEFORE)
    after_set = lookup.record_set(nation_id, EXECUTIVE_FIELD, Side.AFTER)
    before_values, after_values = _entry_values(before_set), _entry_values(after_set)
    sources: list[EventSource] = []
    for entry in change.detail.added:
        sources.append(_entry_source(change, entry, after_set))
    for entry in change.detail.removed:
        sources.append(_entry_source(change, entry, before_set))
    for _, entry in change.detail.changed:
        sources.append(_entry_source(change, entry, after_set))
    new_executive = _value(after_values, "newExecutive")
    recorded_on = _value(after_values, "date")
    attributes: list[tuple[str, Observed]] = [
        ("new_executive", new_executive),
        ("recorded_on", recorded_on),
        ("cause", _value(after_values, "cause")),
    ]
    if before_values:
        attributes += [
            ("previous_executive", _value(before_values, "newExecutive")),
            ("previous_recorded_on", _value(before_values, "date")),
            ("previous_cause", _value(before_values, "cause")),
        ]
    unresolved = any(is_unresolved(value) for _, value in attributes)
    return build.event(
        EXECUTIVE_CHANGE_RECORDED,
        id_parts=(nation_id,),
        sources=sources,
        entities=(
            lookup.ref(nation_id),
            lookup.resolve(new_executive),
            lookup.resolve(_value(before_values, "newExecutive")),
        ),
        attributes=attributes,
        confidence=Confidence.LOW if unresolved else Confidence.HIGH,
        recorded_on=recorded_on,
    )


def _entry_source(change: StateChange, entry: object, record_set: RecordSet | None) -> EventSource:
    if not isinstance(entry, KeyedEntry):
        return EventSource(change, SourceRole.PRIMARY)
    location = record_set.entry_location(entry) if record_set is not None else None
    member = entry.key if isinstance(entry.key, str | EntityRef) else None
    return EventSource(change, SourceRole.PRIMARY, member, location)


def _presence(change: StateChange, lookup: Lookup, build: EventBuilder) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    nation_id = change.entity_id
    assert nation_id is not None
    side = Side.AFTER if appeared else Side.BEFORE
    return build.event(
        APPEARED if appeared else DISAPPEARED,
        id_parts=(nation_id,),
        sources=(primary(change),),
        entities=(lookup.ref(nation_id),),
        attributes=(("side", side.value),),
    )
