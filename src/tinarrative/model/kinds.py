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
    TOP_GDP_NATION = "top_gdp_nation"  # TODO(#362): temporary; the nation's power share replaces it.
    """A narrative-event kind's rule: it promotes an event about a top-ranked economy."""
    BAND_SHIFT = "band_shift"  # TODO(#362): the top-GDP promotion inside it is temporary.
    """A narrative-event kind's rule: statistics that are always major, severe unrest, cohesion extremes and two bands
    crossed are major, others minor; a top-ranked economy is one level up."""
    COLLAPSE_AFTER_STRIKES = "collapse_after_strikes"
    """A narrative-event kind's rule: a population collapse of nuked regions, or with nuclear strikes, is campaign
    defining."""
    LARGE_ARSENAL_DISARMED = "large_arsenal_disarmed"
    """A narrative-event kind's rule: dismantling a large arsenal is campaign defining."""
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
    TARGETS = "targets"
    """A narrative-event stake: the power share of the nations in the target role."""
    WAR_SIDES = "war_sides"
    """A narrative-event stake: the power share of every attacker and defender, with the nuclear bonus when both sides
    hold warheads."""
    MEMBERS = "members"
    """A narrative-event stake: the power share of every nation that was a member."""
    REGIONS = "regions"
    """A narrative-event stake: the population share of the regions the event lists."""
    INDEPENDENT_NATION = "independent_nation"
    """A narrative-event stake: the power share of the nation that became independent."""


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

    A ``narrative`` kind is one a narrative rule builds. Every kind declares its ``base`` level; a narrative rule
    chooses none. An emitter always passes every ``required`` attribute, its value possibly ``Unknown``; an
    attribute whose presence depends on the save is ``optional``. A narrative-event kind that ``digests_members``
    groups the narrative events it cites as its members: the listing tells such a member as a digest under it. A
    narrative-event kind with ``exclusive_constituents`` cites them as its own: no narrative event of another kind
    may cite them (ADR-0002).
    """

    event_type: str
    template: Template
    base: Significance
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
