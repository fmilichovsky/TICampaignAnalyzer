"""The event kind contract: what one declaration of an event type holds (ADR-0001)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from .events import Event, Significance


class Rule(StrEnum):
    """A context rule: sets an event's level from what the event itself says, overriding its base level."""

    COUNCILOR_PRESENCE = "councilor_presence"
    RELATION_CHANGED = "relation_changed"
    CLAIMS_CHANGED = "claims_changed"
    EXECUTIVE_CHANGE = "executive_change"
    POPULATION_CHANGED = "population_changed"
    SPACE_ASSETS_CHANGED = "space_assets_changed"
    ARMY_PRESENCE = "army_presence"
    COMPLETION = "completion"
    BAND_SHIFT = "band_shift"
    """A narrative-event kind's rule: statistics that are always major, severe unrest, cohesion extremes and two bands
    crossed are major, others minor."""
    COLLAPSE_AFTER_STRIKES = "collapse_after_strikes"
    """A narrative-event kind's rule: a population collapse of nuked regions, or with nuclear strikes, is campaign
    defining."""
    ENTERED_TOP = "entered_top"
    """A narrative-event kind's rule: it raises the level when the nation entered the top of a space measure."""
    MILESTONE_TIER = "milestone_tier"
    """A narrative-event kind's rule: it sets the level from the curated tier of the completed template."""


class Measure(StrEnum):
    """The world total a share is taken of. Each measure's label and description are its entry in
    ``narrative.measures.MEASURES``."""

    POWER = "power"
    POPULATION = "population"
    ORGANIZATION = "organization"
    HAB = "hab"
    FLEET = "fleet"
    BATTLE = "battle"
    SPACE_LOSS = "space_loss"
    FACTION = "faction"
    NUCLEAR = "nuclear"


class ShareOf(StrEnum):
    """What an event's score scales with: a measure and the entities of the event whose share it is."""

    NATION = "nation"
    BELLIGERENTS = "belligerents"
    TERRITORY = "territory"
    CONTROL_POINT = "control_point"
    ORGANIZATION = "organization"
    ACTOR = "actor"
    """A narrative-event share: the power share of the nation in the actor role, the nation the event is about."""
    TARGETS = "targets"
    """A narrative-event share: the power share of the nations in the target role."""
    WAR_SIDES = "war_sides"
    """A narrative-event share: the power share of every attacker and defender."""
    MEMBERS = "members"
    """A narrative-event share: the power share of every nation that was a member."""
    REGIONS = "regions"
    """A narrative-event share: the population share of the regions the event lists."""
    INDEPENDENT_NATION = "independent_nation"
    """A narrative-event share: the power share of the nation that became independent."""
    HAB = "hab"
    """The hab share of the habs the event is about: its ``habs`` attribute, else its first hab."""
    FLEET = "fleet"
    """The fleet share of the fleet the event is about."""
    COMBAT = "combat"
    """The contested mass of the recorded combat, read from its record entry."""
    SPACE_LOSSES = "space_losses"
    """The space-loss share of the ships and habs the event lists: their mass and tier² over the human totals."""
    LEFT_FACTION = "left_faction"
    """The share of the faction a transition leaves, on the interval's earlier side."""
    COLONY = "colony"
    """A narrative-event share: the hab share of every hab the cited first-presence events list."""
    NEW_SHIPS = "new_ships"
    """A narrative-event share: the fleet share of every ship the cited appearance events are about."""
    SPACE_CAMPAIGN = "space_campaign"
    """A narrative-event share: the space-loss share of every ship and hab the cited space losses list."""
    NUCLEAR_ARC = "nuclear_arc"
    """A narrative-event share: the nuclear share of the arc's net move, its actor the nation."""


class Scaling(StrEnum):
    """How a share moves a kind's level: a named scaling, whose measure, rise share, drop share and reason are its
    entry in ``narrative.scalings.SCALINGS``. Kinds share one only when the same reason holds for both (ADR-0011)."""

    POWER = "power"
    POPULATION = "population"
    ORGANIZATION = "organization"
    HAB = "hab"
    FLEET = "fleet"
    BATTLE = "battle"
    SPACE_LOSS = "space_loss"
    FACTION = "faction"
    NUCLEAR = "nuclear"


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
    base: Significance = field(kw_only=True)
    evidence: EvidenceRole
    required: frozenset[str]
    optional: frozenset[str] = frozenset()
    rule: Rule | None = None
    share: ShareOf | None = None
    scaling: Scaling | None = None
    """How the share moves the level; declared exactly when ``share`` is."""
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
        if (self.share is None) != (self.scaling is None):
            raise ValueError(f"kind {self.event_type}: a share and a scaling are declared together or not at all")
