"""Objective state changes and the diff that collects them.

Deliberately literal: an entity *appeared* or *disappeared*; whether that is a creation, destruction, merge or
filter is an inference left to later stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .entities import EntityId
from .evidence import Evidence, SourceLocation
from .records import RecordEntry, entry_to_dict
from .snapshot import SaveSnapshot
from .values import FieldValue, Observed, to_jsonable


class ChangeKind(StrEnum):
    """How a change was established; the discriminator for ``StateChange.detail``."""

    APPEARED = "appeared"
    """The entity is present only in the later snapshot; ``field`` is ``None``."""
    DISAPPEARED = "disappeared"
    """The entity is present only in the earlier snapshot; ``field`` is ``None``."""
    VALUE = "value"
    """Both sides are known and compared as one atomic value (scalar, null, reference, nested structure)."""
    MEMBERSHIP = "membership"
    """Both sides are reference or name lists compared as multisets; order alone never counts."""
    MAP = "map"
    """Both sides are mappings; ``detail`` names the keys added, removed and changed."""
    UNKNOWN = "unknown"
    """At least one side is ``Unknown``, so the values cannot be compared structurally."""
    RECORDS = "records"
    """Both sides are known record sets; ``before``/``after`` are entry counts and ``detail`` lists the entries."""


@dataclass(frozen=True)
class MembershipDetail:
    """Members present on one side only, each sorted deterministically."""

    added: tuple[FieldValue, ...] = ()
    removed: tuple[FieldValue, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"added": [to_jsonable(m) for m in self.added], "removed": [to_jsonable(m) for m in self.removed]}


@dataclass(frozen=True)
class MapDetail:
    """Keys of a mapping that differ between the two sides, sorted."""

    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"added": list(self.added), "removed": list(self.removed), "changed": list(self.changed)}


@dataclass(frozen=True)
class RecordsDetail:
    """Entries on one side only, plus (keyed kinds) before/after pairs whose value changed for one key.

    A removed entry is reported literally: the diff never assumes a log is append-only.
    """

    added: tuple[RecordEntry, ...] = ()
    removed: tuple[RecordEntry, ...] = ()
    changed: tuple[tuple[RecordEntry, RecordEntry], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "added": [entry_to_dict(entry) for entry in self.added],
            "removed": [entry_to_dict(entry) for entry in self.removed],
            "changed": [{"before": entry_to_dict(a), "after": entry_to_dict(b)} for a, b in self.changed],
        }


@dataclass(frozen=True)
class StateChange:
    """One literal difference; ``field`` is ``None`` only for entity appearance or disappearance."""

    domain: str
    field: str | None
    before: Observed
    after: Observed
    evidence: Evidence
    entity_id: EntityId | None = None
    kind: ChangeKind = ChangeKind.VALUE
    detail: MembershipDetail | MapDetail | RecordsDetail | None = None

    @property
    def sort_key(self) -> tuple[str, int, int, str, str]:
        """Domain, then entity in natural order (``9`` before ``10``, names after numbers), then field."""
        entity = self.entity_id.sort_key if self.entity_id else ("", 0, 0, "")
        return (self.domain, entity[1], entity[2], entity[3], self.field or "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "field": self.field,
            "kind": self.kind.value,
            "before": to_jsonable(self.before),
            "after": to_jsonable(self.after),
            "detail": self.detail.to_dict() if self.detail else None,
            "description": self.evidence.description,
            "before_location": _location_dict(self.evidence.before_location),
            "after_location": _location_dict(self.evidence.after_location),
        }


def _location_dict(location: SourceLocation | None) -> dict[str, Any] | None:
    return location.to_dict() if location else None


@dataclass(frozen=True)
class StateDiff:
    before: SaveSnapshot
    after: SaveSnapshot
    changes: tuple[StateChange, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "changes", tuple(sorted(self.changes, key=lambda change: change.sort_key)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "before": self.before.source,
            "after": self.after.source,
            "before_date": to_jsonable(self.before.date),
            "after_date": to_jsonable(self.after.date),
            "changes": [change.to_dict() for change in self.changes],
        }
