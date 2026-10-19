"""Structured events; prose is intentionally not part of this model.

An event is a categorized claim about one transition between two snapshots (or about one save-carried
record entry). Its ``sources`` are the literal :class:`StateChange` objects that support it, so every
event traces back to the diff and, through each change's evidence, to the saves. Attributes are literal
copies of normalized values and never a reinterpretation of them. An inferred event also names the objective
events it was reconstructed from in ``constituents``, and its ``sources`` include every source they cite.
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


class Role(StrEnum):
    """What part an entity plays in a narrative event (architecture 11.2); ``ROLE_ORDER`` is the ranking."""

    ACTOR = "actor"
    TARGET = "target"
    BENEFICIARY = "beneficiary"
    LOSER = "loser"
    ASSISTING = "assisting"
    LOCATION = "location"
    BODY = "body"

    @property
    def rank(self) -> int:
        return ROLE_ORDER.index(self)


ROLE_ORDER: tuple[Role, ...] = (
    Role.ACTOR,
    Role.TARGET,
    Role.BENEFICIARY,
    Role.LOSER,
    Role.ASSISTING,
    Role.LOCATION,
    Role.BODY,
)
"""The order roles are listed in; compare through ``Role.rank``."""


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
    ``constituents`` are the IDs of the events an inferred event was reconstructed from (empty for an objective
    event); kept sorted and unique.

    A narrative event (architecture 11.2) also carries its span (``start`` and ``end``, each with its basis), whether
    it is ``open`` at the last save, the interval keys it spans and its entities by role; ``intervals`` is empty for
    every other event, and the other narrative fields then keep their defaults. ``roles`` are kept sorted and unique.
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
    constituents: tuple[str, ...] = ()
    start: Observed = None
    start_basis: DateBasis | None = None
    end: Observed = None
    end_basis: DateBasis | None = None
    open: bool = False
    intervals: tuple[str, ...] = ()
    roles: tuple[tuple[Role, EntityRef], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(sorted(self.sources, key=lambda source: source.sort_key)))
        object.__setattr__(self, "constituents", tuple(sorted(set(self.constituents))))
        object.__setattr__(self, "entities", _unique(self.entities))
        object.__setattr__(self, "attributes", tuple(sorted(self.attributes, key=lambda item: item[0])))
        roles = sorted(set(self.roles), key=lambda item: (item[0].rank, item[1].entity_id.sort_key))
        object.__setattr__(self, "roles", tuple(roles))

    @property
    def is_narrative(self) -> bool:
        return bool(self.intervals)

    @property
    def sort_key(self) -> tuple[str, str, str]:
        """Dated events in date order (undated first), then by type and ID; a narrative event is placed by its start,
        since a history lists a development where it begins."""
        placed = self.start if self.is_narrative else self.date
        date = "" if isinstance(placed, Unknown) else str(placed)
        return (date, self.event_type, self.id)

    def attribute(self, name: str) -> Observed:
        for key, value in self.attributes:
            if key == name:
                return value
        return Unknown()

    def to_dict(self) -> dict[str, Any]:
        """The event as JSON; the narrative fields only for a narrative event."""
        document = {
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
            "constituents": list(self.constituents),
        }
        if self.is_narrative:
            document.update(
                {
                    "start": to_jsonable(self.start),
                    "start_basis": None if self.start_basis is None else self.start_basis.value,
                    "end": to_jsonable(self.end),
                    "end_basis": None if self.end_basis is None else self.end_basis.value,
                    "open": self.open,
                    "intervals": list(self.intervals),
                    "roles": [{"role": role.value, "entity": to_jsonable(ref)} for role, ref in self.roles],
                }
            )
        return document


def _unique(refs: tuple[EntityRef, ...]) -> tuple[EntityRef, ...]:
    seen: set[EntityRef] = set()
    result: list[EntityRef] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            result.append(ref)
    return tuple(result)
