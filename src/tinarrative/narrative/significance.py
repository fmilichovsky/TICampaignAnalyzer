"""Significance rules: which events a campaign history keeps and which are routine churn.

Significance is the impact of an event, independent of how certain it is (architecture section 12). It is
assigned here, after the analyzers ran, so that no analyzer has to judge impact: ``assign_significance`` is a
post-pass that copies every event with its level set. The level comes from, in order:

1. a context rule in ``RULES`` for the event type (it may decline by returning ``None``);
2. the per-type ``BASE`` table;
3. ``DEFAULT`` (minor) for every other type, including every ``notification.<template>`` entry (the game's
   own log is player-centric and open-ended, so no template is ranked).

Every non-default entry states its evidence or rationale beside it. The evidence is the investigation of
2026-10-14 recorded in ``docs/game-data-notes/higher-level-event-sources.md`` (eight private saves of two
campaigns, structure and counts only). No threshold below is tuned to a single campaign. Thresholds that decide
whether an event exists at all live with the analyzer that emits it (the nation statistic shift thresholds are in
``analyzers.politics.nation_metrics``); the ``Thresholds`` block here holds only what ranks emitted events.

Known simplification: the issue text makes ``army.region_changed`` minor "without an accompanying strength
change". Both cases are minor here, because ``army.strength_changed`` is its own minor event and a combined
reading of the two is reconstruction work.
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

__all__ = ["BASE", "DEFAULT", "RULES", "SIGNIFICANCE_ORDER", "Significance", "assign_significance", "significance_of"]

logger = get_logger(__name__)

DEFAULT = Significance.MINOR
"""An event type no rule or table entry names: worth a forensic line, not a history entry."""

# --- Thresholds -------------------------------------------------------------------------------------------
# Constants that rules compare against, with their evidence. Emission thresholds live with their analyzer.

TOP_ORGANIZATION_TIER = 3
"""``TIOrgState.tier`` is 1-3 in every observed save; tier 3 is the top tier (notes, ``TIOrgState``)."""

UPHEAVAL_CAUSES = frozenset({"Coup", "RegimeChange", "Independence", "Enthrall"})
"""``lastExecutiveChange.cause`` values that replace a government outside normal politics. Observed values are
``None``, ``Politics``, ``Independence``, ``Coup``, ``RegimeChange`` and ``Enthrall`` (field map, nations)."""

WAR_RELATION = "wars"
"""The ``nation.relation_changed`` relation that names a war; ``allies`` and ``rivals`` are routine diplomacy."""

DISCRETE_STATISTICS = frozenset({"numNuclearWeapons", "numControlPoints"})
"""``nation.statistic_shifted`` statistics whose every change is a development: a nuclear arsenal (0 -> 1 on two
nations in one older interval) and the number of control points, which changed alongside the region transfers
of the sample. Continuous statistics shift past their threshold for routine reasons too (event effects,
priorities), so they stay minor until reconstruction explains them (issue #72)."""

# --- Per-type table ---------------------------------------------------------------------------------------

_TRIVIAL: tuple[str, ...] = (
    # Councilor movement and ship reassignment happen constantly between saves and say nothing on their own
    # (user review of the real sample, 2026-10-16; the issue listed both as minor).
    "councilor.location_changed",
    "ship.fleet_changed",
    # Organizations are created and removed in bulk: 12-58 added and 0-57 removed per older interval.
    "organization.appeared",
    "organization.disappeared",
    # Log housekeeping: the game prunes and rewrites kept entries (79-126 notification entries per interval).
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
    # Routine movement named minor by the issue: fleets change orbit and dock constantly, armies redeploy.
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
    # Hostile claims mark regions a nation may take by force: frequent (11-12 nations per save) and only a
    # precursor; the war or annexation that follows is the major event (issue #96).
    "nation.hostile_claims_changed",
    # A finished project is minor until a curated, documented milestone list promotes some (issue #102); many
    # projects are routine unlocks.
    "faction.project_completed",
    "faction.finished_project_names_changed",
    # Precursors of a takeover, named by the reconstruction it feeds: unrest attempts per faction and the
    # new-government date, which corroborates the executive record and control-point events (issue #96).
    "nation.unrest_attempts_changed",
    "nation.new_government_recorded",
)

_MAJOR: tuple[str, ...] = (
    # Named major by the issue.
    "control_point.controller_changed",
    "region.nation_changed",
    "nation.federation_changed",
    "councilor.faction_changed",
    "hab.appeared",
    "hab.disappeared",
    "faction.hab_destruction_recorded",
    "technology.completed",
    # Wars and federations: entities that appear with a ``startDate`` and vanish at peace.
    "war.appeared",
    "war.disappeared",
    "war.alliance_changed",
    "federation.appeared",
    "federation.disappeared",
    "federation.members_changed",
    # A declared claim redraws a nation's intent, and a rename marks a unification or a federation's growth;
    # both appear verbatim in the target history (issue #96).
    "nation.claims_changed",
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
"""Significance by event type when no context rule decides; a type absent here is ``DEFAULT``."""

# --- Context rules ----------------------------------------------------------------------------------------

Rule = Callable[[Event, Lookup], Significance | None]
"""Decides from the event's attributes and the snapshots; ``None`` defers to ``BASE``."""


def _subject(event: Event) -> EntityRef | None:
    return event.entities[0] if event.entities else None


def _side(event: Event) -> Side | None:
    side = event.attribute("side")
    return Side(side) if isinstance(side, str) and side in {item.value for item in Side} else None


def _councilor_presence(event: Event, lookup: Lookup) -> Significance | None:
    """Recruit-pool churn is trivial; a councilor with a faction that is gone is a development.

    Evidence (notes, "Recruit pool"): all 52 councilors absent from the later save and all 60 present only
    there had ``faction = null`` on their existing side, in every older interval checked, and null-faction
    councilors were exactly those with no orgs and no prior mission. A councilor whose faction is unknown on
    its existing side defers to the default.
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
    """A war entry is major; allies and rivals are routine diplomacy."""
    return Significance.MAJOR if event.attribute("relation") == WAR_RELATION else Significance.MINOR


def _executive_change(event: Event, lookup: Lookup) -> Significance | None:
    """A government replaced by coup, regime change, independence or enthrallment is major; elections are not."""
    cause = event.attribute("cause")
    return Significance.MAJOR if isinstance(cause, str) and cause in UPHEAVAL_CAUSES else Significance.MINOR


def _organization_assignment(event: Event, lookup: Lookup) -> Significance | None:
    """A top-tier organization changing hands is major; ``assignedCouncilor`` changed on 60-83 orgs per interval."""
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
    """A nuclear arsenal or control-point count changing is major; a continuous statistic's shift is minor."""
    return Significance.MAJOR if event.attribute("statistic") in DISCRETE_STATISTICS else Significance.MINOR


def _army_presence(event: Event, lookup: Lookup) -> Significance | None:
    """Megafauna appearing or vanishing (0 or 1 per save) is major; regular army presence is routine."""
    return Significance.MAJOR if event.attribute("megafauna") is True else Significance.MINOR


RULES: Mapping[str, Rule] = {
    "councilor.appeared": _councilor_presence,
    "councilor.disappeared": _councilor_presence,
    "nation.relation_changed": _relation_changed,
    "nation.executive_change_recorded": _executive_change,
    "organization.assigned_councilor_changed": _organization_assignment,
    "nation.statistic_shifted": _statistic_shifted,
    "army.appeared": _army_presence,
    "army.disappeared": _army_presence,
}
"""Context rules by event type, tried before ``BASE``."""

# --- Entry points -----------------------------------------------------------------------------------------


def significance_of(event: Event, lookup: Lookup) -> Significance:
    """The level for one event: its context rule, else the per-type table, else the default."""
    rule = RULES.get(event.event_type)
    if rule is not None:
        decided = rule(event, lookup)
        if decided is not None:
            return decided
    return BASE.get(event.event_type, DEFAULT)


def assign_significance(events: Iterable[Event], before: SaveSnapshot, after: SaveSnapshot) -> tuple[Event, ...]:
    """Every event with its significance set, in the given order; the snapshots supply the rules' context."""
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
