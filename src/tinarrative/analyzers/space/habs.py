"""Hab (``TIHabState``, domain ``space object``) transitions and the faction's literal hab destruction log.

The log names a hab type and a space body, not a hab ID, so a recorded destruction stays separate from the hab's
disappearance. ``dockedFleets`` belongs to the fleet analyzer.
"""

from __future__ import annotations

from ...kinds.space import (
    HAB_APPEARED,
    HAB_CORE_COMPLETED_CHANGED,
    HAB_DESTRUCTION_RECORDED,
    HAB_DISAPPEARED,
    HAB_FACTION_CHANGED,
    HAB_IN_COMBAT_CHANGED,
    HAB_TIER_CHANGED,
    HAB_TYPE_CHANGED,
    HAB_UNDER_ASSAULT_CHANGED,
    HAB_UNDER_BOMBARDMENT_CHANGED,
)
from ...model.changes import ChangeIndex, ChangeKind, RecordsDetail, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId, EntityRef
from ...model.events import Confidence, Event, EventSource, SourceRole
from ...model.records import DestructionEntry
from ...model.snapshot import EntityState, SaveSnapshot
from ...model.values import Observed
from ..common import EventBuilder, Lookup, Side, is_unresolved, primary, value_transition_event

VALUE_FIELDS = (
    ("faction", HAB_FACTION_CHANGED),
    ("habType", HAB_TYPE_CHANGED),
    ("tier", HAB_TIER_CHANGED),
    ("inCombat", HAB_IN_COMBAT_CHANGED),
    ("underAssault", HAB_UNDER_ASSAULT_CHANGED),
    ("underBombardment", HAB_UNDER_BOMBARDMENT_CHANGED),
    ("anyCoreCompleted", HAB_CORE_COMPLETED_CHANGED),
)
LOG_FIELD = "HabDestructionLog"

HabKey = tuple[EntityId, str, EntityId]
"""Owning faction, hab type and body: what a destruction log entry and a vanished hab share."""


class HabAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        build = EventBuilder(before, after, lookup)
        events: list[Event] = []

        for field_name, kind in VALUE_FIELDS:
            for change in index.fields(EntityDomain.SPACE_OBJECT, field_name):
                assert change.entity_id is not None
                context = () if field_name == "faction" else (lookup.context_ref(change.entity_id, "faction"),)
                event = value_transition_event(kind, change, lookup, build, context=context)
                if event is not None:
                    events.append(event)
        for change in index.presence(EntityDomain.SPACE_OBJECT):
            events.append(_presence(change, lookup, build))
        vanished = _vanished_habs(index, lookup)
        for change in index.fields(EntityDomain.FACTION, LOG_FIELD):
            events.extend(_destructions_recorded(change, lookup, build, vanished))
        return events


def _presence(change: StateChange, lookup: Lookup, build: EventBuilder) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    side = Side.AFTER if appeared else Side.BEFORE
    hab_id = change.entity_id
    assert hab_id is not None
    attributes: list[tuple[str, Observed]] = [("side", side.value)]
    if appeared:
        attributes.extend(_launch_attributes(lookup.state(hab_id, Side.AFTER)))
    return build.event(
        HAB_APPEARED if appeared else HAB_DISAPPEARED,
        id_parts=(hab_id,),
        sources=(primary(change),),
        entities=(lookup.ref(hab_id), lookup.ref_field(hab_id, "faction", side)),
        attributes=attributes,
    )


def _launch_attributes(state: EntityState | None) -> list[tuple[str, Observed]]:
    """Whether a new hab's core already works and, while it does not, the core's projected arrival and completion.

    A hab appears at launch; it is founded when its core completes (``reconstruction/space.py``).
    """
    if state is None:
        return []
    completed = state.get("anyCoreCompleted")
    if not isinstance(completed, bool):
        return []
    found: list[tuple[str, Observed]] = [("core_completed", completed)]
    if not completed:
        for name, field_name in (
            ("projected_arrival", "coreStartBuildDate"),
            ("projected_completion", "coreCompletionDate"),
        ):
            value = state.get(field_name)
            if isinstance(value, str):
                found.append((name, value))
    return found


def _vanished_habs(index: ChangeIndex, lookup: Lookup) -> dict[HabKey, list[EntityId]]:
    """The habs gone from the later save by the key a destruction entry shares, read from the earlier save."""
    found: dict[HabKey, list[EntityId]] = {}
    for change in index.presence(EntityDomain.SPACE_OBJECT):
        hab_id = change.entity_id
        if change.kind is not ChangeKind.DISAPPEARED or hab_id is None:
            continue
        faction = lookup.ref_field(hab_id, "faction", Side.BEFORE)
        body = lookup.ref_field(hab_id, "barycenter", Side.BEFORE)
        state = lookup.state(hab_id, Side.BEFORE)
        hab_type = state.get("habType") if state is not None else None
        if faction is not None and body is not None and isinstance(hab_type, str):
            found.setdefault((faction.entity_id, hab_type, body.entity_id), []).append(hab_id)
    return found


def _destructions_recorded(
    change: StateChange, lookup: Lookup, build: EventBuilder, vanished: dict[HabKey, list[EntityId]]
) -> list[Event]:
    """One record-dated event per log entry added; a removed entry stays in the diff (logs grow).

    ``hab`` is set only for a one-to-one match of entry and vanished hab; ``owner`` is the log's faction.
    """
    if change.kind is not ChangeKind.RECORDS or not isinstance(change.detail, RecordsDetail):
        return []
    if change.entity_id is None:
        return []
    faction_id = change.entity_id
    record_set = lookup.record_set(faction_id, LOG_FIELD, Side.AFTER)
    owner = lookup.ref(faction_id) or (record_set.owner if record_set is not None else None)
    added = [entry for entry in change.detail.added if isinstance(entry, DestructionEntry)]
    entries_per_key: dict[HabKey, int] = {}
    for entry in added:
        key = _entry_key(faction_id, entry)
        if key is not None:
            entries_per_key[key] = entries_per_key.get(key, 0) + 1
    events: list[Event] = []
    for entry in added:  # an unparseable element is skipped; the diff keeps it visible
        location = record_set.entry_location(entry) if record_set is not None else None
        attributes: list[tuple[str, Observed]] = [
            ("hab_type", entry.hab_type),
            ("space_body", entry.space_body),
            ("destroyer", entry.destroyer),
            ("recorded_on", entry.date),
        ]
        unresolved = any(is_unresolved(value) for _, value in attributes)
        key = _entry_key(faction_id, entry)
        habs = vanished.get(key, []) if key is not None else []
        unique = key is not None and entries_per_key[key] == 1 and len(habs) == 1
        hab = lookup.ref(habs[0]) if unique else None
        if hab is not None:
            attributes.append(("hab", hab))
        if owner is not None:
            attributes.append(("owner", owner))
        events.append(
            build.event(
                HAB_DESTRUCTION_RECORDED,
                id_parts=(faction_id, entry.index),
                sources=(EventSource(change, SourceRole.PRIMARY, None, location),),
                entities=(owner, lookup.resolve(entry.space_body), lookup.resolve(entry.destroyer), hab),
                attributes=attributes,
                confidence=Confidence.LOW if unresolved else Confidence.HIGH,
                recorded_on=entry.date,
            )
        )
    return events


def _entry_key(faction_id: EntityId, entry: DestructionEntry) -> HabKey | None:
    body = entry.space_body
    if not isinstance(entry.hab_type, str) or not isinstance(body, EntityRef):
        return None
    return (faction_id, entry.hab_type, body.entity_id)
