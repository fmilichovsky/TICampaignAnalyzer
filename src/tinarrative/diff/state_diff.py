"""Literal comparison of two normalized snapshots: what differs, never why.

Equality is strict (``1 != 1.0``, ``True != 1``). A tuple of only ``EntityRef`` or only ``str`` is a member list,
compared as a multiset; any other tuple is atomic. ``Unknown`` on either side yields ``unknown`` and nothing is
inferred from the known side. An entity on one side only yields a single ``appeared``/``disappeared`` change.
Records are compared per owner and field: logs as multisets of entries, keyed records by key, scalars as fields.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Hashable
from dataclasses import fields as dataclass_fields

from ..log import fields as log_fields
from ..log import get_logger
from ..model.changes import ChangeKind, MapDetail, MembershipDetail, RecordsDetail, StateChange, StateDiff
from ..model.entities import EntityId, EntityRef
from ..model.evidence import Evidence, SourceLocation
from ..model.records import (
    KEYED_KINDS,
    SCALAR_KINDS,
    ItemEntry,
    KeyedEntry,
    NotificationEntry,
    RecordEntry,
    RecordSet,
    content_key,
    diff_key,
)
from ..model.snapshot import STATE_COLLECTIONS, CampaignMetadata, EntityState, ResearchState, SaveSnapshot
from ..model.values import FieldValue, FrozenMap, Observed, Unknown, to_jsonable

__all__ = ["ChangeKind", "MapDetail", "MembershipDetail", "RecordsDetail", "StateChange", "StateDiff", "diff_states"]

Detail = MembershipDetail | MapDetail | RecordsDetail | None

logger = get_logger(__name__)

CAMPAIGN_DOMAIN = "campaign"
"""Pseudo-domain for snapshot-level time and metadata values (no entity)."""
RESEARCH_DOMAIN = "research"
"""Pseudo-domain for the research singleton's fields (no entity)."""
SNAPSHOT_FIELDS = ("date", "campaign_day", "campaign_quarter")
"""``SaveSnapshot`` attributes compared under the campaign domain, before ``CampaignMetadata``."""


def diff_states(before: SaveSnapshot, after: SaveSnapshot) -> StateDiff:
    """Every literal difference between ``before`` and ``after``, sorted by domain, entity and field."""
    changes: list[StateChange] = []
    for name in STATE_COLLECTIONS:
        changes.extend(_collection_changes(name, before, after))
    changes.extend(_record_changes(before, after))
    changes.extend(_singleton_changes(before, after))
    return StateDiff(before=before, after=after, changes=tuple(changes))


def strict_equal(a: Observed, b: Observed) -> bool:
    """Type-aware structural equality: ``1 != 1.0`` and ``True != 1``, recursing into containers."""
    if type(a) is not type(b):
        return False
    if isinstance(a, tuple) and isinstance(b, tuple):
        return len(a) == len(b) and all(strict_equal(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, FrozenMap) and isinstance(b, FrozenMap):
        return len(a.items) == len(b.items) and all(
            ka == kb and strict_equal(va, vb) for (ka, va), (kb, vb) in zip(a.items, b.items, strict=True)
        )
    if isinstance(a, Unknown) and isinstance(b, Unknown):
        return a.reason is b.reason and strict_equal(a.raw, b.raw)
    return bool(a == b)


def is_member_list(value: Observed) -> bool:
    """A tuple of only ``EntityRef`` or only ``str`` elements; an empty tuple qualifies."""
    if not isinstance(value, tuple):
        return False
    return all(isinstance(item, EntityRef) for item in value) or all(isinstance(item, str) for item in value)


def order_key(value: FieldValue) -> tuple[int, str, int, str]:
    """Total deterministic order for members of a list: references naturally, then names, then the rest."""
    if isinstance(value, EntityRef):
        _domain, kind, length, key = value.entity_id.sort_key
        return (kind, value.entity_id.domain.value, length, key)
    if isinstance(value, str):
        return (2, "", 0, value)
    return (3, "", 0, json.dumps(to_jsonable(value), sort_keys=True, ensure_ascii=True))


def compare_values(before: Observed, after: Observed) -> tuple[ChangeKind, Detail] | None:
    """The kind and detail of the difference between two observed values, or ``None`` when equal."""
    if strict_equal(before, after):
        return None
    if isinstance(before, Unknown) or isinstance(after, Unknown):
        return (ChangeKind.UNKNOWN, None)
    if isinstance(before, tuple) and isinstance(after, tuple) and is_member_list(before + after):
        return _membership(before, after)
    if isinstance(before, FrozenMap) and isinstance(after, FrozenMap):
        return (ChangeKind.MAP, _map_detail(before, after))
    return (ChangeKind.VALUE, None)


def _membership(before: tuple[FieldValue, ...], after: tuple[FieldValue, ...]) -> tuple[ChangeKind, Detail] | None:
    before_counts = Counter(before)
    after_counts = Counter(after)
    added = tuple(sorted((after_counts - before_counts).elements(), key=order_key))
    removed = tuple(sorted((before_counts - after_counts).elements(), key=order_key))
    if not added and not removed:
        return None  # same members, different order: not a change
    return (ChangeKind.MEMBERSHIP, MembershipDetail(added=added, removed=removed))


def _map_detail(before: FrozenMap, after: FrozenMap) -> MapDetail:
    before_map = dict(before.items)
    after_map = dict(after.items)
    added = tuple(sorted(after_map.keys() - before_map.keys()))
    removed = tuple(sorted(before_map.keys() - after_map.keys()))
    changed = tuple(
        sorted(key for key in before_map.keys() & after_map.keys() if not strict_equal(before_map[key], after_map[key]))
    )
    return MapDetail(added=added, removed=removed, changed=changed)


def _describe(field: str, kind: ChangeKind, detail: Detail) -> str:
    if isinstance(detail, RecordsDetail):
        return (
            f"{field} records changed: {len(detail.added)} added, {len(detail.removed)} removed, "
            f"{len(detail.changed)} changed"
        )
    if isinstance(detail, MembershipDetail):
        return f"{field} membership changed: {len(detail.added)} added, {len(detail.removed)} removed"
    if isinstance(detail, MapDetail):
        return (
            f"{field} map changed: {len(detail.added)} added, {len(detail.removed)} removed, "
            f"{len(detail.changed)} changed"
        )
    if kind is ChangeKind.UNKNOWN:
        return f"{field} is unknown on at least one side"
    return f"{field} changed"


def _field_change(
    domain: str,
    field: str,
    before: Observed,
    after: Observed,
    before_location: SourceLocation | None,
    after_location: SourceLocation | None,
    entity_id: EntityId | None = None,
) -> StateChange | None:
    compared = compare_values(before, after)
    if compared is None:
        return None
    kind, detail = compared
    description = _describe(field, kind, detail)
    return StateChange(
        domain=domain,
        field=field,
        before=before,
        after=after,
        evidence=Evidence(domain, description, before, after, before_location, after_location),
        entity_id=entity_id,
        kind=kind,
        detail=detail,
    )


def _entity_changes(domain: str, before: EntityState, after: EntityState) -> list[StateChange]:
    names = sorted({name for name, _ in before.fields} | {name for name, _ in after.fields})
    changes: list[StateChange] = []
    for name in names:
        change = _field_change(
            domain, name, before.get(name), after.get(name), before.location, after.location, after.ref.entity_id
        )
        if change is not None:
            changes.append(change)
    return changes


def _presence_change(kind: ChangeKind, domain: str, state: EntityState, absent_source: str) -> StateChange:
    absent: SourceLocation | None = SourceLocation(save_id=absent_source)
    before: Observed
    after: Observed
    if kind is ChangeKind.APPEARED:
        before, after = Unknown(), state.ref
        before_location, after_location = absent, state.location
        description = "present only in the after snapshot"
    else:
        before, after = state.ref, Unknown()
        before_location, after_location = state.location, absent
        description = "absent from the after snapshot"
    return StateChange(
        domain=domain,
        field=None,
        before=before,
        after=after,
        evidence=Evidence(domain, description, before, after, before_location, after_location),
        entity_id=state.ref.entity_id,
        kind=kind,
    )


def _collection_changes(name: str, before: SaveSnapshot, after: SaveSnapshot) -> list[StateChange]:
    before_states: tuple[EntityState, ...] = getattr(before, name)
    after_states: tuple[EntityState, ...] = getattr(after, name)
    before_index = {state.ref.entity_id: state for state in before_states}
    after_index = {state.ref.entity_id: state for state in after_states}
    changes: list[StateChange] = []
    matched = 0
    for entity_id, state in before_index.items():
        domain = entity_id.domain.value
        other = after_index.get(entity_id)
        if other is None:
            changes.append(_presence_change(ChangeKind.DISAPPEARED, domain, state, after.source))
        else:
            matched += 1
            changes.extend(_entity_changes(domain, state, other))
    for entity_id, state in after_index.items():
        if entity_id not in before_index:
            changes.append(_presence_change(ChangeKind.APPEARED, entity_id.domain.value, state, before.source))
    if logger.isEnabledFor(logging.DEBUG):
        counts = Counter(change.kind.value for change in changes)
        logger.debug(
            "collection compared %s",
            log_fields(
                collection=name,
                before=len(before_states),
                after=len(after_states),
                matched=matched,
                **{kind.value: counts.get(kind.value, 0) for kind in ChangeKind},
            ),
        )
    return changes


def _side_count(entries: tuple[RecordEntry, ...] | Unknown) -> Observed:
    return entries if isinstance(entries, Unknown) else len(entries)


def _log_detail(before: tuple[RecordEntry, ...], after: tuple[RecordEntry, ...]) -> RecordsDetail:
    """Entries on one side only, as multisets of ``diff_key``, each kept in serialized order.

    The entries left on both sides are paired per key in serialized order; a pair whose content differs
    (a notification with the same key but another outcome) is ``changed``. For a kind whose key is its
    content no pair can differ.
    """
    before_keys = [diff_key(entry) for entry in before]
    after_keys = [diff_key(entry) for entry in after]
    before_counts = Counter(before_keys)
    after_counts = Counter(after_keys)
    added = _surplus(after, after_keys, after_counts - before_counts)
    removed = _surplus(before, before_keys, before_counts - after_counts)
    kept_before = _kept(before, before_keys, removed)
    changed: list[tuple[RecordEntry, RecordEntry]] = []
    for key, kept_after in _kept(after, after_keys, added).items():
        for old, new in zip(kept_before[key], kept_after, strict=True):
            if content_key(old) != content_key(new):
                changed.append((old, new))
    return RecordsDetail(
        added=tuple(entry for _, entry in added),
        removed=tuple(entry for _, entry in removed),
        changed=tuple(changed),
    )


def _surplus(
    entries: tuple[RecordEntry, ...], keys: list[Hashable], extra: Counter[Hashable]
) -> tuple[tuple[int, RecordEntry], ...]:
    """(position, entry) accounting for ``extra``; among equal keys the later ones, since logs grow at the end."""
    remaining = Counter(extra)
    picked: list[tuple[int, RecordEntry]] = []
    for position in reversed(range(len(entries))):
        key = keys[position]
        if remaining[key] > 0:
            remaining[key] -= 1
            picked.append((position, entries[position]))
    return tuple(reversed(picked))


def _kept(
    entries: tuple[RecordEntry, ...], keys: list[Hashable], picked: tuple[tuple[int, RecordEntry], ...]
) -> dict[Hashable, list[RecordEntry]]:
    """The notifications not ``picked``, grouped by their ``keys`` in serialized order.

    Only a notification's key is narrower than its content, so no other kept pair can differ.
    """
    skip = {position for position, _ in picked}
    groups: dict[Hashable, list[RecordEntry]] = {}
    for position, entry in enumerate(entries):
        if isinstance(entry, NotificationEntry) and position not in skip:
            groups.setdefault(keys[position], []).append(entry)
    return groups


def _keyed_detail(before: tuple[RecordEntry, ...], after: tuple[RecordEntry, ...]) -> RecordsDetail:
    """Entries matched by key; falls back to the multiset rule when a side repeats a key or is not keyed."""
    before_keyed = [entry for entry in before if isinstance(entry, KeyedEntry)]
    after_keyed = [entry for entry in after if isinstance(entry, KeyedEntry)]
    before_map = {entry.key: entry for entry in before_keyed}
    after_map = {entry.key: entry for entry in after_keyed}
    if (
        len(before_keyed) != len(before)
        or len(after_keyed) != len(after)
        or len(before_map) != len(before)
        or len(after_map) != len(after)
    ):
        return _log_detail(before, after)
    added = tuple(entry for entry in after_keyed if entry.key not in before_map)
    removed = tuple(entry for entry in before_keyed if entry.key not in after_map)
    changed = tuple(
        (before_map[entry.key], entry)
        for entry in after_keyed
        if entry.key in before_map and not strict_equal(before_map[entry.key].value, entry.value)
    )
    return RecordsDetail(added=added, removed=removed, changed=changed)


def _record_change(before: RecordSet, after: RecordSet) -> StateChange | None:
    domain = before.owner.entity_id.domain.value
    entity_id = before.owner.entity_id
    field = before.field
    if isinstance(before.entries, Unknown) or isinstance(after.entries, Unknown):
        return _field_change(
            domain,
            field,
            _side_count(before.entries),
            _side_count(after.entries),
            before.location,
            after.location,
            entity_id,
        )
    if before.kind in SCALAR_KINDS and after.kind in SCALAR_KINDS:
        first, second = _single_item(before.entries), _single_item(after.entries)
        if first is not None and second is not None:
            return _field_change(domain, field, first.value, second.value, before.location, after.location, entity_id)
    if before.kind in KEYED_KINDS and after.kind in KEYED_KINDS:
        detail = _keyed_detail(before.entries, after.entries)
    else:
        detail = _log_detail(before.entries, after.entries)
    if not (detail.added or detail.removed or detail.changed):
        return None
    counts: tuple[Observed, Observed] = (len(before.entries), len(after.entries))
    description = _describe(field, ChangeKind.RECORDS, detail)
    return StateChange(
        domain=domain,
        field=field,
        before=counts[0],
        after=counts[1],
        evidence=Evidence(domain, description, counts[0], counts[1], before.location, after.location),
        entity_id=entity_id,
        kind=ChangeKind.RECORDS,
        detail=detail,
    )


def _single_item(entries: tuple[RecordEntry, ...]) -> ItemEntry | None:
    if len(entries) == 1 and isinstance(entries[0], ItemEntry):
        return entries[0]
    return None


def _record_changes(before: SaveSnapshot, after: SaveSnapshot) -> list[StateChange]:
    """Record sets matched by owner and field; a set whose owner is on one side only is covered by that entity's
    ``appeared``/``disappeared`` change."""
    before_index = {(record.owner.entity_id, record.field): record for record in before.records}
    after_index = {(record.owner.entity_id, record.field): record for record in after.records}
    changes: list[StateChange] = []
    matched = 0
    for key, record in before_index.items():
        other = after_index.get(key)
        if other is None:
            continue
        matched += 1
        change = _record_change(record, other)
        if change is not None:
            changes.append(change)
    if logger.isEnabledFor(logging.DEBUG):
        counts = Counter(change.kind.value for change in changes)
        logger.debug(
            "records compared %s",
            log_fields(
                before=len(before.records),
                after=len(after.records),
                matched=matched,
                **{kind.value: counts.get(kind.value, 0) for kind in ChangeKind},
            ),
        )
    return changes


def _singleton_changes(before: SaveSnapshot, after: SaveSnapshot) -> list[StateChange]:
    """Campaign-level values; the normalizer records a location only for the research singleton."""
    changes: list[StateChange] = []
    before_save, after_save = SourceLocation(save_id=before.source), SourceLocation(save_id=after.source)
    for name in SNAPSHOT_FIELDS:
        change = _field_change(
            CAMPAIGN_DOMAIN, name, getattr(before, name), getattr(after, name), before_save, after_save
        )
        if change is not None:
            changes.append(change)
    for item in dataclass_fields(CampaignMetadata):
        change = _field_change(
            CAMPAIGN_DOMAIN,
            item.name,
            getattr(before.campaign, item.name),
            getattr(after.campaign, item.name),
            before_save,
            after_save,
        )
        if change is not None:
            changes.append(change)
    for item in dataclass_fields(ResearchState):
        if item.name == "location":
            continue
        change = _field_change(
            RESEARCH_DOMAIN,
            item.name,
            getattr(before.research, item.name),
            getattr(after.research, item.name),
            before.research.location or before_save,
            after.research.location or after_save,
        )
        if change is not None:
            changes.append(change)
    if logger.isEnabledFor(logging.DEBUG):
        counts = Counter(change.kind.value for change in changes)
        logger.debug(
            "singletons compared %s",
            log_fields(**{kind.value: counts.get(kind.value, 0) for kind in ChangeKind}),
        )
    return changes
