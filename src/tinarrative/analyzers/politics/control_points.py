"""Control-point events: the ``faction`` and ``nation`` references, presence, and recorded losses.

Which faction thereby "controls a nation" is left to reconstruction.
"""

from __future__ import annotations

from ...model.changes import ChangeIndex, ChangeKind, RecordsDetail, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId, EntityRef
from ...model.events import Confidence, Event, EventSource, SourceRole
from ...model.records import KeyedEntry
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed
from ..common import (
    EventBuilder,
    Lookup,
    MembershipLedger,
    Side,
    Transition,
    classify,
    confidence_for,
    is_unresolved,
    list_changed_event,
    mirrored_sources,
    primary,
    transition_attributes,
)

CONTROLLER_CHANGED = "control_point.controller_changed"
NATION_CHANGED = "control_point.nation_changed"
APPEARED = "control_point.appeared"
DISAPPEARED = "control_point.disappeared"
LOSS_RECORDED = "control_point.loss_recorded"
FACTION_LIST_CHANGED = "faction.control_points_changed"
NATION_LIST_CHANGED = "nation.control_points_changed"

HANDLED_LISTS = ((EntityDomain.FACTION, "controlPoints"), (EntityDomain.NATION, "controlPoints"))
LOST_FIELD = "lostControlPoints"

_LIST_EVENT = {EntityDomain.FACTION.value: FACTION_LIST_CHANGED, EntityDomain.NATION.value: NATION_LIST_CHANGED}


class _LossRecord:
    """A changed entry of a faction's ``lostControlPoints`` record."""

    def __init__(
        self, source: EventSource, owner: EntityRef | None, recorded_on: Observed, previous: Observed | None
    ) -> None:
        self.source = source
        self.owner = owner
        self.recorded_on = recorded_on
        self.previous = previous


class ControlPointAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        ledger = MembershipLedger(index, HANDLED_LISTS)
        build = EventBuilder(before, after, lookup)
        losses = _loss_records(index, lookup)
        events: list[Event] = []

        for change in index.fields(EntityDomain.CONTROL_POINT, "faction"):
            event = _controller_changed(change, lookup, ledger, build, losses)
            if event is not None:
                events.append(event)
        for change in index.fields(EntityDomain.CONTROL_POINT, "nation"):
            event = _nation_changed(change, lookup, ledger, build)
            if event is not None:
                events.append(event)
        for change in index.presence(EntityDomain.CONTROL_POINT):
            events.append(_presence(change, lookup, ledger, build))
        for (faction_id, point_id), record in sorted(losses.items(), key=lambda item: (item[0][0], item[0][1])):
            events.append(_loss_recorded(faction_id, point_id, record, lookup, build))
        for change, member, transition in ledger.leftovers():
            events.append(list_changed_event(_LIST_EVENT[change.domain], change, member, transition, lookup, build))
        return events


def _loss_records(index: ChangeIndex, lookup: Lookup) -> dict[tuple[EntityId, EntityId], _LossRecord]:
    """``(faction, control point) -> record`` for every ``lostControlPoints`` entry added or re-dated."""
    records: dict[tuple[EntityId, EntityId], _LossRecord] = {}
    for change in index.fields(EntityDomain.FACTION, LOST_FIELD):
        if change.kind is not ChangeKind.RECORDS or not isinstance(change.detail, RecordsDetail):
            continue
        if change.entity_id is None:
            continue
        record_set = lookup.record_set(change.entity_id, LOST_FIELD, Side.AFTER)
        owner = lookup.ref(change.entity_id) or (record_set.owner if record_set is not None else None)
        pairs = [(entry, None) for entry in change.detail.added] + [
            (after, before) for before, after in change.detail.changed
        ]
        for entry, previous in pairs:
            if not isinstance(entry, KeyedEntry) or not isinstance(entry.key, EntityRef):
                continue  # an unresolvable key names no control point; the diff keeps it visible
            location = record_set.entry_location(entry) if record_set is not None else None
            source = EventSource(change, SourceRole.CORROBORATING, entry.key, location)
            previous_value = previous.value if isinstance(previous, KeyedEntry) else None
            records[(change.entity_id, entry.key.entity_id)] = _LossRecord(source, owner, entry.value, previous_value)
    return records


def _controller_changed(
    change: StateChange,
    lookup: Lookup,
    ledger: MembershipLedger,
    build: EventBuilder,
    losses: dict[tuple[EntityId, EntityId], _LossRecord],
) -> Event | None:
    transition = classify(change.before, change.after)
    if transition is None or change.entity_id is None:
        return None
    point_id = change.entity_id
    sources = mirrored_sources(change, ledger, "controlPoints", point_id)
    attributes = list(transition_attributes(change, transition))
    if isinstance(change.before, EntityRef):
        record = losses.get((change.before.entity_id, point_id))
        if record is not None:
            sources.append(record.source)
            attributes.append(("loss_recorded_on", record.recorded_on))
    return build.event(
        CONTROLLER_CHANGED,
        id_parts=(point_id,),
        sources=sources,
        entities=(
            lookup.ref(point_id),
            lookup.context_ref(point_id, "nation"),
            lookup.resolve(change.before),
            lookup.resolve(change.after),
        ),
        attributes=attributes,
        confidence=confidence_for(transition),
    )


def _nation_changed(change: StateChange, lookup: Lookup, ledger: MembershipLedger, build: EventBuilder) -> Event | None:
    transition = classify(change.before, change.after)
    if transition is None or change.entity_id is None:
        return None
    point_id = change.entity_id
    return build.event(
        NATION_CHANGED,
        id_parts=(point_id,),
        sources=mirrored_sources(change, ledger, "controlPoints", point_id),
        entities=(
            lookup.ref(point_id),
            lookup.resolve(change.before),
            lookup.resolve(change.after),
            lookup.context_ref(point_id, "faction"),
        ),
        attributes=transition_attributes(change, transition),
        confidence=confidence_for(transition),
    )


def _presence(change: StateChange, lookup: Lookup, ledger: MembershipLedger, build: EventBuilder) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    side = Side.AFTER if appeared else Side.BEFORE
    membership = Transition.ADDED if appeared else Transition.REMOVED
    point_id = change.entity_id
    assert point_id is not None  # presence changes always name their entity
    sources = [primary(change)]
    faction = lookup.ref_field(point_id, "faction", side)
    nation = lookup.ref_field(point_id, "nation", side)
    for owner in (faction, nation):
        if owner is not None:
            cited = ledger.claim(owner.entity_id, "controlPoints", point_id, membership, SourceRole.CORROBORATING)
            if cited is not None:
                sources.append(cited)
    return build.event(
        APPEARED if appeared else DISAPPEARED,
        id_parts=(point_id,),
        sources=sources,
        entities=(lookup.ref(point_id), nation, faction),
        attributes=(("side", side.value),),
    )


def _loss_recorded(
    faction_id: EntityId, point_id: EntityId, record: _LossRecord, lookup: Lookup, build: EventBuilder
) -> Event:
    attributes: list[tuple[str, Observed]] = [("recorded_on", record.recorded_on)]
    if record.previous is not None:
        attributes.append(("previous_recorded_on", record.previous))
    source = EventSource(record.source.change, SourceRole.PRIMARY, record.source.member, record.source.entry)
    confidence = Confidence.LOW if is_unresolved(record.recorded_on) else Confidence.HIGH
    return build.event(
        LOSS_RECORDED,
        id_parts=(faction_id, point_id),
        sources=(source,),
        entities=(lookup.resolve(record.source.member), record.owner, lookup.context_ref(point_id, "nation")),
        attributes=attributes,
        confidence=confidence,
        recorded_on=record.recorded_on,
    )
