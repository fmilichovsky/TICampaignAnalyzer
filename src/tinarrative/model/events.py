"""Structured events: categorized claims backed by literal state changes; prose is not part of this model.

Attributes are literal copies of normalized values, never a reinterpretation. An inferred event's ``sources``
include every source of its ``constituents``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

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
    """How much an event matters to a campaign history; independent of confidence (architecture 12).

    Assigned by ``tinarrative.narrative.significance``; ``SIGNIFICANCE_ORDER`` is the ranking. Each level is a fixed
    band of the 0-100 ``Event.score`` (``SCORE_BANDS``).
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

    @property
    def band(self) -> tuple[int, int]:
        """The lowest and highest score of this level, both inclusive."""
        return SCORE_BANDS[self]

    @property
    def base(self) -> int:
        """The band's midpoint: the score of an event whose type alone decides its level."""
        low, high = self.band
        return (low + high) // 2

    @classmethod
    def of(cls, score: int) -> Significance:
        """The level whose band holds ``score``; ``ValueError`` outside 0-100 or for a non-integer."""
        if isinstance(score, bool) or not isinstance(score, int):
            raise ValueError(f"a significance score is an integer, not {score!r}")
        for level, (low, high) in SCORE_BANDS.items():
            if low <= score <= high:
                return level
        raise ValueError(f"a significance score runs 0-100, not {score}")


SIGNIFICANCE_ORDER: tuple[Significance, ...] = (
    Significance.TRIVIAL,
    Significance.MINOR,
    Significance.MAJOR,
    Significance.CAMPAIGN_DEFINING,
)
"""Least to most significant; compare levels through ``Significance.rank``, never by enum declaration order."""

SCORE_BANDS: Mapping[Significance, tuple[int, int]] = {
    Significance.TRIVIAL: (0, 24),
    Significance.MINOR: (25, 49),
    Significance.MAJOR: (50, 74),
    Significance.CAMPAIGN_DEFINING: (75, 100),
}
"""Fixed, so an event's score and level can never disagree; the scaling that moves a score is configured."""

UNSCORED: Final = -1
"""The ``Event.score`` default: replaced by the base of the event's level on construction."""


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

    ``not_before`` is the date of the interval's earlier snapshot; it and ``date`` may be ``Unknown``.
    ``significance`` and ``score`` are set by the narrative stage; analyzers leave the defaults. A score left
    ``UNSCORED`` becomes the level's base, and one outside the level's band raises ``ValueError``. Only a narrative
    event (architecture 11.2) has non-empty ``intervals``; for every other event the span, ``open`` and ``roles``
    fields keep their defaults.
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
    score: int = UNSCORED
    constituents: tuple[str, ...] = ()
    start: Observed = None
    start_basis: DateBasis | None = None
    end: Observed = None
    end_basis: DateBasis | None = None
    open: bool = False
    intervals: tuple[str, ...] = ()
    roles: tuple[tuple[Role, EntityRef], ...] = ()

    def __post_init__(self) -> None:
        if self.score == UNSCORED:
            object.__setattr__(self, "score", self.significance.base)
        elif Significance.of(self.score) is not self.significance:
            raise ValueError(f"event {self.id}: score {self.score} is outside the {self.significance} band")
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
        """Date (undated first), type, ID; a narrative event is placed by its start, where a history lists it."""
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
            "score": self.score,
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
