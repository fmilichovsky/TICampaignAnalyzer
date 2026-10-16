"""Structured events; prose is intentionally not part of this model.

An event is a categorized claim about one transition between two snapshots (or about one save-carried
record entry). Its ``sources`` are the literal :class:`StateChange` objects that support it, so every
event traces back to the diff and, through each change's evidence, to the saves. Attributes are literal
copies of normalized values and never a reinterpretation of them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .changes import StateChange
from .entities import EntityRef
from .evidence import SourceLocation
from .values import FieldValue, Observed, Unknown, to_jsonable


class EventStatus(StrEnum):
    OBJECTIVE = "objective"
    INFERRED = "inferred"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Significance(StrEnum):
    """How much an event matters to a campaign history; independent of how certain it is (architecture 12).

    Assigned by the narrative stage (``tinarrative.narrative.significance``) from the event type and its
    context; the model only carries the value. ``SIGNIFICANCE_ORDER`` is the explicit ranking.
    """

    TRIVIAL = "trivial"
    """Routine churn or bookkeeping that no history level shows (recruit-pool councilors, log pruning)."""
    MINOR = "minor"
    """Worth a forensic log line, not a history entry; the default for an unclassified type."""
    MAJOR = "major"
    """A development a normal campaign history reports."""
    CAMPAIGN_DEFINING = "campaign_defining"
    """A development even a concise summary keeps."""

    @property
    def rank(self) -> int:
        return SIGNIFICANCE_ORDER.index(self)


SIGNIFICANCE_ORDER: tuple[Significance, ...] = (
    Significance.TRIVIAL,
    Significance.MINOR,
    Significance.MAJOR,
    Significance.CAMPAIGN_DEFINING,
)
"""Least to most significant; compare levels through ``Significance.rank``, never by enum declaration order."""


class DateBasis(StrEnum):
    """What ``Event.date`` is derived from."""

    INTERVAL = "interval"
    """The date of the snapshot that first shows the new state; the transition happened after ``not_before``."""
    RECORD = "record"
    """The date carried by a save-carried record entry cited among the sources."""


class SourceRole(StrEnum):
    PRIMARY = "primary"
    """The change the event is directly about; every event has at least one."""
    CORROBORATING = "corroborating"
    """A further literal change consistent with the primary one (for example the mirrored membership list)."""


@dataclass(frozen=True)
class EventSource:
    """One literal change cited by an event.

    ``member`` names the element of a membership change (or the key of a record entry) the event is about,
    when the change covers several. ``entry`` is the location of the cited record entry
    (``RecordSet.entry_location``) for record-backed sources.
    """

    change: StateChange
    role: SourceRole = SourceRole.PRIMARY
    member: FieldValue | None = None
    entry: SourceLocation | None = None

    @property
    def sort_key(self) -> tuple[int, tuple[str, int, int, str, str], str]:
        return (0 if self.role is SourceRole.PRIMARY else 1, self.change.sort_key, _member_key(self.member))

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "member": to_jsonable(self.member),
            "entry": self.entry.to_dict() if self.entry else None,
            "change": self.change.to_dict(),
        }


def _member_key(member: FieldValue | None) -> str:
    if isinstance(member, EntityRef):
        return str(member.entity_id)
    return json.dumps(to_jsonable(member), sort_keys=True, ensure_ascii=True)


@dataclass(frozen=True)
class Event:
    """A categorized, evidence-backed development; sorted deterministically on construction.

    ``date`` is the game date the event is dated by (``date_basis`` says how) and ``not_before`` the date of
    the earlier snapshot of the interval; either may be ``Unknown`` when a snapshot has no date. ``entities``
    are the affected entities (subject first by domain order after sorting), ``attributes`` literal values
    keyed by name. ``significance`` is assigned by the narrative stage; analyzers leave the default.
    """

    id: str
    event_type: str
    status: EventStatus
    confidence: Confidence
    date: Observed
    date_basis: DateBasis
    not_before: Observed
    sources: tuple[EventSource, ...]
    entities: tuple[EntityRef, ...]
    attributes: tuple[tuple[str, Observed], ...] = ()
    significance: Significance = Significance.MINOR

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(sorted(self.sources, key=lambda source: source.sort_key)))
        object.__setattr__(self, "entities", _unique(self.entities))
        object.__setattr__(self, "attributes", tuple(sorted(self.attributes, key=lambda item: item[0])))

    @property
    def sort_key(self) -> tuple[str, str, str]:
        """Dated events in date order (undated first), then by type and ID."""
        date = "" if isinstance(self.date, Unknown) else str(self.date)
        return (date, self.event_type, self.id)

    def attribute(self, name: str) -> Observed:
        for key, value in self.attributes:
            if key == name:
                return value
        return Unknown()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "status": self.status.value,
            "confidence": self.confidence.value,
            "significance": self.significance.value,
            "date": to_jsonable(self.date),
            "date_basis": self.date_basis.value,
            "not_before": to_jsonable(self.not_before),
            "entities": [to_jsonable(ref) for ref in self.entities],
            "attributes": {key: to_jsonable(value) for key, value in self.attributes},
            "sources": [source.to_dict() for source in self.sources],
        }


def _unique(refs: tuple[EntityRef, ...]) -> tuple[EntityRef, ...]:
    seen: set[EntityRef] = set()
    result: list[EntityRef] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            result.append(ref)
    return tuple(result)
