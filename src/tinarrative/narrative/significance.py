"""Significance rules: which events a campaign history keeps and which are routine churn. See ADR-0011.

A post-pass, so no analyzer has to judge impact. Evidence for the entries is in
``docs/game-data-notes/higher-level-event-sources.md``. Notification templates are never ranked: the game's own log
is player-centric and open-ended. Narrative events are not ranked here, as they span intervals and no snapshot is kept
for them.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace

from ..analyzers.common import Lookup, Side
from ..config import DEFAULT_SETTINGS, SignificanceSettings
from ..kinds import kind_of
from ..kinds.nations import REGION_NATION_CHANGED
from ..log import fields as log_fields
from ..log import get_logger
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import SIGNIFICANCE_ORDER, Event, Significance, SignificanceBasis
from ..model.kinds import Rule, Stake, StakeMeasure
from ..model.snapshot import SaveSnapshot
from .milestones import milestone_of
from .prominence import nation_power, organization_shares, region_shares, total

__all__ = [
    "BASE",
    "DEFAULT",
    "RULES",
    "RULE_IMPLEMENTATIONS",
    "SCALED",
    "SIGNIFICANCE_ORDER",
    "STAKE_IMPLEMENTATIONS",
    "Scaling",
    "Significance",
    "Stakes",
    "assign_significance",
    "significance_of",
]

logger = get_logger(__name__)

DEFAULT = Significance.MINOR
"""An event type no kind, rule or table entry names: worth a forensic line, not a history entry."""

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

# --- Per-type table ---------------------------------------------------------------------------------------
# The types not yet migrated to a kind; a kind declares its own base level, context rule and stake.

_TRIVIAL: tuple[str, ...] = (
    # Councilor movement and ship reassignment happen constantly between saves and say nothing on their own.
    "councilor.location_changed",
    "ship.fleet_changed",
    # Organizations are created and removed in bulk.
    "organization.appeared",
    "organization.disappeared",
    # Log housekeeping: the game prunes and rewrites kept entries.
    "faction.combat_entry_removed",
    # Progress-only technology states come and go with research priorities; completion is its own event.
    "technology.appeared",
    "technology.disappeared",
    # A refit date is maintenance bookkeeping.
    "ship.last_refit_date_changed",
    # Leftover list events that mirror an asset's owner field: the owner field already produced the event
    # (``army.region_changed``, ``fleet.faction_changed``, ``ship.fleet_changed``, ...), and what is left is a
    # mirror entry nothing claimed, typically a list unresolved on one side.
    "faction.armies_changed",
    "nation.armies_changed",
    "region.armies_changed",
    "faction.fleets_changed",
    "hab.docked_fleets_changed",
    "fleet.ships_changed",
    "councilor.orgs_changed",
    "faction.unassigned_orgs_changed",
    "research.finished_techs_changed",
)

_MINOR: tuple[str, ...] = (
    # A hab appears at launch; it is founded when its core completes (``hab.established``), often a year later.
    "hab.appeared",
    # Routine movement: fleets change orbit and dock constantly, armies redeploy.
    "fleet.orbit_changed",
    "fleet.barycenter_changed",
    "fleet.docked_location_changed",
    "army.region_changed",
    # Geopolitical leftover lists: emitted only for an entry no explaining event claimed (the explained cases
    # are ``region.nation_changed``, ``nation.relation_changed``, ``nation.breakaway_parent_changed``,
    # ``control_point.controller_changed``, councilor events, ``war.alliance_changed`` and war presence). They
    # stay visible so the unexplained residue is never hidden; promoting one is reconstruction work.
    "nation.wars_changed",
    "faction.control_points_changed",
    "nation.control_points_changed",
    "faction.councilors_changed",
    "war.attacking_alliance_changed",
    "war.defending_alliance_changed",
    "campaign.interstate_wars_changed",
    # A recorded control-point loss corroborates ``control_point.controller_changed`` in the same interval, so
    # it is not counted as a second major event.
    "control_point.loss_recorded",
    "faction.finished_project_names_changed",
)

_MAJOR: tuple[str, ...] = (
    # Core political and asset-ownership changes.
    "control_point.controller_changed",
    "nation.federation_changed",
    "councilor.faction_changed",
    "hab.disappeared",
    "faction.hab_destruction_recorded",
    # Wars and federations: entities that appear with a ``startDate`` and vanish at peace.
    "war.appeared",
    "war.disappeared",
    "war.alliance_changed",
    "federation.appeared",
    "federation.disappeared",
    "federation.members_changed",
    # A federation's rename marks its growth, which a history reports.
    "federation.renamed",
    # A councilor detained by another faction, an asset changing hands, an army's ``destroyed`` flag.
    "councilor.detaining_faction_changed",
    "army.faction_changed",
    "army.destroyed_changed",
    "fleet.faction_changed",
    "hab.faction_changed",
    # An organization changing councilors: its tier² share scales it from here (``SCALED``); a minor one falls
    # below the band.
    "organization.assigned_councilor_changed",
    # Space battles (``CombatLogs``).
    "faction.combat_recorded",
    # Inferred nation control: the executive seat, the plurality or every control point changing hands is what a
    # history reports about the ``control_point.controller_changed`` events it cites; a tie stays major.
    "faction.nation_control_changed",
    # Inferred readings of space evidence: a working hab, a new foothold, a hab lost to an enemy and a battle won
    # are what a history reports about the ``hab.*`` and log events they cite.
    "hab.established",
    "faction.first_hab_on_body",
    "hab.destroyed",
    "faction.battle_outcome",
)

_CAMPAIGN_DEFINING: tuple[str, ...] = ()

BASE: Mapping[str, Significance] = {
    **dict.fromkeys(_TRIVIAL, Significance.TRIVIAL),
    **dict.fromkeys(_MINOR, Significance.MINOR),
    **dict.fromkeys(_MAJOR, Significance.MAJOR),
    **dict.fromkeys(_CAMPAIGN_DEFINING, Significance.CAMPAIGN_DEFINING),
}
"""A type absent here is ``DEFAULT``."""

# --- Context rules ----------------------------------------------------------------------------------------

ContextRule = Callable[[Event, Lookup], Significance | None]
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


RULE_IMPLEMENTATIONS: Mapping[Rule, ContextRule] = {
    Rule.COUNCILOR_PRESENCE: _councilor_presence,
    Rule.RELATION_CHANGED: _relation_changed,
    Rule.CLAIMS_CHANGED: _claims_changed,
    Rule.EXECUTIVE_CHANGE: _executive_change,
    Rule.STATISTIC_SHIFTED: _statistic_shifted,
    Rule.POPULATION_CHANGED: _population_changed,
    Rule.SPACE_ASSETS_CHANGED: _space_assets_changed,
    Rule.ARMY_PRESENCE: _army_presence,
    Rule.COMPLETION: _completion,
}
"""Every ``Rule``'s implementation."""

RULES: Mapping[str, Rule] = {
    "councilor.appeared": Rule.COUNCILOR_PRESENCE,
    "councilor.disappeared": Rule.COUNCILOR_PRESENCE,
    "army.appeared": Rule.ARMY_PRESENCE,
    "army.disappeared": Rule.ARMY_PRESENCE,
    "technology.completed": Rule.COMPLETION,
    "faction.project_completed": Rule.COMPLETION,
}
"""The context rule of a type not yet migrated to a kind; tried before ``BASE``."""

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

SCALED: Mapping[str, Stake] = {
    "nation.federation_changed": Stake.NATION,
    "control_point.controller_changed": Stake.CONTROL_POINT,
    "faction.nation_control_changed": Stake.NATION,
    "organization.assigned_councilor_changed": Stake.ORGANIZATION,
}
"""The stake of a type not yet migrated to a kind (ADR-0011); movement and churn are never listed."""


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
    kind = kind_of(event.event_type)
    named = kind.stake if kind is not None else SCALED.get(event.event_type)
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


def significance_of(event: Event, lookup: Lookup) -> Significance:
    """The context rule, else the base level, else ``DEFAULT``: the level before the stake scales the score.

    A type's kind is read first; a type not yet migrated to a kind is read from ``RULES`` and ``BASE``.
    """
    kind = kind_of(event.event_type)
    rule = kind.rule if kind is not None else RULES.get(event.event_type)
    if rule is not None:
        decided = RULE_IMPLEMENTATIONS[rule](event, lookup)
        if decided is not None:
            return decided
    base = kind.base if kind is not None else BASE.get(event.event_type)
    return base if base is not None else DEFAULT


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
