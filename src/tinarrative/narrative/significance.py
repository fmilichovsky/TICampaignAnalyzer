"""Significance rules: which events a campaign history keeps and which are routine churn. See architecture section 12.

A post-pass, so no analyzer has to judge impact. Evidence for the entries is in
``docs/game-data-notes/higher-level-event-sources.md``. Notification templates are never ranked: the game's own log
is player-centric and open-ended. Narrative events are not ranked here, as they span intervals and no snapshot is kept
for them.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace

from ..analyzers.common import Lookup, Side
from ..log import fields as log_fields
from ..log import get_logger
from ..model.entities import EntityRef
from ..model.events import SIGNIFICANCE_ORDER, Event, Significance
from ..model.snapshot import SaveSnapshot
from .milestones import milestone_of

__all__ = ["BASE", "DEFAULT", "RULES", "SIGNIFICANCE_ORDER", "Significance", "assign_significance", "significance_of"]

logger = get_logger(__name__)

DEFAULT = Significance.MINOR
"""An event type no rule or table entry names: worth a forensic line, not a history entry."""

# --- Thresholds -------------------------------------------------------------------------------------------
# Only what ranks emitted events; thresholds that decide whether an event exists live with its analyzer.

TOP_ORGANIZATION_TIER = 3
"""``TIOrgState.tier`` runs 1-3; tier 3 is the top tier (notes, ``TIOrgState``)."""

UPHEAVAL_CAUSES = frozenset({"Coup", "RegimeChange", "Independence", "Enthrall"})
"""``lastExecutiveChange.cause`` values that replace a government outside normal politics (field map, nations)."""

WAR_RELATION = "wars"
"""The ``nation.relation_changed`` relation that names a war; ``allies`` and ``rivals`` are routine diplomacy."""

DISCRETE_STATISTICS = frozenset({"numNuclearWeapons"})
"""``nation.statistic_shifted`` statistics whose every change is a development: a nuclear arsenal. Other statistics
shift past their threshold for routine reasons too (event effects, priorities), so a shift is evidence for the rules
that explain it and stays trivial on its own."""

# --- Per-type table ---------------------------------------------------------------------------------------

_TRIVIAL: tuple[str, ...] = (
    # Councilor movement and ship reassignment happen constantly between saves and say nothing on their own.
    "councilor.location_changed",
    "ship.fleet_changed",
    # Organizations are created and removed in bulk.
    "organization.appeared",
    "organization.disappeared",
    # A band crossing is the evidence a band-shift development is built from; on its own it may be the game
    # converging the statistic towards its rest value.
    "nation.band_crossed",
    # A per-capita GDP trend is the evidence an economic trajectory is built from.
    "nation.pcgdp_trend",
    # A nation's place by a metric moves whenever one of the nations around it changes; the ranking development
    # states the changes of the top.
    "nation.rank_changed",
    # Log housekeeping: the game prunes and rewrites kept entries.
    "notification.entry_removed",
    "notification.entry_changed",
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
    # Routine movement: fleets change orbit and dock constantly, armies redeploy.
    "fleet.orbit_changed",
    "fleet.barycenter_changed",
    "fleet.docked_location_changed",
    "army.region_changed",
    # Geopolitical leftover lists: emitted only for an entry no explaining event claimed (the explained cases
    # are ``region.nation_changed``, ``nation.relation_changed``, ``nation.breakaway_parent_changed``,
    # ``control_point.controller_changed``, councilor events, ``war.alliance_changed`` and war presence). They
    # stay visible so the unexplained residue is never hidden; promoting one is reconstruction work.
    "nation.regions_changed",
    "nation.breakaways_changed",
    "nation.allies_changed",
    "nation.rivals_changed",
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
    # Inferred aggregates of the ``region.nation_changed`` events they cite, which are already major; ranking
    # them major too would count one transfer twice.
    "nation.territory_gained",
    "nation.territory_lost",
    # Hostile claims mark regions a nation may take by force: frequent and only a
    # precursor; the war or annexation that follows is the major event.
    "nation.hostile_claims_changed",
    "faction.finished_project_names_changed",
    # Precursors of a takeover, named by the reconstruction it feeds: unrest attempts per faction and the
    # new-government date, which corroborates the executive record and control-point events.
    "nation.unrest_attempts_changed",
    "nation.new_government_recorded",
    # A dated mission or operation charge from the resource ledger: corroboration and dating for an effect that
    # is evidenced elsewhere, never a development on its own (architecture 11.3).
    "faction.transaction_recorded",
)

_MAJOR: tuple[str, ...] = (
    # Core political and asset-ownership changes.
    "control_point.controller_changed",
    "region.nation_changed",
    "nation.federation_changed",
    "councilor.faction_changed",
    "hab.appeared",
    "hab.disappeared",
    "faction.hab_destruction_recorded",
    # Wars and federations: entities that appear with a ``startDate`` and vanish at peace.
    "war.appeared",
    "war.disappeared",
    "war.alliance_changed",
    "federation.appeared",
    "federation.disappeared",
    "federation.members_changed",
    # A rename marks a unification or a federation's growth, which a history reports; claims are decided by
    # their context rule.
    "nation.renamed",
    "federation.renamed",
    # A councilor detained by another faction, an asset changing hands, an army's ``destroyed`` flag.
    "councilor.detaining_faction_changed",
    "army.faction_changed",
    "army.destroyed_changed",
    "fleet.faction_changed",
    "hab.faction_changed",
    # Space battles (``CombatLogs``) and alien activity on Earth (crashdowns, landings, facilities).
    "faction.combat_recorded",
    "region.crashdown_changed",
    "region.landing_changed",
    "region.alien_facility_changed",
    # A once-per-campaign narrative event.
    "campaign.narrative_event_triggered",
    # Inferred readings of a territory change: they redraw the political map as ``region.nation_changed`` does,
    # and a whole-nation unification or an independence is what a history reports about it.
    "nation.independence",
    "nation.unification",
    "nation.annexation",
    # Inferred nation control: the executive seat, the plurality or every control point changing hands is what a
    # history reports about the ``control_point.controller_changed`` events it cites; a tie stays major.
    "faction.nation_control_changed",
    # Inferred readings of space evidence: a new foothold, a hab lost to an enemy and a battle won are what a
    # history reports about the ``hab.*`` and log events they cite.
    "faction.first_hab_on_body",
    "hab.destroyed",
    "faction.battle_outcome",
)

_CAMPAIGN_DEFINING: tuple[str, ...] = (
    # Campaign-wide firsts, nuclear use, climate stages and the birth or end of a nation.
    "campaign.global_milestone_recorded",
    "campaign.nuclear_strikes_changed",
    "campaign.sea_level_rise_triggered",
    "nation.appeared",
    "nation.disappeared",
)

BASE: Mapping[str, Significance] = {
    **dict.fromkeys(_TRIVIAL, Significance.TRIVIAL),
    **dict.fromkeys(_MINOR, Significance.MINOR),
    **dict.fromkeys(_MAJOR, Significance.MAJOR),
    **dict.fromkeys(_CAMPAIGN_DEFINING, Significance.CAMPAIGN_DEFINING),
}
"""A type absent here is ``DEFAULT``."""

# --- Context rules ----------------------------------------------------------------------------------------

Rule = Callable[[Event, Lookup], Significance | None]
"""``None`` defers to ``BASE``."""


def _subject(event: Event) -> EntityRef | None:
    return event.entities[0] if event.entities else None


def _side(event: Event) -> Side | None:
    side = event.attribute("side")
    return Side(side) if isinstance(side, str) and side in {item.value for item in Side} else None


def _councilor_presence(event: Event, lookup: Lookup) -> Significance | None:
    """Recruit-pool churn is trivial; a councilor with a faction that is gone is a development.

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


def _organization_assignment(event: Event, lookup: Lookup) -> Significance | None:
    """Only a top-tier organization changing hands is major: ``assignedCouncilor`` changes on many orgs per
    interval."""
    subject = _subject(event)
    if subject is None:
        return None
    for side in (Side.BEFORE, Side.AFTER):
        state = lookup.state(subject.entity_id, side)
        if state is not None:
            tier = state.get("tier")
            if isinstance(tier, int) and not isinstance(tier, bool) and tier >= TOP_ORGANIZATION_TIER:
                return Significance.MAJOR
    return Significance.MINOR


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


RULES: Mapping[str, Rule] = {
    "councilor.appeared": _councilor_presence,
    "councilor.disappeared": _councilor_presence,
    "nation.relation_changed": _relation_changed,
    "nation.claims_changed": _claims_changed,
    "nation.executive_change_recorded": _executive_change,
    "organization.assigned_councilor_changed": _organization_assignment,
    "nation.statistic_shifted": _statistic_shifted,
    "nation.population_changed": _population_changed,
    "nation.space_assets_changed": _space_assets_changed,
    "army.appeared": _army_presence,
    "army.disappeared": _army_presence,
    "technology.completed": _completion,
    "faction.project_completed": _completion,
}
"""Tried before ``BASE``."""

# --- Entry points -----------------------------------------------------------------------------------------


def significance_of(event: Event, lookup: Lookup) -> Significance:
    """The context rule, else ``BASE``, else ``DEFAULT``."""
    rule = RULES.get(event.event_type)
    if rule is not None:
        decided = rule(event, lookup)
        if decided is not None:
            return decided
    return BASE.get(event.event_type, DEFAULT)


def assign_significance(events: Iterable[Event], before: SaveSnapshot, after: SaveSnapshot) -> tuple[Event, ...]:
    """Keeps the given order."""
    lookup = Lookup(before, after)
    assigned = tuple(replace(event, significance=significance_of(event, lookup)) for event in events)
    if logger.isEnabledFor(logging.DEBUG):
        counts = Counter(event.significance.value for event in assigned)
        logger.debug(
            "significance assigned %s",
            log_fields(
                events=len(assigned), **{level.value: counts.get(level.value, 0) for level in SIGNIFICANCE_ORDER}
            ),
        )
    return assigned
