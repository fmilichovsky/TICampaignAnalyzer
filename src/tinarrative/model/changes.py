"""Literal state transitions produced by the diff layer."""

from dataclasses import dataclass
from typing import Any

from .evidence import Evidence


@dataclass(frozen=True)
class StateChange:
    domain: str
    field: str
    before: Any
    after: Any
    evidence: Evidence
    entity_id: str | None = None
