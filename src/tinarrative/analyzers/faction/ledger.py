"""A faction's resource ledger (``TIFactionState.Transactions``) as dated mission and operation charges.

A charge is made at assignment, before the outcome, and proves neither success nor a target: the events are
corroborating and dating evidence only (ADR-0010). Entries are read by date from the later snapshot, with
the ledger's ``records`` change as the cited source; the evidence that ``(before, after]`` entries are reliably
present is in ``higher-level-event-sources.md``. Labels are game identifiers and may appear in IDs and lines; amounts
and labels are never logged.
"""

from __future__ import annotations

import logging
from collections import Counter

from ...kinds import faction as faction_kinds
from ...log import fields as log_fields
from ...log import get_logger
from ...model.changes import ChangeKind, RecordsDetail, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId
from ...model.events import Confidence, Event, EventSource, SourceRole
from ...model.ledger import ALLOWED_LEDGER_LABELS
from ...model.records import LedgerEntry, RecordSet
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed
from ..common import EventBuilder, Lookup, Side

logger = get_logger(__name__)

LEDGER_FIELD = "Transactions"
TRANSACTION_RECORDED = faction_kinds.TRANSACTION_RECORDED.event_type

ALLOWED_LABELS = ALLOWED_LEDGER_LABELS


def in_window(before_date: Observed, after_date: Observed, entry_date: Observed) -> bool:
    """Whether an ISO-dated entry falls inside ``(before, after]``; false when any date is not a string.

    Compared as full timestamps in text order (same ISO shape): a charge later on the earlier save's day belongs here.
    """
    if not (isinstance(before_date, str) and isinstance(after_date, str) and isinstance(entry_date, str)):
        return False
    return before_date < entry_date <= after_date


class LedgerAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        build = EventBuilder(before, after, lookup)
        counts: Counter[str] = Counter()
        events: list[Event] = []
        for change in index.fields(EntityDomain.FACTION, LEDGER_FIELD):
            events.extend(_ledger_events(change, before, after, lookup, build, counts))
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "ledger analyzer done %s",
                log_fields(
                    factions=counts["factions"],
                    entries=counts["entries"],
                    emitted=len(events),
                    skipped_label=counts["skipped_label"],
                    skipped_date=counts["skipped_date"],
                ),
            )
        return events


def _source(change: StateChange, record_set: RecordSet, entry: LedgerEntry) -> EventSource:
    return EventSource(change, SourceRole.PRIMARY, None, record_set.entry_location(entry))


def _attributes(entry: LedgerEntry) -> tuple[tuple[str, Observed], ...]:
    return (
        ("label", entry.label),
        ("resource", entry.resource),
        ("amount", entry.amount),
        ("recorded_on", entry.date),
    )


def _ledger_events(
    change: StateChange,
    before: SaveSnapshot,
    after: SaveSnapshot,
    lookup: Lookup,
    build: EventBuilder,
    counts: Counter[str],
) -> list[Event]:
    """One event per allow-listed entry of the later ledger dated inside the interval."""
    if change.kind is not ChangeKind.RECORDS or not isinstance(change.detail, RecordsDetail):
        return []
    if change.entity_id is None:
        return []
    faction_id: EntityId = change.entity_id
    after_set = lookup.record_set(faction_id, LEDGER_FIELD, Side.AFTER)
    if after_set is None or not isinstance(after_set.entries, tuple):
        return []
    counts["factions"] += 1
    owner = lookup.ref(faction_id) or after_set.owner
    events: list[Event] = []
    for entry in after_set.entries:
        if not isinstance(entry, LedgerEntry):
            continue
        counts["entries"] += 1
        if entry.label not in ALLOWED_LABELS:
            counts["skipped_label"] += 1
            continue
        if not in_window(before.date, after.date, entry.date):
            counts["skipped_date"] += 1
            continue
        events.append(
            build.event(
                faction_kinds.TRANSACTION_RECORDED,
                id_parts=(faction_id, entry.label, entry.index),  # the index is per label list
                sources=(_source(change, after_set, entry),),
                entities=(owner,),
                attributes=_attributes(entry),
                confidence=Confidence.HIGH,
                recorded_on=entry.date,
            )
        )
    return events
