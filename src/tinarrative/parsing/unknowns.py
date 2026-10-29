"""Report save structures the parser does not describe, without recording their content.

Findings hold only JSON type labels and identifier-like member names, never values, IDs or paths, so they can be
logged and committed to ``docs/game-data-notes/unknowns/``. They never change a ``SaveSnapshot``.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..identity import ENTITY_DOMAINS, STATE_PREFIX, read_id_value
from ..log import fields as log_fields
from ..log import get_logger
from ..model.entities import EntityDomain
from .containers import decode_container
from .errors import UnsupportedSaveShapeError
from .fields import (
    ACKNOWLEDGED_FIELDS,
    KNOWN_FIELDS,
    PAIR_MAP_FIELDS,
    REFERENCE_FIELDS,
    SINGLETON_FIELDS,
    UNTRACKED_REFERENCE_TARGETS,
    record_reference_domains,
)
from .inventory import KNOWN_STATE_TYPES, short_state_type
from .raw_save import ENVELOPE_KEYS
from .references import ExpectedDomains, ReferenceIndex, as_domains

logger = get_logger(__name__)

MAX_OBJECT_KEYS = 32
"""Most member names kept per shape; more sets ``object_keys_omitted``."""
MAX_ARRAY_ITEMS = 64
"""Most list elements inspected per observed array."""
_MAX_TRACKED_KEYS = 4 * MAX_OBJECT_KEYS
_IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_]*$")
"""Member names that look like serialized field names; map IDs and free text never match."""

PAIR_MAP_VIOLATION = "pair_map_violation"
"""``detail`` of a container that does not follow the documented pair-map shape."""
ARRAY_OF_REFERENCES = "array_of_references"
REFERENCE_OBJECT = "reference_object"
"""``field_shape`` details for a reference field that is not a list, or a reference that is not ``{"value": id}``."""
PAIR_MAP = "pair_map"
"""``field_shape`` detail: expected ``{}`` or ``Key``/``Value`` objects (with distinct keys in an entity field)."""


class UnknownKind(StrEnum):
    STATE_TYPE = "unknown_state_type"
    """A ``gamestates`` key outside ``KNOWN_STATE_TYPES``; ``occurrences`` is its entry count."""
    FIELD = "unknown_field"
    """A ``Value`` member of a scanned state type outside ``KNOWN_FIELDS``; ``occurrences`` counts entities."""
    ENVELOPE_KEY = "unknown_envelope_key"
    """A root member outside ``ENVELOPE_KEYS``; ``state_type`` is empty."""
    FIELD_SHAPE = "unexpected_field_shape"
    """A known field whose value does not have the documented shape; ``detail`` names the expected shape."""
    REFERENCE_DOMAIN = "unexpected_reference_domain"
    """A reference whose ID exists in the save under a state type outside the expected domains (``detail``)."""
    SINGLETON_COUNT = "unexpected_singleton_count"
    """A singleton state type with more than one entry; ``occurrences`` is the entry count."""
    CONTAINER_SHAPE = "unexpected_container_shape"
    """A pair-map violation in a domain container the reference index had to skip."""


def _type_label(value: Any) -> str:
    """JSON type vocabulary shared with ``tinarrative.log.shape`` and the ``inspect`` report."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list | tuple):
        return "array"
    if isinstance(value, Mapping):
        return "object"
    return type(value).__name__


def _bounded(keys: set[str]) -> tuple[tuple[str, ...], bool]:
    ordered = tuple(sorted(keys))
    return ordered[:MAX_OBJECT_KEYS], len(ordered) > MAX_OBJECT_KEYS


@dataclass(frozen=True)
class ShapeSummary:
    """Bounded, content-free description of every value observed for one finding.

    All tuples are sorted and deduplicated, so summaries compare equal regardless of observation order.
    """

    types: tuple[str, ...] = ()
    object_keys: tuple[str, ...] = ()
    object_keys_omitted: bool = False
    array_item_types: tuple[str, ...] = ()
    array_item_keys: tuple[str, ...] = ()

    def merge(self, other: ShapeSummary) -> ShapeSummary:
        object_keys, truncated = _bounded(set(self.object_keys) | set(other.object_keys))
        item_keys, item_truncated = _bounded(set(self.array_item_keys) | set(other.array_item_keys))
        return ShapeSummary(
            types=tuple(sorted(set(self.types) | set(other.types))),
            object_keys=object_keys,
            object_keys_omitted=self.object_keys_omitted or other.object_keys_omitted or truncated or item_truncated,
            array_item_types=tuple(sorted(set(self.array_item_types) | set(other.array_item_types))),
            array_item_keys=item_keys,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "types": list(self.types),
            "object_keys": list(self.object_keys),
            "object_keys_omitted": self.object_keys_omitted,
            "array_item_types": list(self.array_item_types),
            "array_item_keys": list(self.array_item_keys),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ShapeSummary:
        return cls(
            types=tuple(data.get("types", ())),
            object_keys=tuple(data.get("object_keys", ())),
            object_keys_omitted=bool(data.get("object_keys_omitted", False)),
            array_item_types=tuple(data.get("array_item_types", ())),
            array_item_keys=tuple(data.get("array_item_keys", ())),
        )


class _ShapeAccumulator:
    def __init__(self) -> None:
        self.types: set[str] = set()
        self.object_keys: set[str] = set()
        self.omitted = False
        self.item_types: set[str] = set()
        self.item_keys: set[str] = set()

    def _keys(self, target: set[str], value: Mapping[str, Any]) -> None:
        for key in value:
            if not isinstance(key, str) or not _IDENTIFIER.match(key):
                self.omitted = True
            elif len(target) < _MAX_TRACKED_KEYS:
                target.add(key)
            elif key not in target:
                self.omitted = True

    def observe(self, value: Any) -> None:
        self.types.add(_type_label(value))
        if isinstance(value, Mapping):
            self._keys(self.object_keys, value)
        elif isinstance(value, list | tuple):
            for item in value[:MAX_ARRAY_ITEMS]:
                self.item_types.add(_type_label(item))
                if isinstance(item, Mapping):
                    self._keys(self.item_keys, item)

    def freeze(self) -> ShapeSummary:
        object_keys, truncated = _bounded(self.object_keys)
        item_keys, item_truncated = _bounded(self.item_keys)
        return ShapeSummary(
            types=tuple(sorted(self.types)),
            object_keys=object_keys,
            object_keys_omitted=self.omitted or truncated or item_truncated,
            array_item_types=tuple(sorted(self.item_types)),
            array_item_keys=item_keys,
        )


FindingKey = tuple[str, str, str, str]
"""``(kind, state_type, field or "", detail or "")``: the identity of a finding across saves and scans."""


@dataclass(frozen=True)
class UnknownFinding:
    """One kind of unknown structure met in one save.

    ``state_type`` is the short type (``STATE_PREFIX`` stripped) or the full ``gamestates`` key when it has no
    prefix, and ``""`` for envelope keys. ``detail`` is a short code-like qualifier, never a message.
    """

    kind: UnknownKind
    state_type: str
    field: str | None
    detail: str | None
    occurrences: int
    shape: ShapeSummary | None

    @property
    def key(self) -> FindingKey:
        return (self.kind.value, self.state_type, self.field or "", self.detail or "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "state_type": self.state_type,
            "field": self.field,
            "detail": self.detail,
            "occurrences": self.occurrences,
            "shape": self.shape.to_dict() if self.shape is not None else None,
        }


@dataclass(frozen=True)
class UnknownReport:
    """Every finding of one save, sorted by key."""

    findings: tuple[UnknownFinding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(sorted(self.findings, key=lambda finding: finding.key)))

    @property
    def total(self) -> int:
        return len(self.findings)

    def counts(self) -> dict[str, int]:
        """Findings per kind, every kind present (zero when none)."""
        counter = Counter(finding.kind.value for finding in self.findings)
        return {kind.value: counter.get(kind.value, 0) for kind in UnknownKind}

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "counts": self.counts(),
            "findings": [finding.to_dict() for finding in self.findings],
        }


class _Accumulator:
    def __init__(self, kind: UnknownKind, state_type: str, field: str | None, detail: str | None, shaped: bool):
        self.kind = kind
        self.state_type = state_type
        self.field = field
        self.detail = detail
        self.occurrences = 0
        self.shape = _ShapeAccumulator() if shaped else None

    def add(self, count: int, value: Any = None, *, observe: bool = False) -> None:
        self.occurrences += count
        if observe and self.shape is not None:
            self.shape.observe(value)

    def freeze(self) -> UnknownFinding:
        return UnknownFinding(
            kind=self.kind,
            state_type=self.state_type,
            field=self.field,
            detail=self.detail,
            occurrences=self.occurrences,
            shape=self.shape.freeze() if self.shape is not None else None,
        )


class UnknownCollector:
    """Accumulates findings while one save is normalized; ``report()`` freezes them."""

    def __init__(self) -> None:
        self._entries: dict[FindingKey, _Accumulator] = {}
        self._entities_with_unknown_fields: Counter[str] = Counter()

    def _entry(
        self, kind: UnknownKind, state_type: str, field: str | None, detail: str | None, *, shaped: bool
    ) -> _Accumulator:
        key: FindingKey = (kind.value, state_type, field or "", detail or "")
        entry = self._entries.get(key)
        if entry is None:
            entry = self._entries[key] = _Accumulator(kind, state_type, field, detail, shaped)
        return entry

    def state_type(self, key: str, container: Any) -> None:
        """A ``gamestates`` key outside the inventory; its entries' member names become the shape."""
        state_type = short_state_type(key)
        try:
            entries = decode_container(key, container)
        except UnsupportedSaveShapeError:
            entry = self._entry(UnknownKind.STATE_TYPE, state_type, None, PAIR_MAP_VIOLATION, shaped=True)
            entry.add(1, container, observe=True)
            return
        entry = self._entry(UnknownKind.STATE_TYPE, state_type, None, None, shaped=True)
        if not entries:
            entry.add(0, container, observe=True)
        for item in entries:
            entry.add(1, item.value, observe=True)

    def envelope_key(self, key: str, value: Any) -> None:
        self._entry(UnknownKind.ENVELOPE_KEY, "", key, None, shaped=True).add(1, value, observe=True)

    def field(self, state_type: str, name: str, value: Any) -> None:
        self._entry(UnknownKind.FIELD, state_type, name, None, shaped=True).add(1, value, observe=True)

    def field_shape(self, state_type: str, name: str, expected: str, value: Any) -> None:
        self._entry(UnknownKind.FIELD_SHAPE, state_type, name, expected, shaped=True).add(1, value, observe=True)

    def reference_domain(self, state_type: str, name: str, target_state_type: str) -> None:
        self._entry(UnknownKind.REFERENCE_DOMAIN, state_type, name, target_state_type, shaped=False).add(1)

    def singleton_count(self, state_type: str, entries: int) -> None:
        self._entry(UnknownKind.SINGLETON_COUNT, state_type, None, None, shaped=False).add(entries)

    def container_shape(self, state_type: str) -> None:
        self._entry(UnknownKind.CONTAINER_SHAPE, state_type, None, PAIR_MAP_VIOLATION, shaped=False).add(1)

    def entity_with_unknown_fields(self, state_type: str) -> None:
        self._entities_with_unknown_fields[state_type] += 1

    def field_count(self, state_type: str) -> int:
        """Distinct unknown field names seen on one state type."""
        return sum(1 for key in self._entries if key[0] == UnknownKind.FIELD.value and key[1] == state_type)

    def report(self) -> UnknownReport:
        return UnknownReport(tuple(entry.freeze() for entry in self._entries.values()))

    def log_summary(self) -> None:
        """One INFO line of counts; per-type DEBUG aggregates name no field."""
        counts = self.report().counts()
        logger.info(
            "unknown structures %s",
            log_fields(
                total=sum(counts.values()),
                state_types=counts[UnknownKind.STATE_TYPE.value],
                fields=counts[UnknownKind.FIELD.value],
                envelope_keys=counts[UnknownKind.ENVELOPE_KEY.value],
                field_shapes=counts[UnknownKind.FIELD_SHAPE.value],
                reference_domains=counts[UnknownKind.REFERENCE_DOMAIN.value],
                singletons=counts[UnknownKind.SINGLETON_COUNT.value],
                containers=counts[UnknownKind.CONTAINER_SHAPE.value],
            ),
        )
        for state_type, entities in sorted(self._entities_with_unknown_fields.items()):
            logger.debug(
                "unknown fields %s",
                log_fields(state_type=state_type, fields=self.field_count(state_type), entities=entities),
            )


def scan_envelope(root: Mapping[str, Any], collector: UnknownCollector) -> None:
    """Report root members outside the documented envelope and ``gamestates`` keys outside the inventory."""
    for key, value in root.items():
        if key not in ENVELOPE_KEYS:
            collector.envelope_key(key, value)
    gamestates = root.get("gamestates")
    if isinstance(gamestates, Mapping):
        for key, container in gamestates.items():
            if key not in KNOWN_STATE_TYPES:
                collector.state_type(key, container)


def check_reference(
    state_type: str,
    name: str,
    raw: Any,
    expected: ExpectedDomains,
    is_list: bool,
    index: ReferenceIndex,
    collector: UnknownCollector,
) -> None:
    """Report a reference whose shape or target type is not the documented one; resolution is unchanged.

    ``name`` is the field, or ``Field.member`` for a reference inside a record entry. A target type listed in
    ``UNTRACKED_REFERENCE_TARGETS`` for ``name`` is known to have no domain and is not reported.
    """
    if is_list:
        if not isinstance(raw, list):
            collector.field_shape(state_type, name, ARRAY_OF_REFERENCES, raw)
            return
        items: list[Any] = raw
    else:
        items = [raw]
    domains = as_domains(expected)
    for item in items:
        if item is None and not is_list:
            continue
        map_id = read_id_value(item)
        if map_id is None:
            collector.field_shape(state_type, name, REFERENCE_OBJECT, item)
            continue
        owner = index.owner_state_type(map_id, domains)
        if owner is not None and owner not in UNTRACKED_REFERENCE_TARGETS.get(name, frozenset()):
            collector.reference_domain(state_type, name, owner)


def scan_fields(state_type: str, value: Mapping[str, Any], collector: UnknownCollector) -> None:
    """Report the members of one ``Value`` object that the schema for ``state_type`` does not describe."""
    known = KNOWN_FIELDS.get(state_type)
    if known is None:
        return
    found = False
    for name, item in value.items():
        if name not in known:
            collector.field(state_type, name, item)
            found = True
    if found:
        collector.entity_with_unknown_fields(state_type)


_INDEXED_STATE_TYPES: frozenset[str] = frozenset(
    short_type for strategy in ENTITY_DOMAINS for short_type in strategy.state_types
)
_DOMAIN_OF_STATE_TYPE = {
    short_type: strategy.domain for strategy in ENTITY_DOMAINS for short_type in strategy.state_types
}


def is_known(key: FindingKey) -> bool:
    """Whether the current schema can no longer produce the finding with this key; the registry prunes those.

    An unrecognized kind is never "known".
    """
    kind, state_type, field, detail = key
    if kind == UnknownKind.STATE_TYPE:
        return state_type in KNOWN_STATE_TYPES or STATE_PREFIX + state_type in KNOWN_STATE_TYPES
    if kind == UnknownKind.ENVELOPE_KEY:
        return field in ENVELOPE_KEYS
    if kind == UnknownKind.FIELD:
        known = KNOWN_FIELDS.get(state_type)
        return known is None or field in known
    if kind == UnknownKind.FIELD_SHAPE:
        known = KNOWN_FIELDS.get(state_type)
        return known is None or field not in known or field in ACKNOWLEDGED_FIELDS.get(state_type, {})
    if kind == UnknownKind.REFERENCE_DOMAIN:
        if detail in UNTRACKED_REFERENCE_TARGETS.get(field, frozenset()):
            return True
        expected = REFERENCE_FIELDS.get(state_type, {}).get(field)
        keys = PAIR_MAP_FIELDS.get(state_type, {}).get(field)
        if expected is not None:
            domains: frozenset[EntityDomain] | None = as_domains(expected[0])
        elif keys is not None:
            domains = as_domains(keys)
        else:
            domains = record_reference_domains(state_type, field)
        if domains is None:
            return True
        target_domain = _DOMAIN_OF_STATE_TYPE.get(detail)
        return target_domain is not None and target_domain in domains
    if kind == UnknownKind.SINGLETON_COUNT:
        return state_type not in SINGLETON_FIELDS
    if kind == UnknownKind.CONTAINER_SHAPE:
        return state_type not in _INDEXED_STATE_TYPES
    return False
