"""Significance rules: which events a campaign history keeps and which are routine churn. See ADR-0011.

One path scores atomic and narrative events alike; evidence for the entries is in ``docs/game-data-notes/``.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from ..analyzers.common import Lookup, Side
from ..analyzers.politics.bands import ALWAYS_MAJOR, COHESION_EXTREMES, UNREST_SEVERE, crossed, crosses
from ..analyzers.space.combat import side_factions
from ..kinds import kind_for
from ..kinds.nations import REGION_NATION_CHANGED
from ..kinds.space import SHIP_APPEARED
from ..log import fields as log_fields
from ..log import get_logger
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import SCORE_MAX, SCORE_MIN, SIGNIFICANCE_ORDER, Event, Role, Significance, SignificanceBasis
from ..model.kinds import EventKind, Measure, Rule, ShareOf
from ..model.snapshot import SaveSnapshot
from ..model.values import FrozenMap, Observed, number
from .measures import MEASURES, SCALE_MAX, SCALE_MIN
from .milestones import MILESTONE_TEMPLATES, milestone_of
from .shares import ALIEN_MASS_WEIGHT, FLEET_SATURATION, SaveShares, contested_mass, total

__all__ = [
    "RULE_IMPLEMENTATIONS",
    "SIGNIFICANCE_ORDER",
    "SHARE_IMPLEMENTATIONS",
    "ContextRule",
    "EventScore",
    "IntervalShares",
    "ShareReading",
    "ShareVariant",
    "Significance",
    "arithmetic",
    "assign_significance",
    "decide",
    "own_score",
    "scale",
    "score_event",
    "settled_score",
    "significance_of",
]

logger = get_logger(__name__)

# --- Thresholds -------------------------------------------------------------------------------------------
# Only what ranks emitted events; thresholds that decide whether an event exists live with its analyzer.

UPHEAVAL_CAUSES = frozenset({"Coup", "RegimeChange", "Independence", "Enthrall"})
"""``lastExecutiveChange.cause`` values that replace a government outside normal politics (field map, nations)."""

WAR_RELATION = "wars"
"""The ``nation.relation_changed`` relation that names a war; ``allies`` and ``rivals`` are routine diplomacy."""

# --- Context rules ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ContextRule:
    """A kind's context rule: it reads the event, and the snapshot lookup when ``needs_lookup``."""

    judge: Callable[[Event, Lookup | None], Significance | None]
    """``None`` defers to the base level."""
    needs_lookup: bool = False


def _from_event(rule: Callable[[Event], Significance | None]) -> ContextRule:
    return ContextRule(lambda event, lookup: rule(event))


def _from_snapshots(rule: Callable[[Event, Lookup], Significance | None]) -> ContextRule:
    def judge(event: Event, lookup: Lookup | None) -> Significance | None:
        if lookup is None:
            raise ValueError(f"rule {rule.__name__} of {event.event_type} needs the snapshot lookup")
        return rule(event, lookup)

    return ContextRule(judge, needs_lookup=True)


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


def _relation_changed(event: Event) -> Significance | None:
    return Significance.MAJOR if event.attribute("relation") == WAR_RELATION else Significance.MINOR


def _executive_change(event: Event) -> Significance | None:
    cause = event.attribute("cause")
    return Significance.MAJOR if isinstance(cause, str) and cause in UPHEAVAL_CAUSES else Significance.MINOR


def _population_changed(event: Event) -> Significance | None:
    """A population drop beyond territory is major, since routine decline is far slower; growth is minor."""
    return Significance.MAJOR if event.attribute("direction") == "drop" else Significance.MINOR


def _space_assets_changed(event: Event) -> Significance | None:
    """A nation's first space defences are major (they appear only late); boost and mission control moves are
    minor."""
    first = event.attribute("statistic") == "spaceDefences" and event.attribute("before") == 0
    return Significance.MAJOR if first else Significance.MINOR


def _army_presence(event: Event) -> Significance | None:
    """Megafauna are rare, so their presence is major; regular army presence is routine."""
    return Significance.MAJOR if event.attribute("megafauna") is True else Significance.MINOR


def _completion(event: Event) -> Significance | None:
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


def _band_shift(event: Event) -> Significance | None:
    """Major for a statistic that is always major, a crossing into severe unrest, a crossing of a cohesion extreme or
    two bands crossed, else minor."""
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
    return Significance.MAJOR if major else Significance.MINOR


def _collapse_after_strikes(event: Event) -> Significance | None:
    """A population collapse of nuked regions, or one citing nuclear strikes, is campaign defining."""
    nuked = event.attribute("nuked_regions")
    if (isinstance(nuked, tuple) and nuked) or event.attribute("nuclear_strikes") is True:
        return Significance.CAMPAIGN_DEFINING
    return None


def _entered_top(event: Event) -> Significance | None:
    """A nation entering the top of a space measure is a major event."""
    return Significance.MAJOR if event.attribute("entered_top") is True else None


def _milestone_tier(event: Event) -> Significance | None:
    """A completion's level is the tier the curated milestone list gives its template."""
    template = event.attribute("template")
    milestone = MILESTONE_TEMPLATES.get(template) if isinstance(template, str) else None
    return milestone.significance if milestone is not None else None


RULE_IMPLEMENTATIONS: Mapping[Rule, ContextRule] = {
    Rule.COUNCILOR_PRESENCE: _from_snapshots(_councilor_presence),
    Rule.RELATION_CHANGED: _from_event(_relation_changed),
    Rule.CLAIMS_CHANGED: _from_snapshots(_claims_changed),
    Rule.EXECUTIVE_CHANGE: _from_event(_executive_change),
    Rule.POPULATION_CHANGED: _from_event(_population_changed),
    Rule.SPACE_ASSETS_CHANGED: _from_event(_space_assets_changed),
    Rule.ARMY_PRESENCE: _from_event(_army_presence),
    Rule.COMPLETION: _from_event(_completion),
    Rule.BAND_SHIFT: _from_event(_band_shift),
    Rule.COLLAPSE_AFTER_STRIKES: _from_event(_collapse_after_strikes),
    Rule.ENTERED_TOP: _from_event(_entered_top),
    Rule.MILESTONE_TIER: _from_event(_milestone_tier),
}
"""Every ``Rule``'s implementation."""

# --- Shares -----------------------------------------------------------------------------------------------


class IntervalShares:
    """The shares of the two saves of one interval, the earlier side read first."""

    def __init__(self, before: SaveShares, after: SaveShares) -> None:
        self._saves = {Side.BEFORE: before, Side.AFTER: after}

    def save(self, side: Side) -> SaveShares:
        return self._saves[side]

    def shares(self, measure: Measure, side: Side) -> Mapping[EntityId, float]:
        return self._saves[side].of(measure)

    def share(self, measure: Measure, entities: Iterable[EntityId]) -> float | None:
        """The summed share of the distinct ``entities`` on the interval's earlier side, an entity without one there
        read on the later side; ``None`` when no entity has a share on either."""
        before, after = self.shares(measure, Side.BEFORE), self.shares(measure, Side.AFTER)
        found = {
            entity: (before if entity in before else after)[entity]
            for entity in set(entities)
            if entity in before or entity in after
        }
        return total(found, found) if found else None

    def world_warheads(self, side: Side) -> float | None:
        """The warheads of every nation in the side's save whose count is known; ``None`` when no count is known."""
        return self._saves[side].world_warheads


def _contested_share(event: Event, shares: IntervalShares) -> tuple[float, tuple[EntityRef, ...]] | None:
    """A recorded combat's contested mass over the world's weighted ship mass in the interval's earlier snapshot,
    with the factions of its sides; ``None`` when the event does not carry enough to measure it.

    Each side's mass is the event's ``side_dry_mass`` (priced by the analyzer), alien ships weighted up by the
    faction kinds the event carries. An event with one side is contested mass 0 (the analyzer leaves the mass of a
    one-sided record with a ``HabFaction`` unknown, as the hab is not named).
    """
    masses = event.attribute("side_dry_mass")
    factions = side_factions(event.attribute("sides"))
    if not isinstance(masses, tuple) or not 1 <= len(masses) <= 2 or len(masses) != len(factions):
        return None
    kinds = event.attribute("faction_kinds")
    kind_of = dict(kinds.items) if isinstance(kinds, FrozenMap) else {}
    weighted = [
        (ALIEN_MASS_WEIGHT if kind_of.get(str(faction.entity_id)) == "alien" else 1.0) * mass
        for faction, mass in zip(factions, masses, strict=True)
        if isinstance(mass, int | float)
    ]
    if len(weighted) != len(masses):
        return None
    contested = contested_mass(weighted[0], weighted[1]) if len(weighted) == 2 else 0.0
    world = max(shares.save(Side.BEFORE).world_ship_mass, FLEET_SATURATION)
    return contested / world, factions


Selector = Callable[[Event, Sequence[Event]], tuple[EntityRef, ...]]
"""An event and the events it cites in, the entities whose summed share is the event's share out; no entities, no
scale."""


class ShareVariant(StrEnum):
    """How a reading's share is taken when it is not the summed share of its entities."""

    PER_POINT = "per_point"
    """The share of a single control point: the nation's, divided by the points it holds."""
    BATTLE = "battle"
    """The share is read from the side masses the event carries (``_contested_share``), not from the shares of the
    entities."""
    NET_MOVE = "net_move"
    """The share is the arc's net move over the world total at its larger end (``_nuclear_share``)."""


@dataclass(frozen=True)
class ShareReading:
    """A ``ShareOf``'s implementation: its measure and the entities (of the event, or of the events it cites) whose
    summed share, in the shares of the event's first interval, is the share."""

    measure: Measure
    entities: Selector
    variant: ShareVariant | None = None


def _first(event: Event, domain: EntityDomain) -> tuple[EntityRef, ...]:
    return next(((ref,) for ref in event.entities if ref.entity_id.domain is domain), ())


def _nation(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    return _first(event, EntityDomain.NATION)


def _organization(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    return _first(event, EntityDomain.ORGANIZATION)


def _belligerents(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    if event.attribute("relation") != WAR_RELATION:
        return ()
    return tuple(ref for ref in event.entities if ref.entity_id.domain is EntityDomain.NATION)


def _moved_regions(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    """The regions of a transfer: the event's own, else those of the region events it cites; a region event is its
    own territory."""
    if event.event_type == REGION_NATION_CHANGED.event_type:
        return _first(event, EntityDomain.REGION)
    listed = _listed_refs(event.attribute("regions"))
    if listed:
        return listed
    return tuple(
        ref for item in cited if item.event_type == REGION_NATION_CHANGED.event_type for ref in _moved_regions(item)
    )


HAB_STATE_TYPE = "TIHabState"


def _habs(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    """The habs the event lists, else its first hab (lagrange points share the domain, so the state type tells)."""
    listed = _listed_refs(event.attribute("habs"))
    return listed or tuple(ref for ref in event.entities if ref.state_type == HAB_STATE_TYPE)[:1]


def _fleet(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    return _first(event, EntityDomain.FLEET)


def _left_faction(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    """The faction a transition leaves: its ``before`` value."""
    left = event.attribute("before")
    return (left,) if isinstance(left, EntityRef) else ()


def _role_nations(event: Event, wanted: Role) -> tuple[EntityRef, ...]:
    return tuple(ref for role, ref in event.roles if role is wanted and ref.entity_id.domain is EntityDomain.NATION)


def _listed_refs(value: Observed) -> tuple[EntityRef, ...]:
    """The entity references of a list attribute; anything else lists none."""
    return tuple(item for item in value if isinstance(item, EntityRef)) if isinstance(value, tuple) else ()


def _actor(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    """The nation the event is about; the kinds with this share name one actor, so a second would be another nation's
    share."""
    return _role_nations(event, Role.ACTOR)[:1]


def _targets(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    return _role_nations(event, Role.TARGET)


WAR_SIDES = ("attackers", "defenders")
"""The ``war.arc`` attributes listing each side's nations."""


def _sides(event: Event) -> tuple[tuple[EntityRef, ...], ...]:
    return tuple(_listed_refs(event.attribute(side)) for side in WAR_SIDES)


def _war_sides(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    return tuple(ref for side in _sides(event) for ref in side)


def _federation_members(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    changes = event.attribute("member_changes")
    changed = tuple(
        member
        for change in (changes if isinstance(changes, tuple) else ())
        if isinstance(change, FrozenMap) and isinstance(member := dict(change.items).get("nation"), EntityRef)
    )
    return (
        *_listed_refs(event.attribute("members_initial")),
        *_listed_refs(event.attribute("members_final")),
        *changed,
    )


def _listed_regions(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    return _listed_refs(event.attribute("regions"))


def _independent_nation(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    """A released nation is the beneficiary (the releasing nation acts); a breakaway nation acts."""
    return _role_nations(event, Role.BENEFICIARY)[:1] or _role_nations(event, Role.ACTOR)[:1]


def _cited_habs(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    """The habs of the cited first-presence events."""
    return tuple(ref for item in cited for ref in _listed_refs(item.attribute("habs")))


def _lost_assets(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    """The ships and habs the event lists as lost."""
    return tuple(ref for name in ("ships", "habs") for ref in _listed_refs(event.attribute(name)))


def _cited_losses(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    """The ships and habs of the cited space-losses events."""
    return tuple(ref for item in cited for ref in _lost_assets(item))


def _cited_ships(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    """The ships of the cited appearance events: the first entity of each."""
    return tuple(item.entities[0] for item in cited if item.event_type == SHIP_APPEARED.event_type and item.entities)


SHARE_IMPLEMENTATIONS: Mapping[ShareOf, ShareReading] = {
    ShareOf.NATION: ShareReading(Measure.POWER, _nation),
    ShareOf.BELLIGERENTS: ShareReading(Measure.POWER, _belligerents),
    ShareOf.TERRITORY: ShareReading(Measure.POPULATION, _moved_regions),
    ShareOf.CONTROL_POINT: ShareReading(Measure.POWER, _nation, ShareVariant.PER_POINT),
    ShareOf.ORGANIZATION: ShareReading(Measure.ORGANIZATION, _organization),
    ShareOf.HAB: ShareReading(Measure.HAB, _habs),
    ShareOf.FLEET: ShareReading(Measure.FLEET, _fleet),
    ShareOf.SPACE_LOSSES: ShareReading(Measure.SPACE_LOSS, _lost_assets),
    ShareOf.LEFT_FACTION: ShareReading(Measure.FACTION, _left_faction),
    ShareOf.COMBAT: ShareReading(Measure.BATTLE, lambda event, cited: (), ShareVariant.BATTLE),
    ShareOf.ACTOR: ShareReading(Measure.POWER, _actor),
    ShareOf.TARGETS: ShareReading(Measure.POWER, _targets),
    ShareOf.WAR_SIDES: ShareReading(Measure.POWER, _war_sides),
    ShareOf.MEMBERS: ShareReading(Measure.POWER, _federation_members),
    ShareOf.REGIONS: ShareReading(Measure.POPULATION, _listed_regions),
    ShareOf.INDEPENDENT_NATION: ShareReading(Measure.POWER, _independent_nation),
    ShareOf.COLONY: ShareReading(Measure.HAB, _cited_habs),
    ShareOf.NEW_SHIPS: ShareReading(Measure.FLEET, _cited_ships),
    ShareOf.SPACE_CAMPAIGN: ShareReading(Measure.SPACE_LOSS, _cited_losses),
    ShareOf.NUCLEAR_ARC: ShareReading(Measure.NUCLEAR, _actor, ShareVariant.NET_MOVE),
}
"""Every ``ShareOf``'s implementation; any kind may declare any of them."""


def scale(share: float, reference: float) -> int:
    """``round(10 * log10(share / reference))``, bounded by ``SCALE_MIN`` and ``SCALE_MAX``; no share takes
    ``SCALE_MIN``."""
    if share <= 0:
        return SCALE_MIN
    return max(SCALE_MIN, min(SCALE_MAX, round(10 * math.log10(share / reference))))


def _points(shares: IntervalShares, nation: EntityId) -> int:
    for side in (Side.BEFORE, Side.AFTER):
        if held := shares.save(side).control_points.get(nation):
            return held
    return 1


def _nuclear_share(event: Event, first: IntervalShares, last: IntervalShares) -> float | None:
    """The arc's net move, its first ``before`` to its last ``after``, over the larger world total of the earlier report
    of its first interval and the later report of its last (ADR-0011). A report missing counts can total less than the
    move, so the move bounds the total. ``None`` when a count of the move or both world totals are unknown, or nothing
    moved."""
    before, after = number(event.attribute("before")), number(event.attribute("after"))
    totals = [item for item in (first.world_warheads(Side.BEFORE), last.world_warheads(Side.AFTER)) if item is not None]
    if before is None or after is None or not totals:
        return None
    moved = abs(after - before)
    return moved / max(*totals, moved) if moved > 0 else None


def _unique(refs: Iterable[EntityRef]) -> tuple[EntityRef, ...]:
    """The first seen of each entity, in order."""
    seen: dict[EntityId, EntityRef] = {}
    for ref in refs:
        seen.setdefault(ref.entity_id, ref)
    return tuple(seen.values())


def _basis(
    reading: ShareReading,
    event: Event,
    cited: Sequence[Event],
    level: Significance,
    shares: IntervalShares,
    last: IntervalShares,
) -> SignificanceBasis | None:
    share: float | None
    if reading.variant is ShareVariant.BATTLE:
        measured = _contested_share(event, shares)
        if measured is None:
            return None
        share, refs = measured
    else:
        refs = _unique(reading.entities(event, cited))
        if reading.variant is ShareVariant.NET_MOVE:
            share = _nuclear_share(event, shares, last)
        else:
            share = shares.share(reading.measure, (ref.entity_id for ref in refs))
            if share is not None and reading.variant is ShareVariant.PER_POINT:
                share /= _points(shares, refs[0].entity_id)
        if share is None:
            return None
    return SignificanceBasis(
        base=level.base,
        measure=reading.measure,
        share=share,
        scale=scale(share, MEASURES[reading.measure].reference),
        entities=refs,
    )


def own_score(base: int, scales: Iterable[int]) -> int:
    """``base`` moved by the highest of ``scales``, inside the score bound; no scale leaves the base."""
    moved = max(scales, default=None)
    return base if moved is None else max(SCORE_MIN, min(SCORE_MAX, base + moved))


def settled_score(own: int, cited_scores: Iterable[int]) -> int:
    """The higher of an event's own score and the highest score it cites (ADR-0011)."""
    return max([own, *cited_scores])


def arithmetic(
    level: Significance, basis: SignificanceBasis | None, cited_scores: Iterable[int]
) -> tuple[int, Significance]:
    """The score and its level from the starting ``level``, the share's ``basis`` (``None`` for no share) and the
    scores of the cited events (ADR-0011): the higher of the level's base moved by the share and the highest cited
    score. The plain-number steps are ``own_score`` and ``settled_score``."""
    own = level.base if basis is None else own_score(basis.base, (basis.scale,))
    score = settled_score(own, cited_scores)
    return score, Significance.of(score)


# --- Entry points -----------------------------------------------------------------------------------------


def _kind(event: Event) -> EventKind:
    kind = kind_for(event.event_type)
    if kind is None:
        raise ValueError(f"event type {event.event_type} is declared by no kind")
    return kind


def decide(kind: EventKind, event: Event, lookup: Lookup | None = None) -> tuple[Significance, Rule | None]:
    """The kind's context-rule level, else its base level, and the context rule that decided it, ``None`` when the
    base level stood. A rule that needs the snapshot lookup raises ``ValueError`` without one: a code bug."""
    if kind.rule is not None:
        decided = RULE_IMPLEMENTATIONS[kind.rule].judge(event, lookup)
        if decided is not None:
            return decided, kind.rule
    return kind.base, None


def significance_of(event: Event, lookup: Lookup) -> Significance:
    """The kind's context rule, else its base level: the level before the share scales the score.

    Raises ``ValueError`` for a type no kind declares, or a narrative-event kind, scored when the narrative builder
    builds it: each is a code bug, as every emitter passes a kind and narrative events are not ranked here.
    """
    kind = _kind(event)
    if kind.narrative:
        raise ValueError(f"event type {event.event_type} is a narrative event, scored when it is built")
    return decide(kind, event, lookup)[0]


@dataclass(frozen=True)
class EventScore:
    """An event scored by ``score_event``."""

    score: int
    basis: SignificanceBasis | None
    rule: Rule | None
    """The kind's context rule that decided ``level``; ``None`` when the base level stood."""
    level: Significance
    """The level the own score starts from, before the share moves it."""

    @property
    def ruled(self) -> bool:
        """The kind's context rule decided ``level``; the base did not apply."""
        return self.rule is not None


def score_event(
    kind: EventKind,
    event: Event,
    cited: Iterable[Event] = (),
    *,
    shares: IntervalShares | None = None,
    last: IntervalShares | None = None,
    lookup: Lookup | None = None,
    reading: ShareReading | None = None,
    base: Significance | None = None,
    floored: bool = True,
) -> EventScore:
    """The one scoring path of every event: the kind's context rule, else its base level, moved by its share, never
    below the highest score among the ``cited`` events (ADR-0011).

    ``shares`` are the saves' shares of the event's first interval, without them there is no basis; ``last`` those of
    its last interval (by default the first's), read only by the nuclear share. ``lookup`` is the snapshots' lookup,
    for the rules that need it. ``reading`` and ``base`` override the kind's own share and base
    level; the context rule still decides first, ``base`` applying only where it defers. ``floored`` is false where
    the cited events only locate the share's entities and their scores must not lift the event: an atomic event's
    evidence.
    """
    cited = tuple(cited)
    decided, rule = decide(kind, event, lookup)
    level = decided if rule is not None else (base if base is not None else kind.base)
    named = kind.share
    reading = reading or (SHARE_IMPLEMENTATIONS[named] if named is not None else None)
    basis = (
        _basis(reading, event, cited, level, shares, last or shares)
        if reading is not None and shares is not None
        else None
    )
    score, _ = arithmetic(level, basis, (item.score for item in cited) if floored else ())
    return EventScore(score, basis, rule, level)


def assign_significance(
    events: Iterable[Event],
    before: SaveSnapshot,
    after: SaveSnapshot,
    shares: tuple[SaveShares, SaveShares],
    *,
    evidence: Iterable[Event] = (),
) -> tuple[Event, ...]:
    """Each event gets its score (its level's base, moved by its share when the type has one) and the level
    of that score; keeps the given order. ``shares`` are the two snapshots' (``shares.build_shares``, built once per
    save); ``evidence`` are the events a reconstructed one may cite for its share."""
    interval = IntervalShares(*shares)
    lookup = Lookup(before, after)
    known = {event.id: event for event in evidence}
    assigned = tuple(_ranked(event, known, interval, lookup) for event in events)
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


def _ranked(event: Event, known: Mapping[str, Event], shares: IntervalShares, lookup: Lookup) -> Event:
    cited = tuple(known[item] for item in event.constituents if item in known)
    scored = score_event(_kind(event), event, cited, shares=shares, lookup=lookup, floored=False)
    return replace(
        event,
        significance=Significance.of(scored.score),
        score=scored.score,
        significance_basis=scored.basis,
        context_rule=scored.rule,
    )
