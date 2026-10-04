"""Objective state changes and the diff that collects them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .entities import EntityId
from .evidence import Evidence, SourceLocation
from .snapshot import SaveSnapshot
from .values import Observed, to_jsonable


@dataclass(frozen=True)
class StateChange:
    domain: str
    field: str
    before: Observed
    after: Observed
    evidence: Evidence
    entity_id: EntityId | None = None

    @property
    def sort_key(self) -> tuple[str, str, str]:
        return (self.domain, str(self.entity_id) if self.entity_id else "", self.field)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "field": self.field,
            "before": to_jsonable(self.before),
            "after": to_jsonable(self.after),
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
            "changes": [change.to_dict() for change in self.changes],
        }
