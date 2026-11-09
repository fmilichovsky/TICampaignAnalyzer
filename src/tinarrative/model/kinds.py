"""The event kind contract: what one declaration of an event type holds (ADR-0001)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from .events import Event, Significance


class Rule(StrEnum):
    """A context rule: sets an event's level from what the event itself says, overriding its base level."""

    COUNCILOR_PRESENCE = "councilor_presence"
    RELATION_CHANGED = "relation_changed"
    CLAIMS_CHANGED = "claims_changed"
    EXECUTIVE_CHANGE = "executive_change"
    STATISTIC_SHIFTED = "statistic_shifted"
    POPULATION_CHANGED = "population_changed"
    SPACE_ASSETS_CHANGED = "space_assets_changed"
    ARMY_PRESENCE = "army_presence"
    COMPLETION = "completion"


class StakeMeasure(StrEnum):
    """The world total a stake is a share of; each is a ``config.ReferenceSettings`` key."""

    POWER = "power"
    POPULATION = "population"
    ORGANIZATION = "organization"


class Stake(StrEnum):
    """What an event's score scales with: a stake measure and the entities of the event whose share it is."""

    NATION = "nation"
    BELLIGERENTS = "belligerents"
    TERRITORY = "territory"
    CONTROL_POINT = "control_point"
    ORGANIZATION = "organization"


class EvidenceRole(StrEnum):
    """Whether the narrator package lists an event of the kind when a narrative event cites it."""

    EVIDENCE = "evidence"
    """States a fact its narrative event does not carry: a record date, a place, a destruction."""
    BOOKKEEPING = "bookkeeping"
    """Already stated in summary form by the narrative event that cites it."""


Template = Callable[[Event], str]


@dataclass(frozen=True)
class EventKind:
    """The single declaration of one event type.

    ``base`` is ``None`` only for a narrative-event kind, whose level is set by the rule that emits it. An emitter
    always passes every ``required`` attribute, its value possibly ``Unknown``; an attribute whose presence depends
    on the save is ``optional``.
    """

    event_type: str
    template: Template
    base: Significance | None
    evidence: EvidenceRole
    required: frozenset[str]
    optional: frozenset[str] = frozenset()
    rule: Rule | None = None
    stake: Stake | None = None

    @property
    def is_prefix(self) -> bool:
        """Whether the declared type ends in ``*`` and covers every type with that prefix (names the save supplies)."""
        return self.event_type.endswith("*")

    @property
    def prefix(self) -> str:
        return self.event_type.removesuffix("*")

    def __post_init__(self) -> None:
        shared = self.required & self.optional
        if shared:
            raise ValueError(f"kind {self.event_type}: {sorted(shared)} are both required and optional")
