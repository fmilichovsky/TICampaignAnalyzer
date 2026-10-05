"""Provenance: where in which save a value was observed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .values import Observed


@dataclass(frozen=True, order=True)
class SourceLocation:
    save_id: str
    state_type: str | None = None
    map_id: int | None = None
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"save_id": self.save_id, "state_type": self.state_type, "map_id": self.map_id, "path": self.path}

    @property
    def provenance_key(self) -> str | None:
        """Factual provenance key such as ``TINationState:123``."""
        if self.state_type is None or self.map_id is None:
            return None
        return f"{self.state_type}:{self.map_id}"


@dataclass(frozen=True)
class Evidence:
    """Serialized before/after values with the locations they came from.

    A location is ``None`` when the value does not exist on that side (e.g. entity added or removed).
    """

    domain: str
    description: str
    before: Observed
    after: Observed
    before_location: SourceLocation | None = None
    after_location: SourceLocation | None = None
