"""Code form of the observed ``gamestates`` key inventory.

This mirrors ``docs/game-data-notes/state-type-inventory.md``: the exact keys seen in the inspected saves. It
exists so that the parser can *report* a key it has never seen; it is never used to reject a save, because a
new game build may add state types that must be preserved rather than refused.
"""

from __future__ import annotations

from ..identity import STATE_PREFIX

_PREFIXED_SHORT_TYPES: tuple[str, ...] = (
    "TIMetadataState",
    "TITimeState",
    "TIFactionState",
    "TIPlayerState",
    "TIEffectsState",
    "TIGlobalResearchState",
    "TIGlobalValuesState",
    "TINationState",
    "TIControlPoint",
    "TIRegionState",
    "TIRegionAlienActivityState",
    "TIRegionAlienFacilityState",
    "TIRegionUFOCrashdownState",
    "TIRegionUFOLandingState",
    "TIRegionXenoformingState",
    "TIArmyState",
    "TIMegafaunaArmyState",
    "TICouncilorState",
    "TIOrgState",
    "TIFederationState",
    "TIWarState",
    "TILaunchFacilityState",
    "TIMissionControlFacilityState",
    "TISpaceDefensesFacilityState",
    "TIMissionState",
    "TIMissionPhaseState",
    "TITimeEvent",
    "TINotificationQueueState",
    "TIPromptQueueState",
    "TISpaceBodyState",
    "TILagrangePointState",
    "TIOrbitState",
    "TIAdHocOrbitState",
    "TISectorState",
    "TIHabSiteState",
    "TIHabState",
    "TIHabModuleState",
    "TISpaceFleetState",
    "TISpaceShipState",
    "TIOfficerState",
    "TISpaceCombatState",
    "TISpaceCombatProjectileState",
    "FactionGoal_AssembleFleet",
    "FactionGoal_AttackWithFleet",
    "FactionGoal_BuildFullBase",
    "FactionGoal_BuildFullStation",
    "FactionGoal_BuildMiningBase",
    "FactionGoal_BuildRefuellingStation",
    "FactionGoal_CaptureHab",
    "FactionGoal_CaptureNation_Clean",
    "FactionGoal_CaptureNation_Dirty",
    "FactionGoal_DefendWithFleet",
    "FactionGoal_DevelopNation",
    "FactionGoal_ExpandNation",
    "FactionGoal_FoundBase",
    "FactionGoal_FoundMaxStation",
    "FactionGoal_FoundPlatform",
    "FactionGoal_FoundSurveillanceStation",
    "FactionGoal_InvadeEarth",
    "FactionGoal_JoinFleet",
    "FactionGoal_MilitarizeNation",
    "FactionGoal_NeutralizeNation",
    "FactionGoal_NonAggressionPact",
    "FactionGoal_ProspectSites",
    "FactionGoal_RefitFleet",
    "FactionGoal_RepairFleet",
    "FactionGoal_ResupplyFleet",
    "FactionGoal_SecureEarthSpace",
    "FactionGoal_SendFleet",
    "FactionGoal_SpaceifyNation",
    "FactionGoal_SurveilEarth",
    "FactionGoal_TransportCouncilorsWithFleet",
    "FactionGoal_TruceWithFaction",
    "FactionGoal_Victory",
    "FactionGoal_WarOnFaction",
)

_BARE_KEYS: tuple[str, ...] = ("TIHistoricalData",)
"""Inventory keys serialized without the ``PavonisInteractive.TerraInvicta.`` prefix."""

KNOWN_STATE_TYPES: frozenset[str] = frozenset(STATE_PREFIX + short for short in _PREFIXED_SHORT_TYPES) | frozenset(
    _BARE_KEYS
)
"""Every ``gamestates`` key observed on 2026-09-08; a key outside this set is reported as an unknown state type."""


def short_state_type(key: str) -> str:
    """The state type as the rest of the package names it: the key without the observed namespace prefix."""
    return key.removeprefix(STATE_PREFIX)
