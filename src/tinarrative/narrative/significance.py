"""Significance rules: which events a campaign history keeps and which are routine churn. See ADR-0011.

A post-pass, so no analyzer has to judge impact. Evidence for the entries is in
``docs/game-data-notes/higher-level-event-sources.md``. Notification templates are never ranked: the game's own log
is player-centric and open-ended. Narrative events span intervals and keep no snapshot: ``narrative_score`` scores
each as the narrative builder builds it.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace

from ..analyzers.common import Lookup, Side
from ..analyzers.politics.bands import ALWAYS_MAJOR, COHESION_EXTREMES, UNREST_SEVERE, crossed, crosses
from ..analyzers.politics.nation_assets import GDP, STRENGTH
from ..config import DEFAULT_SETTINGS, GeopoliticsSettings, SignificanceSettings
from ..kinds import kind_for
from ..kinds.nations import REGION_NATION_CHANGED
from ..log import fields as log_fields
from ..log import get_logger
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import SIGNIFICANCE_ORDER, Event, Significance, SignificanceBasis
from ..model.kinds import EventKind, Rule, Stake, StakeMeasure
from ..model.snapshot import SaveSnapshot
from ..model.values import Observed, number
from .milestones import MILESTONE_TEMPLATES, milestone_of
from .prominence import nation_power, organization_shares, region_shares, total
from .situation import SituationReport

__all__ = [
    "PROMOTED",
    "RULE_IMPLEMENTATIONS",
    "SIGNIFICANCE_ORDER",
    "STAKE_IMPLEMENTATIONS",
    "NarrativeContextRule",
    "Scaling",
    "Significance",
    "Stakes",
    "assign_significance",
    "in_top_n",
    "narrative_score",
    "promoted_at_rank",
    "promoted_by_rank",
    "significance_of",
]

logger = get_logger(__name__)

# --- Thresholds -------------------------------------------------------------------------------------------
# Only what ranks emitted events; thresholds that decide whether an event exists live with its analyzer.

UPHEAVAL_CAUSES = frozenset({"Coup", "RegimeChange", "Independence", "Enthrall"})
"""``lastExecutiveChange.cause`` values that replace a government outside normal politics (field map, nations)."""

WAR_RELATION = "wars"
"""The ``nation.relation_changed`` relation that names a war; ``allies`` and ``rivals`` are routine diplomacy."""

DISCRETE_STATISTICS = frozenset({"numNuclearWeapons"})
"""``nation.statistic_shifted`` statistics whose every change is a narrative event: a nuclear arsenal. Other statistics
shift past their threshold for routine reasons too (event effects, priorities), so a shift is evidence for the rules
that explain it and stays trivial on its own."""

LARGE_ARSENAL = 10
"""Dismantling an arsenal at least this large to zero is campaign defining."""

# --- Rank promotion ---------------------------------------------------------------------------------------
# TODO(#362): temporary; the named context rule and the stakes replace these, then they go with ``top_gdp_nations``.

PROMOTED = {
    Significance.TRIVIAL: Significance.MINOR,
    Significance.MINOR: Significance.MAJOR,
    Significance.MAJOR: Significance.CAMPAIGN_DEFINING,
    Significance.CAMPAIGN_DEFINING: Significance.CAMPAIGN_DEFINING,
}
"""One level up; the highest level stays."""


def in_top_n(rank: Observed, top: int) -> bool:
    """Whether ``rank`` (1 is the largest) is at most ``top``. An unranked nation (``None``, unknown) is not in it."""
    return isinstance(rank, int) and not isinstance(rank, bool) and rank <= top


def promoted_at_rank(level: Significance, rank: Observed, top: int) -> Significance:
    """``level`` one up when ``rank`` is in the top ``top``."""
    return PROMOTED[level] if in_top_n(rank, top) else level


def promoted_by_rank(
    level: Significance, report: SituationReport, nation_id: EntityId, top: int, *, by_strength: bool = False
) -> Significance:
    """``level`` one up when the nation ranks in the top ``top`` by GDP (or, with ``by_strength``, by strength) in
    ``report``, ranked as ``SituationReport.rank`` ranks."""
    statistics = (GDP, STRENGTH) if by_strength else (GDP,)
    if any(in_top_n(report.rank(nation_id, statistic), top) for statistic in statistics):
        return PROMOTED[level]
    return level


# --- Context rules ----------------------------------------------------------------------------------------

ContextRule = Callable[[Event, Lookup], Significance | None]
"""An atomic kind's context rule; ``None`` defers to the base level."""


@dataclass(frozen=True)
class NarrativeContextRule:
    """A narrative-event kind's context rule: it reads only the event, and the settings of a temporary rule."""

    judge: Callable[[Event, GeopoliticsSettings], Significance | None]
    """``None`` defers to the base level."""


def _subject(event: Event) -> EntityRef | None:
    return event.entities[0] if event.entities else None


def _side(event: Event) -> Side | None:
    side = event.attribute("side")
    return Side(side) if isinstance(side, str) and side in {item.value for item in Side} else None


def _councilor_presence(event: Event, lookup: Lookup) -> Significance | None:
    """Recruit-pool churn is trivial; a councilor with a faction that is gone is a narrative event.

    A null faction marks the recruit pool (notes, "Recruit pool").
    """
    subject, side = _subject(event), _side(event)
    if subject is None or side is None:
        return None
    state = lookup.state(subject.entity_id, side)
    if state is None:
        return None
    faction = state.get("faction")
    if faction is None:
        return Significance.TRIVIAL
    if isinstance(faction, EntityRef):
        return Significance.MAJOR if side is Side.BEFORE else Significance.MINOR
    return None


def _relation_changed(event: Event, lookup: Lookup) -> Significance | None:
    return Significance.MAJOR if event.attribute("relation") == WAR_RELATION else Significance.MINOR


def _executive_change(event: Event, lookup: Lookup) -> Significance | None:
    cause = event.attribute("cause")
    return Significance.MAJOR if isinstance(cause, str) and cause in UPHEAVAL_CAUSES else Significance.MINOR


def _statistic_shifted(event: Event, lookup: Lookup) -> Significance | None:
    return Significance.MAJOR if event.attribute("statistic") in DISCRETE_STATISTICS else Significance.TRIVIAL


def _population_changed(event: Event, lookup: Lookup) -> Significance | None:
    """A population drop beyond territory is major, since routine decline is far slower; growth is minor."""
    return Significance.MAJOR if event.attribute("direction") == "drop" else Significance.MINOR


def _space_assets_changed(event: Event, lookup: Lookup) -> Significance | None:
    """A nation's first space defences are major (they appear only late); boost and mission control moves are
    minor."""
    first = event.attribute("statistic") == "spaceDefences" and event.attribute("before") == 0
    return Significance.MAJOR if first else Significance.MINOR


def _army_presence(event: Event, lookup: Lookup) -> Significance | None:
    """Megafauna are rare, so their presence is major; regular army presence is routine."""
    return Significance.MAJOR if event.attribute("megafauna") is True else Significance.MINOR


def _completion(event: Event, lookup: Lookup) -> Significance | None:
    """An unlisted completion is minor: many technologies and projects are routine unlocks."""
    milestone = milestone_of(event)
    return milestone.significance if milestone is not None else Significance.MINOR


def _claims_changed(event: Event, lookup: Lookup) -> Significance | None:
    """The alien administration's claims cover every region implicitly, so its changes are minor; a human
    nation's claims are major."""
    subject = _subject(event)
    for side in (Side.AFTER, Side.BEFORE):
        state = lookup.state(subject.entity_id, side) if subject is not None else None
        if state is not None and state.get("alienNation") is True:
            return Significance.MINOR
    return Significance.MAJOR


def _top_gdp_nation(event: Event, geopolitics: GeopoliticsSettings) -> Significance | None:
    """An event about a top-ranked economy is one level up. TODO(#362): temporary; the nation's power share replaces
    it."""
    return promoted_at_rank(_base(event), event.attribute("gdp_rank"), geopolitics.top_gdp_nations)


def _band_shift(event: Event, geopolitics: GeopoliticsSettings) -> Significance | None:
    """Major for a statistic that is always major, a crossing into severe unrest, a crossing of a cohesion extreme or
    two bands crossed, else minor; a top-ranked economy is one level up (TODO(#362): temporary)."""
    statistic, before, after = (
        event.attribute("statistic"),
        number(event.attribute("before")),
        number(event.attribute("after")),
    )
    if not isinstance(statistic, str) or before is None or after is None:
        return None
    move = crossed(statistic, before, after)
    bands = move.bands_crossed if move is not None else 0
    if statistic in ALWAYS_MAJOR:
        major = True
    elif statistic == "unrest":
        major = bands >= 2 or crosses(UNREST_SEVERE, before, after)
    elif statistic == "cohesion":
        major = any(crosses(boundary, before, after) for boundary in COHESION_EXTREMES)
    else:
        major = bands >= 2
    level = Significance.MAJOR if major else Significance.MINOR
    return promoted_at_rank(level, event.attribute("gdp_rank"), geopolitics.top_gdp_nations)


def _collapse_after_strikes(event: Event, _: GeopoliticsSettings) -> Significance | None:
    """A population collapse of nuked regions, or one citing nuclear strikes, is campaign defining."""
    nuked = event.attribute("nuked_regions")
    if (isinstance(nuked, tuple) and nuked) or event.attribute("nuclear_strikes") is True:
        return Significance.CAMPAIGN_DEFINING
    return None


def _large_arsenal_disarmed(event: Event, _: GeopoliticsSettings) -> Significance | None:
    """Dismantling a large arsenal to zero is campaign defining."""
    before, after = number(event.attribute("before")), number(event.attribute("after"))
    if before is not None and after == 0 and before >= LARGE_ARSENAL:
        return Significance.CAMPAIGN_DEFINING
    return None


def _top_rank(event: Event, geopolitics: GeopoliticsSettings) -> Significance | None:
    """An event of a nation ranked in the top by GDP or strength is one level up."""
    # TODO(#362): temporary; the nation's power share replaces it.
    top = geopolitics.top_gdp_nations
    if in_top_n(event.attribute("gdp_rank"), top) or in_top_n(event.attribute("strength_rank"), top):
        return PROMOTED[_base(event)]
    return None


def _entered_top(event: Event, geopolitics: GeopoliticsSettings) -> Significance | None:
    """A nation entering the top of a space measure is a major event."""
    return Significance.MAJOR if event.attribute("entered_top") is True else None


def _milestone_tier(event: Event, geopolitics: GeopoliticsSettings) -> Significance | None:
    """A completion's level is the tier the curated milestone list gives its template."""
    template = event.attribute("template")
    milestone = MILESTONE_TEMPLATES.get(template) if isinstance(template, str) else None
    return milestone.significance if milestone is not None else None


RULE_IMPLEMENTATIONS: Mapping[Rule, ContextRule | NarrativeContextRule] = {
    Rule.COUNCILOR_PRESENCE: _councilor_presence,
    Rule.RELATION_CHANGED: _relation_changed,
    Rule.CLAIMS_CHANGED: _claims_changed,
    Rule.EXECUTIVE_CHANGE: _executive_change,
    Rule.STATISTIC_SHIFTED: _statistic_shifted,
    Rule.POPULATION_CHANGED: _population_changed,
    Rule.SPACE_ASSETS_CHANGED: _space_assets_changed,
    Rule.ARMY_PRESENCE: _army_presence,
    Rule.COMPLETION: _completion,
    Rule.TOP_GDP_NATION: NarrativeContextRule(_top_gdp_nation),
    Rule.BAND_SHIFT: NarrativeContextRule(_band_shift),
    Rule.COLLAPSE_AFTER_STRIKES: NarrativeContextRule(_collapse_after_strikes),
    Rule.LARGE_ARSENAL_DISARMED: NarrativeContextRule(_large_arsenal_disarmed),
    Rule.TOP_RANK: NarrativeContextRule(_top_rank),
    Rule.ENTERED_TOP: NarrativeContextRule(_entered_top),
    Rule.MILESTONE_TIER: NarrativeContextRule(_milestone_tier),
}
"""Every ``Rule``'s implementation."""

# --- Stakes -----------------------------------------------------------------------------------------------


class Stakes:
    """The prominence shares of the two snapshots of one interval, each built on first use."""

    def __init__(
        self,
        before: SaveSnapshot,
        after: SaveSnapshot,
        settings: SignificanceSettings,
        evidence: Iterable[Event] = (),
    ) -> None:
        self.lookup = Lookup(before, after)
        self.settings = settings
        self._snapshots = {Side.BEFORE: before, Side.AFTER: after}
        self._shares: dict[tuple[StakeMeasure, Side], dict[EntityId, float]] = {}
        self._evidence = {event.id: event for event in evidence}

    def shares(self, measure: StakeMeasure, side: Side) -> dict[EntityId, float]:
        key = (measure, side)
        if key not in self._shares:
            snapshot = self._snapshots[side]
            if measure is StakeMeasure.POWER:
                self._shares[key] = nation_power(snapshot, self.settings.power)
            elif measure is StakeMeasure.POPULATION:
                self._shares[key] = region_shares(snapshot)
            else:
                self._shares[key] = organization_shares(snapshot, self.settings.tier_exponent)
        return self._shares[key]

    def share(self, measure: StakeMeasure, entities: Iterable[EntityId]) -> float | None:
        """The summed share of ``entities`` on the interval's earlier side, an entity without one there read on the
        later side; ``None`` when no entity has a share on either."""
        before = self.shares(measure, Side.BEFORE)
        after = self.shares(measure, Side.AFTER)
        found = {
            entity: (before if entity in before else after)[entity]
            for entity in set(entities)
            if entity in before or entity in after
        }
        return total(found, found) if found else None

    def cited(self, event: Event) -> tuple[Event, ...]:
        return tuple(self._evidence[item] for item in event.constituents if item in self._evidence)


EntitiesOf = Callable[[Event, Stakes], tuple[EntityId, ...]]


@dataclass(frozen=True)
class Scaling:
    """A ``Stake``'s implementation: its measure and the entities whose summed share is the stake; no entities, no
    scale."""

    measure: StakeMeasure
    entities: EntitiesOf
    per_point: bool = False
    """The share of a single control point: the nation's, divided by the points it holds."""
    nuclear_bonus: bool = False


def _first(event: Event, domain: EntityDomain) -> tuple[EntityId, ...]:
    return next(((ref.entity_id,) for ref in event.entities if ref.entity_id.domain is domain), ())


def _nation(event: Event, stakes: Stakes) -> tuple[EntityId, ...]:
    return _first(event, EntityDomain.NATION)


def _organization(event: Event, stakes: Stakes) -> tuple[EntityId, ...]:
    return _first(event, EntityDomain.ORGANIZATION)


def _belligerents(event: Event, stakes: Stakes) -> tuple[EntityId, ...]:
    if event.attribute("relation") != WAR_RELATION:
        return ()
    return tuple(ref.entity_id for ref in event.entities if ref.entity_id.domain is EntityDomain.NATION)


def _moved_regions(event: Event, stakes: Stakes) -> tuple[EntityId, ...]:
    """The regions of a transfer: the event's own, else those of the region events it cites; a region event is its
    own territory."""
    if event.event_type == REGION_NATION_CHANGED.event_type:
        return _first(event, EntityDomain.REGION)
    listed = event.attribute("regions")
    if isinstance(listed, tuple):
        return tuple(ref.entity_id for ref in listed if isinstance(ref, EntityRef))
    return tuple(
        entity
        for cited in stakes.cited(event)
        if cited.event_type == REGION_NATION_CHANGED.event_type
        for entity in _moved_regions(cited, stakes)
    )


STAKE_IMPLEMENTATIONS: Mapping[Stake, Scaling] = {
    Stake.NATION: Scaling(StakeMeasure.POWER, _nation),
    Stake.BELLIGERENTS: Scaling(StakeMeasure.POWER, _belligerents, nuclear_bonus=True),
    Stake.TERRITORY: Scaling(StakeMeasure.POPULATION, _moved_regions),
    Stake.CONTROL_POINT: Scaling(StakeMeasure.POWER, _nation, per_point=True),
    Stake.ORGANIZATION: Scaling(StakeMeasure.ORGANIZATION, _organization),
}
"""Every ``Stake``'s implementation."""


def _scale(share: float, reference: float, settings: SignificanceSettings) -> int:
    if share <= 0:
        return settings.scale_min
    return max(settings.scale_min, min(settings.scale_max, round(10 * math.log10(share / reference))))


def _points(stakes: Stakes, nation: EntityId) -> int:
    for side in (Side.BEFORE, Side.AFTER):
        state = stakes.lookup.state(nation, side)
        held = state.get("controlPoints") if state is not None else None
        if isinstance(held, tuple) and held:
            return len(held)
    return 1


def _holds_nuclear_weapons(stakes: Stakes, nation: EntityId) -> bool:
    for side in (Side.BEFORE, Side.AFTER):
        state = stakes.lookup.state(nation, side)
        if state is not None:
            weapons = state.get("numNuclearWeapons")
            return isinstance(weapons, int | float) and not isinstance(weapons, bool) and weapons > 0
    return False


def _basis(event: Event, level: Significance, stakes: Stakes) -> SignificanceBasis | None:
    named = _kind(event).stake
    if named is None:
        return None
    stake = STAKE_IMPLEMENTATIONS[named]
    entities = stake.entities(event, stakes)
    share = stakes.share(stake.measure, entities)
    if share is None:
        return None
    if stake.per_point:
        share /= _points(stakes, entities[0])
    reference = getattr(stakes.settings.reference, stake.measure.value)
    bonus = 0
    if (
        stake.nuclear_bonus
        and len(set(entities)) > 1
        and all(_holds_nuclear_weapons(stakes, item) for item in entities)
    ):
        bonus = stakes.settings.reference.nuclear_bonus
    refs = tuple(ref for ref in event.entities if ref.entity_id in set(entities))
    return SignificanceBasis(
        base=level.base,
        measure=stake.measure,
        share=float(f"{share:.6g}"),
        scale=_scale(share, reference, stakes.settings),
        entities=refs,
        bonus=bonus,
    )


# --- Entry points -----------------------------------------------------------------------------------------


def _kind(event: Event) -> EventKind:
    kind = kind_for(event.event_type)
    if kind is None:
        raise ValueError(f"event type {event.event_type} is declared by no kind")
    return kind


def _base(event: Event) -> Significance:
    return _base_of(_kind(event))


def _base_of(kind: EventKind) -> Significance:
    if kind.base is None:
        raise ValueError(f"event type {kind.event_type} has its level set by its narrative rule")
    return kind.base


def significance_of(event: Event, lookup: Lookup) -> Significance:
    """The kind's context rule, else its base level: the level before the stake scales the score.

    Raises ``ValueError`` for a type no kind declares, or a narrative-event kind, scored by ``narrative_score``: each
    is a code bug, as every emitter passes a kind and narrative events are not ranked here.
    """
    kind = _kind(event)
    if kind.narrative:
        raise ValueError(f"event type {event.event_type} is a narrative event, scored when it is built")
    if kind.rule is not None:
        if isinstance(rule := RULE_IMPLEMENTATIONS[kind.rule], NarrativeContextRule):
            raise ValueError(f"rule {kind.rule} of {event.event_type} judges a narrative event")
        decided = rule(event, lookup)
        if decided is not None:
            return decided
    return _base(event)


def narrative_score(kind: EventKind, event: Event, cited: Iterable[Event], geopolitics: GeopoliticsSettings) -> int:
    """The higher of the kind's context-rule level, else its base level, and the highest score among the ``cited``
    events (ADR-0011).

    Raises ``ValueError`` for a kind without a base level, one declaring a stake (no narrative stake is implemented
    yet), or one whose context rule judges atomic events: each is a code bug.
    """
    if kind.stake is not None:
        raise ValueError(f"narrative-event kind {kind.event_type} declares a stake, which is not implemented")
    level = _base_of(kind)
    if kind.rule is not None:
        rule = RULE_IMPLEMENTATIONS[kind.rule]
        if not isinstance(rule, NarrativeContextRule):
            raise ValueError(f"rule {kind.rule} of {event.event_type} judges an atomic event")
        decided = rule.judge(event, geopolitics)
        if decided is not None:
            level = decided
    return max([level.base, *(item.score for item in cited)])


def assign_significance(
    events: Iterable[Event],
    before: SaveSnapshot,
    after: SaveSnapshot,
    settings: SignificanceSettings = DEFAULT_SETTINGS.narrative.significance,
    *,
    evidence: Iterable[Event] = (),
) -> tuple[Event, ...]:
    """Each event gets its score (its level's base, moved by its stake when the type has one) and the level
    of that score; keeps the given order. ``evidence`` are the events a reconstructed one may cite for its stake."""
    stakes = Stakes(before, after, settings, evidence)
    assigned = tuple(_ranked(event, significance_of(event, stakes.lookup), stakes) for event in events)
    if logger.isEnabledFor(logging.DEBUG):
        counts = Counter(event.significance.value for event in assigned)
        logger.debug(
            "significance assigned %s",
            log_fields(
                events=len(assigned),
                scaled=sum(event.significance_basis is not None for event in assigned),
                **{level.value: counts.get(level.value, 0) for level in SIGNIFICANCE_ORDER},
            ),
        )
    return assigned


def _ranked(event: Event, level: Significance, stakes: Stakes) -> Event:
    basis = _basis(event, level, stakes)
    if basis is None:
        return replace(event, significance=level, score=level.base, significance_basis=None)
    score = max(0, min(100, basis.base + basis.scale + basis.bonus))
    return replace(event, significance=Significance.of(score), score=score, significance_basis=basis)
