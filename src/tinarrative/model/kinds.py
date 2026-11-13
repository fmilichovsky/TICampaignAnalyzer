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
    TOP_GDP_TAKEOVER = "top_gdp_takeover"  # TODO(#362): temporary; the takeover's stake replaces it.
    """A narrative-event kind's rule: it promotes a takeover of a top-ranked economy."""
    TOP_RANK = "top_rank"  # TODO(#362): temporary; the nation's power share replaces it.
    """A narrative-event kind's rule: it promotes an event of a nation ranked in the top by GDP or strength."""
    ENTERED_TOP = "entered_top"
    """A narrative-event kind's rule: it raises the level when the nation entered the top of a space measure."""
    MILESTONE_TIER = "milestone_tier"
    """A narrative-event kind's rule: it sets the level from the curated tier of the completed template."""


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

    A ``narrative`` kind is one a narrative rule builds; ``base`` is ``None`` only for such a kind whose level its
    rule still sets. An emitter
    always passes every ``required`` attribute, its value possibly ``Unknown``; an attribute whose presence depends
    on the save is ``optional``. A narrative-event kind that ``digests_members`` groups the narrative events it cites
    as its members: the listing tells such a member as a digest under it. A narrative-event kind with
    ``exclusive_constituents`` cites them as its own: no narrative event of another kind may cite them (ADR-0002).
    """

    event_type: str
    template: Template
    base: Significance | None
    evidence: EvidenceRole
    required: frozenset[str]
    optional: frozenset[str] = frozenset()
    rule: Rule | None = None
    stake: Stake | None = None
    narrative: bool = False
    digests_members: bool = False
    exclusive_constituents: bool = False

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
