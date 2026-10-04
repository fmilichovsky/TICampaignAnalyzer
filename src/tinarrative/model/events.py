"""Structured events; prose is intentionally not part of this model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .entities import EntityRef
from .evidence import Evidence
from .values import FieldValue


class EventStatus(StrEnum):
    OBJECTIVE = "objective"
    INFERRED = "inferred"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class Event:
    id: str
    date: str
    event_type: str
    status: EventStatus
    confidence: Confidence
    sources: tuple[Evidence, ...] = ()
    entities: tuple[EntityRef, ...] = ()
    attributes: tuple[tuple[str, FieldValue], ...] = ()
