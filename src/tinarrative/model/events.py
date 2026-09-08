"""Structured events; prose is intentionally not part of this model."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .entities import EntityRef
from .evidence import Evidence


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
    sources: list[Evidence] = field(default_factory=list)
    entities: list[EntityRef] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
