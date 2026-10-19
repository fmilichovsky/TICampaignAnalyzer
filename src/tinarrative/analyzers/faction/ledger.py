"""A faction's resource ledger (``TIFactionState.Transactions``) as dated mission and operation charges.

Each entry of the later snapshot whose label is allow-listed and whose date falls inside the interval becomes one
objective ``faction.transaction_recorded`` event, dated by the entry. The entry is a cost charged when a mission or
operation is assigned, some days to weeks before it resolves, and a charge does not mean the mission succeeded. It
names no target. So the event is corroborating and dating evidence for an effect that is already evidenced, under the
bounds of architecture 11.3; no rule anchors on it, and confidence on ledger evidence alone stays at most medium in
the consumers. This event itself records a literal entry and is high confidence, like ``faction.combat_recorded``.

Entries are read **by date from the later snapshot**, not from the diff's ``added`` list, as the architecture asks;
the ledger's ``records`` change of the interval is still the cited source, so every event is backed by a literal
change. Entries are never rewritten, and an entry pruned between two saves is dated at or before the earlier save, so an
entry dated inside ``(before, after]`` is reliably present in the later save (evidence:
``higher-level-event-sources.md``, ``TIFactionState.Transactions``). Dates are compared as full timestamps: saves
are written at midnight and charges carry the time of day, so a charge made later on the earlier save's day
belongs to this interval. The allow-list holds the labels whose charges agree with a visible effect; income, spoils,
trade, council transfers, ``Effect.*`` bookkeeping, org purchases, project and objective rewards and the hashed
numeric labels are never emitted. Labels are game identifiers (mission and operation template names, like notification
template names), not player text, so they appear in IDs and rendered lines; amounts and labels are never logged.
"""

from __future__ import annotations

import logging
from collections import Counter

from ...log import fields as log_fields
from ...log import get_logger
from ...model.changes import ChangeKind, RecordsDetail, StateChange, StateDiff
from ...model.entities import EntityDomain, EntityId
from ...model.events import Confidence, Event, EventSource, SourceRole
from ...model.records import LedgerEntry, RecordSet
from ...model.snapshot import SaveSnapshot
from ...model.values import Observed
from ..common import ChangeIndex, EventBuilder, Lookup, Side

logger = get_logger(__name__)

LEDGER_FIELD = "Transactions"
TRANSACTION_RECORDED = "faction.transaction_recorded"

COUNCILOR_MISSIONS: frozenset[str] = frozenset(
    {
        "Coup",
        "Purge",
        "Crackdown",
        "HostileTakeover",
        "Propaganda",
        "Stabilize",
        "Inspire",
        "Unrest",
        "Assassinate",
        "Detain",
        "Turn",
        "Advise",
        "Extract",
        "Augmentation",
        "SetNationalPolicy",
        "DefendInterests",
        "InvestigateCouncilor",
        "StealProject",
        "SabotageProject",
        "SabotageFacilities",
        "Abductions",
        "EnthrallElites",
        "TerrorizeRegion",
        "Xenoform",
        "AssaultAlienAsset",
        "Contact",
    }
)
"""Councilor mission labels (evidence in ``higher-level-event-sources.md``). ``Unrest`` entries are cross-checked
against ``factionUnrestAttempts`` by the consumers (bound 7)."""

SPACE_OPERATIONS: frozenset[str] = frozenset(
    {
        "FoundColonyOperation",
        "FoundOrbitalOperation",
        "FoundOutpostOperation",
        "FoundPlatformOperation",
        "FoundRingOperation",
        "FoundSettlementOperation",
        "LaunchProbeOperation",
        "LaunchAllProbeOperation",
        "RepairFleetOperation",
        "ResupplyOperation",
        "ResupplyAndRepairOperation",
        "TransferOfficersOperation",
    }
)
"""Space operation labels, listed by name rather than by suffix so that an unseen label is reviewed before it is
emitted. ``Found*Operation`` charges accompany a hab gained in the same interval."""

ASSET_CHARGES: frozenset[str] = frozenset({"Ship Construction", "Hire Councilor", "Global Milestone"})
"""``Ship Construction`` charges (one entry per resource) accompany ships gained by the faction; ``Hire Councilor``
matches councilors that gained a faction; ``Global Milestone`` accompanies a global milestone."""

ALLOWED_LABELS: frozenset[str] = COUNCILOR_MISSIONS | SPACE_OPERATIONS | ASSET_CHARGES
"""The labels whose entries become events. Everything else is left in the diff."""


def in_window(before_date: Observed, after_date: Observed, entry_date: Observed) -> bool:
    """Whether an ISO-dated entry falls inside ``(before, after]``; false when any date is not a string.

    The snapshot dates and record dates are ISO-8601 texts of the same shape, so text order is date order.
    """
    if not (isinstance(before_date, str) and isinstance(after_date, str) and isinstance(entry_date, str)):
        return False
    return before_date < entry_date <= after_date


class LedgerAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = ChangeIndex(diff)
        lookup = Lookup(before, after)
        build = EventBuilder(before, after)
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
                TRANSACTION_RECORDED,
                id_parts=(faction_id, entry.label, entry.index),  # the index is per label list
                sources=(_source(change, after_set, entry),),
                entities=(owner,),
                attributes=_attributes(entry),
                confidence=Confidence.HIGH,
                recorded_on=entry.date,
            )
        )
    return events
