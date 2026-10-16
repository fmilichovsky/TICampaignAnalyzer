"""Decode save-carried records (``RECORD_FIELDS``) into ``RecordSet`` objects.

Each record field of an entity becomes exactly one :class:`~tinarrative.model.records.RecordSet`, located at
``<entity Value path>/<field>``. An absent field gives ``entries = Unknown()``; a field whose value does not
have the documented shape gives ``Unknown(unparseable, raw)`` and an ``unexpected_field_shape`` finding. A
problem inside one element (an unparseable date, an unresolvable reference) stays inside that entry, so
the rest of the log remains evidence. Nothing read from a record is logged: ledger labels, milestone names,
narrative-event names, kill lists and notification summaries are campaign content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..identity import STATE_PREFIX
from ..log import fields as log_fields
from ..log import get_logger
from ..model.entities import EntityRef
from ..model.evidence import SourceLocation, pointer_path
from ..model.records import (
    DestructionEntry,
    ItemEntry,
    KeyedEntry,
    LedgerEntry,
    NotificationEntry,
    RecordEntry,
    RecordKind,
    RecordSet,
    record_counts,
)
from ..model.snapshot import EntityState
from ..model.values import Observed, Unknown, UnknownReason, freeze
from .containers import StateEntry, decode_pair_map, entry_path
from .dates import iso_date
from .fields import RECORD_ENTRY_MEMBERS, RECORD_FIELDS, RECORD_MEMBER_TARGETS, RecordField, entry_member_name
from .references import ExpectedDomains, ReferenceIndex
from .unknowns import PAIR_MAP, UnknownCollector, check_reference

logger = get_logger(__name__)

OBJECT = "object"
ARRAY = "array"
ARRAY_OF_OBJECTS = "array_of_objects"
"""``field_shape`` details for a record field, or a list element inside one, of the wrong JSON type."""

Entries = tuple[RecordEntry, ...] | Unknown


@dataclass
class _Context:
    """One record field of one entity being decoded; counts problems for the per-type debug aggregate."""

    state_type: str
    field: str
    index: ReferenceIndex
    collector: UnknownCollector
    unparseable_dates: int = 0
    unresolved_references: int = 0
    shape_findings: int = 0

    def unparseable(self, expected: str, raw: Any) -> Unknown:
        self.collector.field_shape(self.state_type, self.field, expected, raw)
        self.shape_findings += 1
        return Unknown(UnknownReason.UNPARSEABLE, freeze(raw))

    def date(self, raw: Any) -> Observed:
        value = iso_date(raw, self.state_type, self.field, self.collector)
        if isinstance(value, Unknown):
            self.unparseable_dates += 1
        return value

    def reference(self, raw: Any, expected: ExpectedDomains, name: str) -> Observed:
        check_reference(self.state_type, name, raw, expected, False, self.index, self.collector)
        value = self.index.resolve(raw, expected)
        if isinstance(value, Unknown):
            self.unresolved_references += 1
        return value

    def member(self, item: dict[str, Any], name: str) -> Observed:
        return freeze(item[name]) if name in item else Unknown()

    def member_date(self, item: dict[str, Any], name: str) -> Observed:
        return self.date(item[name]) if name in item else Unknown()

    def member_reference(self, item: dict[str, Any], name: str) -> Observed:
        if name not in item:
            return Unknown()
        qualified = f"{self.field}.{name}"
        return self.reference(item[name], RECORD_MEMBER_TARGETS[qualified], qualified)

    def member_references(self, item: dict[str, Any], name: str) -> Observed:
        """A list of references inside an entry; one unresolvable element makes the member unknown."""
        if name not in item:
            return Unknown()
        qualified = f"{self.field}.{name}"
        targets = RECORD_MEMBER_TARGETS[qualified]
        check_reference(self.state_type, qualified, item[name], targets, True, self.index, self.collector)
        value = self.index.resolve_list(item[name], targets)
        if isinstance(value, Unknown):
            self.unresolved_references += 1
        return value


def _ledger(raw: Any, ctx: _Context) -> Entries:
    if not isinstance(raw, dict):
        return ctx.unparseable(OBJECT, raw)
    entries: list[RecordEntry] = []
    for label in sorted(raw):
        items = raw[label]
        if not isinstance(items, list):
            ctx.collector.field_shape(ctx.state_type, ctx.field, ARRAY, items)
            ctx.shape_findings += 1
            continue
        for position, item in enumerate(items):
            if not isinstance(item, dict):
                bad = ctx.unparseable(ARRAY_OF_OBJECTS, item)
                entries.append(LedgerEntry(position, str(label), bad, bad, bad))
                continue
            entries.append(
                LedgerEntry(
                    position,
                    str(label),
                    ctx.member(item, "Resource"),
                    ctx.member(item, "Amount"),
                    ctx.member_date(item, "Date"),
                )
            )
    return tuple(entries)


def _destruction_log(raw: Any, ctx: _Context) -> Entries:
    if not isinstance(raw, list):
        return ctx.unparseable(ARRAY, raw)
    entries: list[RecordEntry] = []
    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            bad = ctx.unparseable(ARRAY_OF_OBJECTS, item)
            entries.append(DestructionEntry(position, bad, bad, bad, bad))
            continue
        entries.append(
            DestructionEntry(
                position,
                ctx.member(item, "HabType"),
                ctx.member_reference(item, "SpaceBody"),
                ctx.member_date(item, "Date"),
                ctx.member_reference(item, "Destroyer"),
            )
        )
    return tuple(entries)


def _name_log(raw: Any, ctx: _Context) -> Entries:
    if not isinstance(raw, list):
        return ctx.unparseable(ARRAY, raw)
    return tuple(ItemEntry(position, freeze(item)) for position, item in enumerate(raw))


def _pair_map(raw: Any, spec: RecordField, ctx: _Context) -> Entries:
    pairs = decode_pair_map(raw)
    if pairs is None:
        return ctx.unparseable(PAIR_MAP, raw)
    targets = spec.targets if spec.targets is not None else frozenset()
    dated = spec.kind is RecordKind.DATED_REFERENCES
    return tuple(
        KeyedEntry(position, ctx.reference(key, targets, ctx.field), ctx.date(value) if dated else freeze(value))
        for position, (key, value) in enumerate(pairs)
    )


def _label_map(raw: Any, spec: RecordField, ctx: _Context) -> Entries:
    if not isinstance(raw, dict):
        return ctx.unparseable(OBJECT, raw)
    dated = spec.kind is RecordKind.DATED_LABELS
    return tuple(
        KeyedEntry(position, str(label), ctx.date(value) if dated else freeze(value))
        for position, (label, value) in enumerate(raw.items())
    )


def _executive_change(raw: Any, ctx: _Context) -> Entries:
    if not isinstance(raw, dict):
        return ctx.unparseable(OBJECT, raw)
    return (
        KeyedEntry(0, "cause", ctx.member(raw, "cause")),
        KeyedEntry(1, "date", ctx.member_date(raw, "date")),
        KeyedEntry(2, "newExecutive", ctx.member_reference(raw, "newExecutive")),
    )


def _reference_list(raw: Any, spec: RecordField, ctx: _Context) -> Entries:
    targets = spec.targets if spec.targets is not None else frozenset()
    check_reference(ctx.state_type, ctx.field, raw, targets, True, ctx.index, ctx.collector)
    value = ctx.index.resolve_list(raw, targets)
    if isinstance(value, Unknown):
        ctx.unresolved_references += 1
    return (ItemEntry(0, value),)


def _labelled_references(raw: Any, spec: RecordField, ctx: _Context) -> Entries:
    """An object label -> one reference or a list of references; each value is checked and resolved in place."""
    if not isinstance(raw, dict):
        return ctx.unparseable(OBJECT, raw)
    targets = spec.targets if spec.targets is not None else frozenset()
    entries: list[RecordEntry] = []
    for position, (label, value) in enumerate(raw.items()):
        if isinstance(value, list):
            check_reference(ctx.state_type, ctx.field, value, targets, True, ctx.index, ctx.collector)
            resolved = ctx.index.resolve_list(value, targets)
            if isinstance(resolved, Unknown):
                ctx.unresolved_references += 1
        else:
            resolved = ctx.reference(value, targets, ctx.field)
        entries.append(KeyedEntry(position, str(label), resolved))
    return tuple(entries)


def _notification_log(raw: Any, ctx: _Context) -> Entries:
    """A list of notification objects; a member outside ``RECORD_ENTRY_MEMBERS`` is reported as ``Field[].member``.

    ``itemSummary`` is campaign content: it is kept as evidence and never logged.
    """
    if not isinstance(raw, list):
        return ctx.unparseable(ARRAY, raw)
    known = RECORD_ENTRY_MEMBERS.get(ctx.state_type, {}).get(ctx.field, frozenset())
    entries: list[RecordEntry] = []
    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            bad = ctx.unparseable(ARRAY_OF_OBJECTS, item)
            entries.append(NotificationEntry(position, bad, bad, bad, bad, bad, bad, bad, bad))
            continue
        for name, value in item.items():
            if name not in known:
                ctx.collector.field(ctx.state_type, entry_member_name(ctx.field, str(name)), value)
        entries.append(
            NotificationEntry(
                position,
                template=ctx.member(item, "templateName"),
                date=ctx.member_date(item, "dateTime"),
                summary=ctx.member(item, "itemSummary"),
                outcome=ctx.member(item, "outcome"),
                subject=ctx.member_reference(item, "gotoGameState"),
                alien_related=ctx.member(item, "alienRelated"),
                news_feed_factions=ctx.member_references(item, "newsFeedFactions"),
                summary_log_factions=ctx.member_references(item, "summaryLogFactions"),
            )
        )
    return tuple(entries)


def _entries(spec: RecordField, raw: Any, ctx: _Context) -> Entries:
    kind = spec.kind
    if kind is RecordKind.LEDGER:
        return _ledger(raw, ctx)
    if kind is RecordKind.DESTRUCTION_LOG:
        return _destruction_log(raw, ctx)
    if kind is RecordKind.NAME_LOG:
        return _name_log(raw, ctx)
    if kind in (RecordKind.DATED_REFERENCES, RecordKind.REFERENCE_VALUES):
        return _pair_map(raw, spec, ctx)
    if kind in (RecordKind.LABEL_VALUES, RecordKind.DATED_LABELS):
        return _label_map(raw, spec, ctx)
    if kind is RecordKind.EXECUTIVE_CHANGE:
        return _executive_change(raw, ctx)
    if kind is RecordKind.LABELLED_REFERENCES:
        return _labelled_references(raw, spec, ctx)
    if kind is RecordKind.NOTIFICATION_LOG:
        return _notification_log(raw, ctx)
    if kind is RecordKind.COUNTER:
        return (ItemEntry(0, freeze(raw)),)
    if kind is RecordKind.DATE:
        return (ItemEntry(0, ctx.date(raw)),)
    return _reference_list(raw, spec, ctx)


@dataclass
class _Totals:
    sets: int = 0
    missing: int = 0
    unparseable_dates: int = 0
    unresolved_references: int = 0
    shape_findings: int = 0
    kinds: dict[str, int] = field(default_factory=dict)


def decode_records(
    short_type: str,
    entries: tuple[StateEntry, ...],
    states: tuple[EntityState, ...],
    index: ReferenceIndex,
    source: str,
    collector: UnknownCollector,
) -> tuple[RecordSet, ...]:
    """One ``RecordSet`` per entity and record field of ``short_type``; ``states`` pair with ``entries``."""
    specs = RECORD_FIELDS.get(short_type)
    if not specs:
        return ()
    records: list[RecordSet] = []
    totals = _Totals()
    for entry, state in zip(entries, states, strict=True):
        base = entry_path(STATE_PREFIX + short_type, entry.index)
        for name, spec in specs.items():
            location = SourceLocation(source, short_type, entry.map_id, pointer_path(base, name))
            records.append(_record_set(spec, name, entry.value, state.ref, location, index, collector, totals))
    known_sets, known_entries = record_counts(records)
    logger.debug(
        "records normalized %s",
        log_fields(
            state_type=short_type,
            fields=len(specs),
            entities=len(entries),
            sets=totals.sets,
            known_sets=known_sets,
            missing=totals.missing,
            entries=known_entries,
            unparseable_dates=totals.unparseable_dates,
            unresolved_references=totals.unresolved_references,
            shape_findings=totals.shape_findings,
        ),
    )
    return tuple(records)


def _record_set(
    spec: RecordField,
    name: str,
    value: dict[str, Any],
    owner: EntityRef,
    location: SourceLocation,
    index: ReferenceIndex,
    collector: UnknownCollector,
    totals: _Totals,
) -> RecordSet:
    totals.sets += 1
    if name not in value:
        totals.missing += 1
        return RecordSet(owner, name, spec.kind, location)
    ctx = _Context(owner.state_type or "", name, index, collector)
    entries = _entries(spec, value[name], ctx)
    totals.unparseable_dates += ctx.unparseable_dates
    totals.unresolved_references += ctx.unresolved_references
    totals.shape_findings += ctx.shape_findings
    return RecordSet(owner, name, spec.kind, location, entries)
