"""Hab (``TIHabState``, domain ``space object``) transitions and the faction's literal hab destruction log.

Events here speak about a hab's ``faction``, ``habType``, ``tier``, combat and assault flags, core completion and
presence, and about every entry added to a faction's ``HabDestructionLog``. The log names a hab type and a space
body, not a hab ID, so a recorded destruction is never linked to a hab absent from the later save: the two stay
separate events. ``sectors``, ``councilorsOnBoard``, ``officersOnBoard``, orbit and position fields stay in the
diff; ``dockedFleets`` belongs to the fleet analyzer.
"""

from __future__ import annotations

from ...model.changes import ChangeKind, RecordsDetail, StateChange, StateDiff
from ...model.entities import EntityDomain
from ...model.events import Confidence, Event, EventSource, SourceRole
from ...model.records import DestructionEntry
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed
from ..common import ChangeIndex, EventBuilder, Lookup, Side, is_unresolved, primary, value_transition_event

FACTION_CHANGED = "hab.faction_changed"
TYPE_CHANGED = "hab.type_changed"
TIER_CHANGED = "hab.tier_changed"
IN_COMBAT_CHANGED = "hab.in_combat_changed"
UNDER_ASSAULT_CHANGED = "hab.under_assault_changed"
UNDER_BOMBARDMENT_CHANGED = "hab.under_bombardment_changed"
CORE_COMPLETED_CHANGED = "hab.core_completed_changed"
APPEARED = "hab.appeared"
DISAPPEARED = "hab.disappeared"
DESTRUCTION_RECORDED = "faction.hab_destruction_recorded"

VALUE_FIELDS = (
    ("faction", FACTION_CHANGED),
    ("habType", TYPE_CHANGED),
    ("tier", TIER_CHANGED),
    ("inCombat", IN_COMBAT_CHANGED),
    ("underAssault", UNDER_ASSAULT_CHANGED),
    ("underBombardment", UNDER_BOMBARDMENT_CHANGED),
    ("anyCoreCompleted", CORE_COMPLETED_CHANGED),
)
LOG_FIELD = "HabDestructionLog"


class HabAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = ChangeIndex(diff)
        lookup = Lookup(before, after)
        build = EventBuilder(before, after)
        events: list[Event] = []

        for field_name, event_type in VALUE_FIELDS:
            for change in index.fields(EntityDomain.SPACE_OBJECT, field_name):
                assert change.entity_id is not None
                context = () if field_name == "faction" else (lookup.context_ref(change.entity_id, "faction"),)
                event = value_transition_event(event_type, change, lookup, build, context=context)
                if event is not None:
                    events.append(event)
        for change in index.presence(EntityDomain.SPACE_OBJECT):
            events.append(_presence(change, lookup, build))
        for change in index.fields(EntityDomain.FACTION, LOG_FIELD):
            events.extend(_destructions_recorded(change, lookup, build))
        return events


def _presence(change: StateChange, lookup: Lookup, build: EventBuilder) -> Event:
    appeared = change.kind is ChangeKind.APPEARED
    side = Side.AFTER if appeared else Side.BEFORE
    hab_id = change.entity_id
    assert hab_id is not None
    return build.event(
        APPEARED if appeared else DISAPPEARED,
        id_parts=(hab_id,),
        sources=(primary(change),),
        entities=(lookup.ref(hab_id), lookup.ref_field(hab_id, "faction", side)),
        attributes=(("side", side.value),),
    )


def _destructions_recorded(change: StateChange, lookup: Lookup, build: EventBuilder) -> list[Event]:
    """One record-dated event per log entry added; a removed entry stays in the diff (logs grow)."""
    if change.kind is not ChangeKind.RECORDS or not isinstance(change.detail, RecordsDetail):
        return []
    if change.entity_id is None:
        return []
    faction_id = change.entity_id
    record_set = lookup.record_set(faction_id, LOG_FIELD, Side.AFTER)
    owner = lookup.ref(faction_id) or (record_set.owner if record_set is not None else None)
    events: list[Event] = []
    for entry in change.detail.added:
        if not isinstance(entry, DestructionEntry):
            continue  # an unparseable element; the diff keeps it visible
        location = record_set.entry_location(entry) if record_set is not None else None
        attributes: list[tuple[str, Observed]] = [
            ("hab_type", entry.hab_type),
            ("space_body", entry.space_body),
            ("destroyer", entry.destroyer),
            ("recorded_on", entry.date),
        ]
        unresolved = any(is_unresolved(value) for _, value in attributes)
        events.append(
            build.event(
                DESTRUCTION_RECORDED,
                id_parts=(faction_id, entry.index),
                sources=(EventSource(change, SourceRole.PRIMARY, None, location),),
                entities=(owner, lookup.resolve(entry.space_body), lookup.resolve(entry.destroyer)),
                attributes=attributes,
                confidence=Confidence.LOW if unresolved else Confidence.HIGH,
                recorded_on=entry.date,
            )
        )
    return events
