"""Significance rules: which events a campaign history keeps and which are routine churn. See ADR-0011.

A post-pass, so no analyzer has to judge impact. Evidence for the entries is in
``docs/game-data-notes/higher-level-event-sources.md``. Notification templates are never ranked: the game's own log
is player-centric and open-ended. Narrative events span intervals and keep no snapshot: ``narrative_score`` scores
each as the narrative builder builds it, its stake read from the situation reports of its first interval.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

from ..analyzers.common import Lookup, Side
from ..analyzers.politics.bands import ALWAYS_MAJOR, COHESION_EXTREMES, UNREST_SEVERE, crossed, crosses
from ..analyzers.politics.nation_assets import GDP, STRENGTH
from ..analyzers.space.combat import LOG_FIELD as COMBAT_LOG
from ..config import DEFAULT_SETTINGS, GeopoliticsSettings, SignificanceSettings
from ..kinds import kind_for
from ..kinds.nations import REGION_NATION_CHANGED
from ..kinds.space import SHIP_APPEARED
from ..log import fields as log_fields
from ..log import get_logger
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import SIGNIFICANCE_ORDER, Event, Role, Significance, SignificanceBasis
from ..model.kinds import EventKind, Rule, Stake, StakeMeasure
from ..model.records import CombatEntry
from ..model.snapshot import SaveSnapshot
from ..model.values import FrozenMap, Observed, number
from .milestones import MILESTONE_TEMPLATES, milestone_of
from .prominence import (
    ALIEN_MASS_WEIGHT,
    FLEET_SATURATION,
    ShipMasses,
    contested_mass,
    nation_power,
    organization_shares,
    region_shares,
    ship_masses,
    total,
)
from .situation import SituationReport, build_situation

__all__ = [
    "PROMOTED",
    "RULE_IMPLEMENTATIONS",
    "SIGNIFICANCE_ORDER",
    "STAKE_IMPLEMENTATIONS",
    "NARRATIVE_STAKE_IMPLEMENTATIONS",
    "NarrativeContextRule",
    "NarrativeScaling",
    "ReportStakes",
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


def _band_shift(event: Event, _: GeopoliticsSettings) -> Significance | None:
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


def _collapse_after_strikes(event: Event, _: GeopoliticsSettings) -> Significance | None:
    """A population collapse of nuked regions, or one citing nuclear strikes, is campaign defining."""
    nuked = event.attribute("nuked_regions")
    if (isinstance(nuked, tuple) and nuked) or event.attribute("nuclear_strikes") is True:
        return Significance.CAMPAIGN_DEFINING
    return None

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
    Rule.POPULATION_CHANGED: _population_changed,
    Rule.SPACE_ASSETS_CHANGED: _space_assets_changed,
    Rule.ARMY_PRESENCE: _army_presence,
    Rule.COMPLETION: _completion,
    Rule.BAND_SHIFT: NarrativeContextRule(_band_shift),
    Rule.COLLAPSE_AFTER_STRIKES: NarrativeContextRule(_collapse_after_strikes),
    Rule.ENTERED_TOP: NarrativeContextRule(_entered_top),
    Rule.MILESTONE_TIER: NarrativeContextRule(_milestone_tier),
}
"""Every ``Rule``'s implementation."""

# --- Stakes -----------------------------------------------------------------------------------------------


class _IntervalShares:
    """The prominence shares of the two sides of one interval, each measured on first use (``_measured``)."""

    def __init__(self, settings: SignificanceSettings) -> None:
        self.settings = settings
        self._shares: dict[tuple[StakeMeasure, Side], dict[EntityId, float]] = {}

    def _measured(self, measure: StakeMeasure, side: Side) -> dict[EntityId, float]:
        raise NotImplementedError

    def _report(self, side: Side) -> SituationReport:
        raise NotImplementedError

    def _space_measured(self, measure: StakeMeasure, side: Side) -> dict[EntityId, float]:
        """The hab, fleet and faction shares, read from the side's situation report."""
        report = self._report(side)
        if measure is StakeMeasure.HAB:
            return report.hab_shares()
        if measure is StakeMeasure.FLEET:
            return report.fleet_shares()
        return report.faction_stakes(self.settings.power, self.settings.w_space)

    def shares(self, measure: StakeMeasure, side: Side) -> dict[EntityId, float]:
        key = (measure, side)
        if key not in self._shares:
            self._shares[key] = self._measured(measure, side)
        return self._shares[key]

    def share(self, measure: StakeMeasure, entities: Iterable[EntityId]) -> float | None:
        """The summed share of the distinct ``entities`` on the interval's earlier side, an entity without one there
        read on the later side; ``None`` when no entity has a share on either."""
        before, after = self.shares(measure, Side.BEFORE), self.shares(measure, Side.AFTER)
        found = {
            entity: (before if entity in before else after)[entity]
            for entity in set(entities)
            if entity in before or entity in after
        }
        return total(found, found) if found else None


def _is_design_count(value: object) -> bool:
    """A ``CombatEntry.designs`` triple: design, hull class, count."""
    return (
        isinstance(value, tuple)
        and len(value) == 3
        and isinstance(value[0], str)
        and isinstance(value[1], str)
        and isinstance(value[2], int)
    )


class Stakes(_IntervalShares):
    """The prominence shares of the two snapshots of one interval: an atomic event's stakes."""

    def __init__(
        self,
        before: SaveSnapshot,
        after: SaveSnapshot,
        settings: SignificanceSettings,
        evidence: Iterable[Event] = (),
    ) -> None:
        super().__init__(settings)
        self.lookup = Lookup(before, after)
        self._snapshots = {Side.BEFORE: before, Side.AFTER: after}
        self._evidence = {event.id: event for event in evidence}
        self._reports: dict[Side, SituationReport] = {}
        self._masses: ShipMasses | None = None

    def _report(self, side: Side) -> SituationReport:
        if side not in self._reports:
            self._reports[side] = build_situation(self._snapshots[side])
        return self._reports[side]

    def _measured(self, measure: StakeMeasure, side: Side) -> dict[EntityId, float]:
        snapshot = self._snapshots[side]
        if measure is StakeMeasure.POWER:
            return nation_power(snapshot, self.settings.power)
        if measure is StakeMeasure.POPULATION:
            return region_shares(snapshot)
        if measure is StakeMeasure.ORGANIZATION:
            return organization_shares(snapshot, self.settings.tier_exponent)
        if measure is StakeMeasure.BATTLE:
            raise ValueError("a battle stake is read from a combat record, not from shares")
        return self._space_measured(measure, side)

    def contested_share(self, event: Event) -> tuple[float, tuple[EntityRef, ...]] | None:
        """A recorded combat's contested mass over the world's weighted ship mass in the interval's earlier snapshot,
        with the factions of its sides; ``None`` when the record does not say enough to measure it.

        Each side's mass is its ships' dry mass (a live ship of the design in the earlier snapshot, else the median of
        its hull class there, else nothing), alien ships weighted up. A record with one side and a ``HabFaction``
        does not name the hab, so it is not measured; one side without is contested mass 0.
        """
        entry = self._combat_entry(event)
        if entry is None or not isinstance(entry.designs, tuple):
            return None
        sides: list[tuple[EntityRef, tuple[tuple[str, str, int], ...]]] = []
        for side in entry.designs:
            if not (isinstance(side, tuple) and isinstance(side[0], EntityRef) and isinstance(side[1], tuple)):
                return None
            sides.append((side[0], tuple(ship for ship in side[1] if _is_design_count(ship))))  # type: ignore[misc]
        if not 1 <= len(sides) <= 2 or (len(sides) == 1 and isinstance(entry.hab_faction, EntityRef)):
            return None
        if self._masses is None:
            self._masses = ship_masses(self._snapshots[Side.BEFORE])
        masses = [self._side_mass(faction, ships, self._masses) for faction, ships in sides]
        contested = contested_mass(masses[0], masses[1]) if len(masses) == 2 else 0.0
        world = max(self._report(Side.BEFORE).world.weighted_ship_mass, FLEET_SATURATION)
        return contested / world, tuple(self.lookup.resolve(faction) or faction for faction, _ in sides)

    def _side_mass(self, faction: EntityRef, ships: tuple[tuple[str, str, int], ...], masses: ShipMasses) -> float:
        weight = ALIEN_MASS_WEIGHT if self.lookup.faction_kind(faction.entity_id) == "alien" else 1.0
        return weight * math.fsum(
            (masses.of(faction.entity_id, design, hull) or 0.0) * count for design, hull, count in ships
        )

    def _combat_entry(self, event: Event) -> CombatEntry | None:
        """The entry a ``faction.combat_recorded`` event rests on, found by its record index."""
        source = event.sources[0] if event.sources else None
        location = source.entry if source is not None else None
        owner = event.entities[0] if event.entities else None
        if location is None or location.path is None or owner is None:
            return None
        tail = location.path.rsplit("/", 1)[-1]
        record_set = self.lookup.record_set(owner.entity_id, COMBAT_LOG, Side.AFTER)
        if not tail.isdigit() or record_set is None or not isinstance(record_set.entries, tuple):
            return None
        return next(
            (item for item in record_set.entries if isinstance(item, CombatEntry) and item.index == int(tail)), None
        )

    def cited(self, event: Event) -> tuple[Event, ...]:
        return tuple(self._evidence[item] for item in event.constituents if item in self._evidence)


class ReportStakes(_IntervalShares):
    """The prominence shares of the two situation reports of a narrative event's first interval. A report states no
    organization tiers, so a narrative stake is a power, population, hab or fleet share."""

    def __init__(self, before: SituationReport, after: SituationReport, settings: SignificanceSettings) -> None:
        super().__init__(settings)
        self._reports = {Side.BEFORE: before, Side.AFTER: after}

    def _report(self, side: Side) -> SituationReport:
        return self._reports[side]

    def _measured(self, measure: StakeMeasure, side: Side) -> dict[EntityId, float]:
        report = self._reports[side]
        if measure is StakeMeasure.POWER:
            return report.power_shares(self.settings.power)
        if measure is StakeMeasure.POPULATION:
            return report.population_shares()
        if measure in (StakeMeasure.HAB, StakeMeasure.FLEET, StakeMeasure.FACTION):
            return self._space_measured(measure, side)
        raise ValueError(f"a situation report states no {measure} shares")

    def world_warheads(self, side: Side) -> float | None:
        """The warheads of every nation in the side's report whose count is known (ADR-0005: absent is not zero);
        ``None`` when no count is known."""
        counts = [number(row.nuclear_weapons) for row in self._reports[side].nations]
        known = [count for count in counts if count is not None]
        return math.fsum(known) if known else None

    def nuclear_armed(self, nation: EntityId) -> bool:
        """Whether the nation holds warheads, on the earlier side when it is listed there."""
        for side in (Side.BEFORE, Side.AFTER):
            row = self._reports[side].nation(nation)
            if row is not None:
                weapons = number(row.nuclear_weapons)
                return weapons is not None and weapons > 0
        return False


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
    from_record: bool = False
    """The share is read from the record entry the event rests on (``Stakes.contested_share``), not from the shares of
    ``entities``."""


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


HAB_STATE_TYPE = "TIHabState"


def _habs(event: Event, stakes: Stakes) -> tuple[EntityId, ...]:
    """The habs the event lists, else its first hab (lagrange points share the domain, so the state type tells)."""
    listed = _listed_refs(event.attribute("habs"))
    refs = listed or tuple(ref for ref in event.entities if ref.state_type == HAB_STATE_TYPE)[:1]
    return tuple(ref.entity_id for ref in refs)


def _fleet(event: Event, stakes: Stakes) -> tuple[EntityId, ...]:
    return _first(event, EntityDomain.FLEET)


def _left_faction(event: Event, stakes: Stakes) -> tuple[EntityId, ...]:
    """The faction a transition leaves: its ``before`` value."""
    left = event.attribute("before")
    return (left.entity_id,) if isinstance(left, EntityRef) else ()


STAKE_IMPLEMENTATIONS: Mapping[Stake, Scaling] = {
    Stake.NATION: Scaling(StakeMeasure.POWER, _nation),
    Stake.BELLIGERENTS: Scaling(StakeMeasure.POWER, _belligerents, nuclear_bonus=True),
    Stake.TERRITORY: Scaling(StakeMeasure.POPULATION, _moved_regions),
    Stake.CONTROL_POINT: Scaling(StakeMeasure.POWER, _nation, per_point=True),
    Stake.ORGANIZATION: Scaling(StakeMeasure.ORGANIZATION, _organization),
    Stake.HAB: Scaling(StakeMeasure.HAB, _habs),
    Stake.FLEET: Scaling(StakeMeasure.FLEET, _fleet),
    Stake.LEFT_FACTION: Scaling(StakeMeasure.FACTION, _left_faction),
    Stake.COMBAT: Scaling(StakeMeasure.BATTLE, lambda event, stakes: (), from_record=True),
}
"""Every atomic ``Stake``'s implementation."""

NarrativeEntitiesOf = Callable[[Event, Sequence[Event]], tuple[EntityRef, ...]]


@dataclass(frozen=True)
class NarrativeScaling:
    """A narrative-event ``Stake``'s implementation: its measure and the entities (of the event, or of the events it
    cites) whose summed share, in the situation reports of the event's first interval, is the stake; no entities, no
    scale."""

    measure: StakeMeasure
    entities: NarrativeEntitiesOf
    nuclear_bonus: bool = False
    """Adds ``ReferenceSettings.nuclear_bonus`` when an attacker and a defender both hold warheads."""
    net_move: bool = False
    """The share is the arc's net move over the world total at its larger end (``_nuclear_share``), not the summed
    share of ``entities``."""


def _role_nations(event: Event, wanted: Role) -> tuple[EntityRef, ...]:
    return tuple(ref for role, ref in event.roles if role is wanted and ref.entity_id.domain is EntityDomain.NATION)


def _listed_refs(value: Observed) -> tuple[EntityRef, ...]:
    """The entity references of a list attribute; anything else lists none."""
    return tuple(item for item in value if isinstance(item, EntityRef)) if isinstance(value, tuple) else ()


def _actor(event: Event, cited: Sequence[Event] = ()) -> tuple[EntityRef, ...]:
    """The nation the event is about; the kinds with this stake name one actor, so a second would be another nation's
    stake."""
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


def _cited_habs(event: Event, cited: Sequence[Event]) -> tuple[EntityRef, ...]:
    """The habs of the cited first-presence events."""
    return tuple(ref for item in cited for ref in _listed_refs(item.attribute("habs")))


def _cited_ships(event: Event, cited: Sequence[Event]) -> tuple[EntityRef, ...]:
    """The ships of the cited appearance events: the first entity of each."""
    return tuple(item.entities[0] for item in cited if item.event_type == SHIP_APPEARED.event_type and item.entities)


NARRATIVE_STAKE_IMPLEMENTATIONS: Mapping[Stake, NarrativeScaling] = {
    Stake.ACTOR: NarrativeScaling(StakeMeasure.POWER, _actor),
    Stake.TARGETS: NarrativeScaling(StakeMeasure.POWER, _targets),
    Stake.WAR_SIDES: NarrativeScaling(StakeMeasure.POWER, _war_sides, nuclear_bonus=True),
    Stake.MEMBERS: NarrativeScaling(StakeMeasure.POWER, _federation_members),
    Stake.REGIONS: NarrativeScaling(StakeMeasure.POPULATION, _listed_regions),
    Stake.INDEPENDENT_NATION: NarrativeScaling(StakeMeasure.POWER, _independent_nation),
    Stake.COLONY: NarrativeScaling(StakeMeasure.HAB, _cited_habs),
    Stake.NEW_SHIPS: NarrativeScaling(StakeMeasure.FLEET, _cited_ships),
    Stake.NUCLEAR_ARC: NarrativeScaling(StakeMeasure.NUCLEAR, _actor, net_move=True),
}
"""Every narrative-event ``Stake``'s implementation."""


CODE_REFERENCES: Mapping[StakeMeasure, float] = {
    StakeMeasure.HAB: 0.015,
    StakeMeasure.FLEET: 0.01,
    StakeMeasure.BATTLE: 0.0033,
    StakeMeasure.FACTION: 1 / 7,  # an even split among the seven human factions
    StakeMeasure.NUCLEAR: 0.01,
}
"""The share at which a space, faction or nuclear stake leaves a score at its base. Code constants, not settings:
the power, population and organization references are ``ReferenceSettings``."""


def _reference(measure: StakeMeasure, settings: SignificanceSettings) -> float:
    return CODE_REFERENCES[measure] if measure in CODE_REFERENCES else float(getattr(settings.reference, measure.value))


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


def _combat_basis(event: Event, level: Significance, stakes: Stakes) -> SignificanceBasis | None:
    measured = stakes.contested_share(event)
    if measured is None:
        return None
    share, factions = measured
    return _scaled(level, StakeMeasure.BATTLE, share, factions, 0, stakes.settings)


def _basis(event: Event, level: Significance, stakes: Stakes) -> SignificanceBasis | None:
    named = _kind(event).stake
    if named is None:
        return None
    stake = STAKE_IMPLEMENTATIONS.get(named)
    if stake is None:
        raise ValueError(f"stake {named} of {event.event_type} scales a narrative event")
    if stake.from_record:
        return _combat_basis(event, level, stakes)
    entities = stake.entities(event, stakes)
    share = stakes.share(stake.measure, entities)
    if share is None:
        return None
    if stake.per_point:
        share /= _points(stakes, entities[0])
    bonus = 0
    if (
        stake.nuclear_bonus
        and len(set(entities)) > 1
        and all(_holds_nuclear_weapons(stakes, item) for item in entities)
    ):
        bonus = stakes.settings.reference.nuclear_bonus
    refs = tuple(ref for ref in event.entities if ref.entity_id in set(entities))
    return _scaled(level, stake.measure, share, refs, bonus, stakes.settings)


def _narrative_basis(
    kind: EventKind,
    event: Event,
    cited: Sequence[Event],
    level: Significance,
    stakes: ReportStakes,
    last: ReportStakes,
) -> SignificanceBasis | None:
    named = kind.stake
    if named is None:
        return None
    stake = NARRATIVE_STAKE_IMPLEMENTATIONS.get(named)
    if stake is None:
        raise ValueError(f"stake {named} of {event.event_type} scales an atomic event")
    refs = _unique(stake.entities(event, cited))
    if stake.net_move:
        share = _nuclear_share(event, stakes, last)
    else:
        share = stakes.share(stake.measure, (ref.entity_id for ref in refs))
    if share is None:
        return None
    bonus = 0
    if stake.nuclear_bonus and _armed_on_both_sides(event, stakes):
        bonus = stakes.settings.reference.nuclear_bonus
    return _scaled(level, stake.measure, share, refs, bonus, stakes.settings)


def _nuclear_share(event: Event, first: ReportStakes, last: ReportStakes) -> float | None:
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


def _armed_on_both_sides(event: Event, stakes: ReportStakes) -> bool:
    return all(any(stakes.nuclear_armed(ref.entity_id) for ref in side) for side in _sides(event))


def _unique(refs: Iterable[EntityRef]) -> tuple[EntityRef, ...]:
    """The first seen of each entity, in order."""
    seen: dict[EntityId, EntityRef] = {}
    for ref in refs:
        seen.setdefault(ref.entity_id, ref)
    return tuple(seen.values())


def _scaled(
    level: Significance,
    measure: StakeMeasure,
    share: float,
    entities: tuple[EntityRef, ...],
    bonus: int,
    settings: SignificanceSettings,
) -> SignificanceBasis:
    return SignificanceBasis(
        base=level.base,
        measure=measure,
        share=float(f"{share:.6g}"),
        scale=_scale(share, _reference(measure, settings), settings),
        entities=entities,
        bonus=bonus,
    )


def _clamped(basis: SignificanceBasis) -> int:
    return max(0, min(100, basis.base + basis.scale + basis.bonus))


# --- Entry points -----------------------------------------------------------------------------------------


def _kind(event: Event) -> EventKind:
    kind = kind_for(event.event_type)
    if kind is None:
        raise ValueError(f"event type {event.event_type} is declared by no kind")
    return kind


def _base(event: Event) -> Significance:
    return _kind(event).base


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


def narrative_score(
    kind: EventKind,
    event: Event,
    cited: Iterable[Event],
    geopolitics: GeopoliticsSettings,
    stakes: ReportStakes | None = None,
    last: ReportStakes | None = None,
) -> tuple[int, SignificanceBasis | None]:
    """The score and its basis: the higher of the kind's own score and the highest score among the ``cited`` events
    (ADR-0011). The own score is the kind's context-rule level, else its base level, moved by its stake as an atomic
    event's is; ``stakes`` are the reports of the event's first interval, and without them there is no basis. ``last``
    are the reports of its last interval (by default the first's), read only by the nuclear share.

    Raises ``ValueError`` for a kind whose context rule judges atomic events, or whose stake scales atomic events:
    each is a code bug.
    """
    cited = tuple(cited)
    level = kind.base
    if kind.rule is not None:
        rule = RULE_IMPLEMENTATIONS[kind.rule]
        if not isinstance(rule, NarrativeContextRule):
            raise ValueError(f"rule {kind.rule} of {event.event_type} judges an atomic event")
        decided = rule.judge(event, geopolitics)
        if decided is not None:
            level = decided
    basis = _narrative_basis(kind, event, cited, level, stakes, last or stakes) if stakes is not None else None
    own = level.base if basis is None else _clamped(basis)
    return max([own, *(item.score for item in cited)]), basis


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
    score = _clamped(basis)
    return replace(event, significance=Significance.of(score), score=score, significance_basis=basis)
