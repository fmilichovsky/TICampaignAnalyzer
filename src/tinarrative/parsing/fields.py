"""Observed field names per normalized state type.

This is the code form of ``docs/game-data-notes/domain-field-map.md``: only fields observed in real saves
are listed, and a reference field is resolved only when its observed target type has an entity domain.
Three tables describe a state type's members: ``ENTITY_FIELDS`` (copied into the entity state),
``RECORD_FIELDS`` (decoded into save-carried records) and ``ACKNOWLEDGED_FIELDS`` (known, deliberately
not normalized).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..model.entities import EntityDomain
from ..model.records import RecordKind
from .references import ExpectedDomains, as_domains

COMMON_FIELDS = ("templateName", "displayName", "archived", "exists")

_ARMY_FIELDS = COMMON_FIELDS + (
    "currentRegion",
    "faction",
    "homeRegion",
    "priorRegion",
    "strength",
    "operationTarget",
    "destroyed",
    "armyType",
    "deploymentType",
    "destinationQueue",
    "currentOperations",
    "destinationSeaDate",
    "embarkDate",
    "huntingXenofauna",
)

ENTITY_FIELDS: dict[str, tuple[str, ...]] = {
    "TIFactionState": COMMON_FIELDS
    + (
        "player",
        "councilors",
        "knownSpies",
        "fleets",
        "habSectors",
        "controlPoints",
        "armies",
        "resources",
        "finishedProjectNames",
        "currentProjectProgress",
        "researchWeights",
        "intel",
        "factionGoals",
        "knowsWinCondition",
        "unlockedVictoryObjective",
        "defeated",
        "sabotagedProjects",
        "unassignedOrgs",
        "shipDesigns",
        "shipsBuiltInClass",
        "techNameContributionHistory",
    ),
    "TINationState": COMMON_FIELDS
    + (
        "capital",
        "regions",
        "allies",
        "rivals",
        "claims",
        "wars",
        "armies",
        "publicOpinion",
        "GDP",
        "inequality",
        "education",
        "democracy",
        "cohesion",
        "unrest",
        "militaryTechLevel",
        "controlPoints",
        "federation",
        "breakawayParent",
        "breakaways",
        "originalCapital",
        "hostileClaims",
        "advisingCouncilors",
        "aggregateNation",
        "alienNation",
        "military",
        "nuclearProgram",
        "numNuclearWeapons",
        "spaceFlightProgram",
        "spaceFunding_year",
        "sustainability",
        "numControlPoints",
        "policy_closedBorders",
        "policy_noMineralDevelopment",
        "policy_noNukes",
        "policy_noOilDevelopment",
        "factionUnrestAttempts",
        "tracker_CohesionChangeReason_AllTime",
        "tracker_DemocracyChangeReason_AllTime",
        "tracker_EducationChangeReason_AllTime",
        "tracker_GDPChangeReason_AllTime",
        "tracker_InequalityChangeReason_AllTime",
        "tracker_UnrestChangeReason_AllTime",
        "tracker_PCGDP_ByQuarter",
    ),
    "TIControlPoint": COMMON_FIELDS
    + (
        "nation",
        "faction",
        "benefitsDisabled",
        "defended",
        "crackdownExpiration",
        "defendExpiration",
        "controlPointType",
        "positionInNation",
        "controlPointPriorities",
    ),
    "TIRegionState": COMMON_FIELDS
    + (
        "nation",
        "leadOccupier",
        "occupations",
        "populationInMillions",
        "alienFacility",
        "alienActivity",
        "xenoforming",
        "isBeingAnnexed",
        "annexingArmy",
        "adjacencies",
        "armies",
        "abductions",
        "alienCrashdown",
        "alienLanding",
        "boostFacility",
        "missionControlFacility",
        "spaceDefenseFacility",
        "spaceFacilities",
        "originalColony",
        "annexationBeginDate",
        "annexationDaysLeft",
        "antiSpaceDefenses",
        "boostPerYear_dekatons",
        "missionControl",
        "numSTOFighters",
        "isCounterfiring",
        "nuclearDetonations",
        "underBombardment",
        "colonyRegion",
        "permanentlyDecolonized",
        "coreEconomicRegion",
        "oilRegion",
        "resourceRegion",
        "oceanType",
    ),
    "TICouncilorState": COMMON_FIELDS
    + (
        "faction",
        "agentForFaction",
        "location",
        "priorLocation",
        "homeRegion",
        "detainingFaction",
        "recruitDate",
        "detainedReleaseDate",
        "attributes",
        "activeMission",
        "completedMission",
        "orgs",
        "status",
        "XP",
        "typeTemplateName",
        "traitTemplateNames",
        "ancestry",
        "gender",
        "dateBorn",
        "assassinations",
        "knowsIveBeenSeenBy",
        "priorMissionTemplateName",
        "protectingTarget",
    ),
    "TIArmyState": _ARMY_FIELDS,
    "TIMegafaunaArmyState": _ARMY_FIELDS + ("bonusTechLevel",),
    "TISpaceFleetState": COMMON_FIELDS
    + (
        "ships",
        "trajectory",
        "inAccelerationPhase",
        "inDecelerationPhase",
        "homeport",
        "barycenter",
        "combatState",
        "parentFleet",
        "faction",
        "orbitState",
        "dockedLocation",
        "inCombat",
        "globalPosition",
        "displayNameByFaction",
        "currentOperations",
        "huntingXenofauna",
        "unavailableForOperations",
        "bombardmentTarget",
        "bombardmentTargetBracketStatus",
        "endBombardmentReason",
        "timeOfLastFireMission",
    ),
    "TISpaceShipState": COMMON_FIELDS
    + (
        "fleet",
        "launchDate",
        "lastRefitDate",
        "propellant_tons",
        "kills",
        "officers",
        "storedFaction",
        "cruiseAcceleration_mps2",
        "combatAcceleration_mps2",
        "currentDeltaV_kps",
        "currentMaxDeltaV_kps",
        "currentMass_kg",
        "armor",
        "damagedParts",
        "damagedSystems",
        "isDamageControlSuspended",
    ),
    "TIHabState": COMMON_FIELDS
    + (
        "faction",
        "orbitState",
        "habSite",
        "barycenter",
        "sectors",
        "districts",
        "dockedFleets",
        "councilorsOnBoard",
        "officersOnBoard",
        "advisingCouncilors",
        "habType",
        "tier",
        "inCombat",
        "underAssault",
        "underBombardment",
        "anyCoreCompleted",
        "coreDefended",
        "coreDefendExpiration",
        "staticHab",
        "inEarthLEO",
        "globalPosition",
    ),
}
"""Fields copied into each ``EntityState``; anything else serialized on the object is ignored."""

RESEARCH_STATE_TYPE = "TIGlobalResearchState"
RESEARCH_FIELDS = (
    "finishedTechsNames",
    "finishedOneTimeOnlyProjectNames",
    "techProgress",
    "campaignStartYear",
    "endGameTechsCompletedByCategory",
)
"""Singleton research fields copied into ``ResearchState``; technologies are derived from the first three."""

TIME_FIELDS = (
    "currentDateTime",
    "daysInCampaign",
    "currentQuarterSinceStart",
    "masterMetaTemplateName",
    "scenarioMetaTemplateName",
)
"""``TITimeState`` singleton fields read into ``SaveSnapshot`` chronology and ``CampaignMetadata``."""

METADATA_FIELDS = (
    "playerFactionName",
    "difficulty",
    "playedWithMods",
    "gameTimeString",
    "selectedFactionsForScenario",
)
"""``TIMetadataState`` singleton fields read into ``CampaignMetadata``."""

SINGLETON_FIELDS: dict[str, tuple[str, ...]] = {
    "TITimeState": TIME_FIELDS,
    "TIMetadataState": METADATA_FIELDS,
    RESEARCH_STATE_TYPE: RESEARCH_FIELDS,
}
"""The singleton state types the normalizer reads, with the fields it copies from each."""

_ARMY_LIST = (EntityDomain.ARMY, True)
_FACTION = (EntityDomain.FACTION, False)
_REGION = (EntityDomain.REGION, False)
_SPACE_OBJECT = (EntityDomain.SPACE_OBJECT, False)
_PLACE = (frozenset((EntityDomain.REGION, EntityDomain.SPACE_OBJECT, EntityDomain.SHIP)), False)
"""A councilor location: observed to point at a ``TIRegionState``, a ``TIHabState`` or (once) a ``TISpaceShipState``."""

_ARMY_REFERENCES: dict[str, tuple[ExpectedDomains, bool]] = {
    "currentRegion": _REGION,
    "homeRegion": _REGION,
    "priorRegion": _REGION,
    "faction": _FACTION,
}

REFERENCE_FIELDS: dict[str, dict[str, tuple[ExpectedDomains, bool]]] = {
    "TIFactionState": {
        "councilors": (EntityDomain.COUNCILOR, True),
        "fleets": (EntityDomain.FLEET, True),
        "controlPoints": (EntityDomain.CONTROL_POINT, True),
        "armies": _ARMY_LIST,
        "unassignedOrgs": (EntityDomain.ORGANIZATION, True),
    },
    "TINationState": {
        "capital": (EntityDomain.REGION, False),
        "originalCapital": (EntityDomain.REGION, False),
        "regions": (EntityDomain.REGION, True),
        "claims": (EntityDomain.REGION, True),
        "hostileClaims": (EntityDomain.REGION, True),
        "allies": (EntityDomain.NATION, True),
        "rivals": (EntityDomain.NATION, True),
        "wars": (EntityDomain.NATION, True),
        "breakaways": (EntityDomain.NATION, True),
        "breakawayParent": (EntityDomain.NATION, False),
        "controlPoints": (EntityDomain.CONTROL_POINT, True),
        "armies": _ARMY_LIST,
    },
    "TIControlPoint": {
        "nation": (EntityDomain.NATION, False),
        "faction": (EntityDomain.FACTION, False),
    },
    "TIRegionState": {
        "nation": (EntityDomain.NATION, False),
        "originalColony": (EntityDomain.NATION, False),
        "armies": _ARMY_LIST,
    },
    "TICouncilorState": {
        "faction": _FACTION,
        "detainingFaction": _FACTION,
        "homeRegion": _REGION,
        "location": _PLACE,
        "priorLocation": _PLACE,
        "orgs": (EntityDomain.ORGANIZATION, True),
        "knowsIveBeenSeenBy": (EntityDomain.FACTION, True),
    },
    "TIArmyState": _ARMY_REFERENCES,
    "TIMegafaunaArmyState": _ARMY_REFERENCES,
    "TISpaceFleetState": {
        "ships": (EntityDomain.SHIP, True),
        "parentFleet": (EntityDomain.FLEET, False),
        "faction": _FACTION,
        "orbitState": _SPACE_OBJECT,
        "barycenter": _SPACE_OBJECT,
        "dockedLocation": _SPACE_OBJECT,
    },
    "TISpaceShipState": {
        "fleet": (EntityDomain.FLEET, False),
    },
    "TIHabState": {
        "faction": _FACTION,
        "orbitState": _SPACE_OBJECT,
        "habSite": _SPACE_OBJECT,
        "barycenter": _SPACE_OBJECT,
        "dockedFleets": (EntityDomain.FLEET, True),
        "councilorsOnBoard": (EntityDomain.COUNCILOR, True),
    },
}
"""Reference fields and their observed target domain(s); ``True`` marks a list of references.

Reference-shaped fields whose observed target type has no ``EntityDomain`` (officers, missions, sectors,
hab modules, region facility and alien sub-states) or whose target was never observed non-null
(``agentForFaction``, ``storedFaction``) are deliberately absent and stay raw. A fleet's ``bombardmentTarget`` and
``currentOperations`` stay raw too: their targets include a domain-less ``TIRegionXenoformingState``, and operation
dates can be ``$ref`` graph nodes.
"""

KEYED_LIST_FIELDS: dict[str, dict[str, str]] = {
    "TIFactionState": {"shipDesigns": "dataName"},
}
"""List-of-object fields copied as a ``FrozenMap`` keyed by the named string member, per state type.

Observed unique within each list (``shipDesigns``: ship ``templateName`` points at a design ``dataName``), so
keying by it lets the diff compare designs one by one instead of the whole list as one value. Each element is
copied whole. A list that does not have this shape stays raw as ``Unknown(unparseable)`` and is reported.
"""

PAIR_MAP_FIELDS: dict[str, dict[str, ExpectedDomains | None]] = {
    "TINationState": {"factionUnrestAttempts": EntityDomain.FACTION, "tracker_PCGDP_ByQuarter": None},
    "TICouncilorState": {"assassinations": EntityDomain.FACTION},
    "TISpaceFleetState": {"displayNameByFaction": EntityDomain.FACTION},
}
"""Entity fields serialized as a field-level pair map, with the keys' observed target domain(s); ``None`` marks
integer keys (``tracker_PCGDP_ByQuarter``: quarter index -> value), which are not references.

Each is also in ``ENTITY_FIELDS``. The normalizer decodes it (``{}`` when empty, otherwise ``Key``/``Value``
objects) into a ``FrozenMap`` from each key's ``EntityId`` text (``faction:12``), or the integer key's decimal
text, to the frozen ``Value``, so the diff compares it key by key. A key that does not resolve makes the whole
field unresolved, as in a reference list.
"""

NORMALIZED_DOMAINS: tuple[tuple[EntityDomain, str, str], ...] = (
    (EntityDomain.FACTION, "TIFactionState", "factions"),
    (EntityDomain.NATION, "TINationState", "nations"),
    (EntityDomain.REGION, "TIRegionState", "regions"),
    (EntityDomain.CONTROL_POINT, "TIControlPoint", "control_points"),
    (EntityDomain.COUNCILOR, "TICouncilorState", "councilors"),
    (EntityDomain.ARMY, "TIArmyState", "armies"),
    (EntityDomain.ARMY, "TIMegafaunaArmyState", "armies"),
    (EntityDomain.FLEET, "TISpaceFleetState", "fleets"),
    (EntityDomain.SHIP, "TISpaceShipState", "ships"),
    (EntityDomain.SPACE_OBJECT, "TIHabState", "habs"),
)
"""(domain, short state type, ``SaveSnapshot`` attribute) for each normalized collection.

Several state types may feed one attribute (both army types fill ``armies``).
"""

SERIALIZATION_FIELDS = ("$type", "ID", "finderSortOverride", "gameStateSubjectCreated")
"""Serializer members observed on every entity and singleton ``Value`` object; known, never normalized."""


@dataclass(frozen=True)
class RecordField:
    """How one save-carried record field is decoded (``parsing.records``).

    ``targets`` are the expected domains of the references a pair map is keyed by or a reference list holds.
    Kinds with fixed members (``destruction_log``, ``executive_change``) resolve each member against
    ``RECORD_MEMBER_TARGETS`` instead.
    """

    kind: RecordKind
    targets: ExpectedDomains | None = None


_FACTION_COUNTER = RecordField(RecordKind.COUNTER)
_FACTION_KEYED = RecordField(RecordKind.REFERENCE_VALUES, EntityDomain.FACTION)
_ALIEN_SITE = frozenset((EntityDomain.REGION, EntityDomain.SPACE_OBJECT, EntityDomain.SHIP))
"""A ``knownAlienSites`` key: observed to point at a region, a hab or (once) a ship."""

RECORD_FIELDS: dict[str, dict[str, RecordField]] = {
    "TIFactionState": {
        "HabDestructionLog": RecordField(RecordKind.DESTRUCTION_LOG),
        "Kills": _FACTION_KEYED,
        "Transactions": RecordField(RecordKind.LEDGER),
        "abductions": _FACTION_COUNTER,
        "alienInvestigations": _FACTION_COUNTER,
        "aliensRemoved": _FACTION_COUNTER,
        "armiesLost": RecordField(RecordKind.LABEL_VALUES),
        "atrocities": _FACTION_COUNTER,
        "boostAccounts": RecordField(RecordKind.DATED_LABELS),
        "factionAssassinations": _FACTION_KEYED,
        "factionHate": _FACTION_KEYED,
        "intelSharingFactions": RecordField(RecordKind.REFERENCE_LIST, EntityDomain.FACTION),
        "knownAlienSites": RecordField(RecordKind.DATED_REFERENCES, _ALIEN_SITE),
        "lostControlPoints": RecordField(RecordKind.DATED_REFERENCES, EntityDomain.CONTROL_POINT),
        "milestones": RecordField(RecordKind.NAME_LOG),
        "numAtrocitiesByCause": RecordField(RecordKind.LABEL_VALUES),
        "objectiveNames": RecordField(RecordKind.LABEL_VALUES),
    },
    "TINationState": {
        "dateOfNewGovernment": RecordField(RecordKind.DATE),
        "lastExecutiveChange": RecordField(RecordKind.EXECUTIVE_CHANGE),
    },
}
"""Save-carried record fields per state type: dated logs and cumulative counters not derivable from the snapshot.

Observed in private saves (``domain-field-map.md``, "Save-carried records"); decoded by ``parsing.records`` into
``SaveSnapshot.records`` rather than copied into the entity state.
"""

RECORD_MEMBER_TARGETS: dict[str, ExpectedDomains] = {
    "HabDestructionLog.SpaceBody": EntityDomain.SPACE_OBJECT,
    "HabDestructionLog.Destroyer": EntityDomain.FACTION,
    "lastExecutiveChange.newExecutive": EntityDomain.FACTION,
}
"""Reference members inside record entries, as ``Field.member``, with their observed target domain."""


def record_reference_domains(state_type: str, field: str) -> frozenset[EntityDomain] | None:
    """Expected domains of the references in a record field (``Field`` or ``Field.member``); ``None`` if not one."""
    spec = RECORD_FIELDS.get(state_type, {}).get(field)
    if spec is not None and spec.targets is not None:
        return as_domains(spec.targets)
    member_target = RECORD_MEMBER_TARGETS.get(field)
    if member_target is not None and field.split(".", 1)[0] in RECORD_FIELDS.get(state_type, {}):
        return as_domains(member_target)
    return None


class UnsupportedReason(StrEnum):
    """Why an observed field is deliberately not normalized (the classification issue #8 asks for)."""

    VECTOR = "vector"
    """Spatial or physics values: ``{x, y, z}`` and ``{w, x, y, z}`` vectors, orbital elements, epochs."""
    REFERENCE_GRAPH = "reference_graph"
    """JSON.NET ``$id``/``$ref`` object graphs that the normalizer does not reconstruct."""
    DERIVED_HISTORY = "derived_history"
    """Rolling windows and running histories the game derives from state the snapshot already carries."""
    DERIVED_CACHE = "derived_cache"
    """Values recomputable from other fields of the same snapshot (``*_dailyCache``, counts, sums, pools)."""
    STALE_REFERENCES = "stale_references"
    """Reference lists observed to point mostly at IDs absent from the save."""
    AI_INTERNAL = "ai_internal"
    """AI planning scratch data."""
    UI_CACHE = "ui_cache"
    """Presentation assets, display strings, and player preferences and order settings."""
    RUNTIME_INTERNAL = "runtime_internal"
    """Engine plumbing: event-bus names, dirty flags, combat-simulation and physics scratch, timers, setup flags."""


def _reasons(*groups: tuple[UnsupportedReason, tuple[str, ...]]) -> dict[str, UnsupportedReason]:
    return {name: reason for reason, names in groups for name in names}


_ARMY_ACKNOWLEDGED = _reasons(
    (UnsupportedReason.DERIVED_CACHE, ("controlPointIdx",)),
    (UnsupportedReason.AI_INTERNAL, ("AI_targetEnemyRegion",)),
    (UnsupportedReason.UI_CACHE, ("displayNameWithArticle",)),
    (
        UnsupportedReason.RUNTIME_INTERNAL,
        (
            "armyDamageEventName",
            "armyOperationCompleteEventName",
            "armyStatusUpdateEventName",
            "createdFromTemplate",
        ),
    ),
)
"""Acknowledged fields shared by both army state types."""

ACKNOWLEDGED_FIELDS: dict[str, dict[str, UnsupportedReason]] = {
    "TIFactionState": _reasons(
        (
            UnsupportedReason.DERIVED_HISTORY,
            (
                "highestIntel",
                "history_CPCapOverageByDay",
                "history_MCCapOverageByDay",
                "LocalTransferDVLog",
                "SolarTransferDVLog",
            ),
        ),
        (
            UnsupportedReason.DERIVED_CACHE,
            (
                "activeProjectTriggers",
                "availableCouncilors",
                "availableOrgs",
                "availableProjectNames",
                "baseIncomes_year",
                "cachedSTOFighterMinimumBoost",
                "cachedYearlyRevenue",
                "councilorsGenerated",
                "factionFleetsEncountered",
                "fleetWetMassDuringHighestShipMaintainence",
                "globalResearchPurse",
                "habProjectSlotUnlocked",
                "hiddenProjects",
                "highestRecordedExpenditurePerDay",
                "lastMonthsSpoils",
                "lastWeeksSpoils",
                "missionControlUsage",
                "nextRefitNumber",
                "obsoletedShipParts",
                "obsoleteShipDesigns",
                "orgProjectSlotUnlocked",
                "PassiveTechSlot",
                "savedHabDesigns",
                "shipDesignCount",
                "shipRefitDesignNames",
                "shipRefitDesigns",
                "techRaceSlot",
                "thisMonthsCumulativeSpoils",
                "thisWeeksCumulativeSpoils",
                "turnedCouncilors",
            ),
        ),
        (
            UnsupportedReason.AI_INTERNAL,
            (
                "AIReviewProjects",
                "AISavingTarget",
                "aiValues",
                "alienProxyNeedsHelp",
                "assessedAlienHateOfMe",
                "crazyIvan",
                "currentRiskAversion",
                "desiredShipClass",
                "desiredStaticFleetFraction",
                "factionEarlyToDoList",
                "factionLateToDoList",
                "favoredProjects",
                "focusGoal",
                "habDesigns",
                "highestSpaceStrengthSinceLastAlienKnockdown",
                "ignoreContacts",
                "ignoreInterstateDiplomacy",
                "initialAINationGoals",
                "internalCouncilorSuspicion",
                "lastRecordedLoyalty",
                "lastTechRaceDate",
                "lastUnaffordableShipShipyard",
                "longtermTechTarget",
                "majorCPTrouble",
                "minorCPTrouble",
                "missedProjects",
                "mostPowerfulHumanEnemy",
                "perceivedEnemyFleetStrengthFactors",
                "permaAbandonedNations",
                "plannedPolicies",
                "primaryHab",
                "resourceIncomeDeficiencies",
                "selfAssessement",
                "thisTurnsReveralScore",
                "updateHabPlanningFlag",
                "updateShipDesignsFlag",
            ),
        ),
        (
            UnsupportedReason.UI_CACHE,
            (
                "alarms",
                "alertSpaceTimerNotifications",
                "checkNotificationOverrides",
                "customPresets",
                "defaultFleetArrivalAlert",
                "defaultFleetArrivalAlert_Earth",
                "defaultFleetArrivalAlienModifier",
                "defaultFleetArrivalAlienModifier_Earth",
                "defaultHullAppearanceIndex",
                "defaultPriorityPresetTemplateName",
                "lastDateOfFixedAlienHate",
                "lastTimeSecretsWereSeen",
                "mapColorationStyle",
                "newAvailableCouncilors",
                "newAvailableOrgs",
                "notificationOverrides",
                "showAlerts",
                "showMonthlyIncomesInTopBarAndIntel",
                "showObsoleteParts",
                "showRegularNotifications",
                "showSummaryLogs",
                "showTimerNotifications",
            ),
        ),
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "AlienControlPointGiftHistory",
                "CombatLogs",
                "dailyResourceTransfers",
                "factionOperationCompleteName",
                "LastObjectiveProjectCompletionDate",
                "nShipyardQueues",
                "specialRegionAdjacencies",
            ),
        ),
    ),
    "TINationState": _reasons(
        (
            UnsupportedReason.DERIVED_HISTORY,
            (
                "historyBoost",
                "historyCohesion",
                "historyCohesionRestState",
                "historyDemocracy",
                "historyEducation",
                "historyGDP",
                "historyInequality",
                "historyInvestmentPoints",
                "historyMiltech",
                "historyMissionControl",
                "historyNukes",
                "historyNumRegions",
                "historyPopulation",
                "historyPublicOpinion",
                "historyResearch",
                "historySpaceFunding",
                "historySustainability",
                "historyUnrest",
                "historyUnrestRestState",
                "historyWarStatus",
                "tracker_Cohesion_ByQuarter",
                "tracker_CohesionChangeReason_CurrentTrackingPeriod",
                "tracker_CohesionChangeReason_PriorTrackingPeriod",
                "tracker_Democracy_ByQuarter",
                "tracker_DemocracyChangeReason_CurrentTrackingPeriod",
                "tracker_DemocracyChangeReason_PriorTrackingPeriod",
                "tracker_Education_ByQuarter",
                "tracker_EducationChangeReason_CurrentTrackingPeriod",
                "tracker_EducationChangeReason_PriorTrackingPeriod",
                "tracker_GDP_ByQuarter",
                "tracker_GDPChangeReason_CurrentTrackingPeriod",
                "tracker_GDPChangeReason_PriorTrackingPeriod",
                "tracker_Inequality_ByQuarter",
                "tracker_InequalityChangeReason_CurrentTrackingPeriod",
                "tracker_InequalityChangeReason_PriorTrackingPeriod",
                "tracker_Unrest_ByQuarter",
                "tracker_UnrestChangeReason_CurrentTrackingPeriod",
                "tracker_UnrestChangeReason_PriorTrackingPeriod",
            ),
        ),
        (
            UnsupportedReason.DERIVED_CACHE,
            (
                "_accumulatedInvestmentPoints",
                "baseInvestmentPoints_month",
                "cohesionRestState_dailyCache",
                "directInvestmentedIPsThisYear",
                "economyScore",
                "maxMilitaryTechLevel",
                "missionDifficultyEconomyScore",
                "numControlPoints_unclamped",
                "numCoreEconomicRegions_dailyCache",
                "numMiningRegions_dailyCache",
                "numOilRegions_dailyCache",
                "priorityEffectPopScaling",
                "restofFederationECOBonus_dailyCache",
                "StartOfTurnNativeControlPoints",
                "unrestRestState_dailyCache",
            ),
        ),
        (UnsupportedReason.UI_CACHE, ("adjacentNations",)),
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "accumulatedLegitimizeClaimTriggers",
                "canAccumulateCoreEconomyTriggers",
                "canAccumulateCoreMiningTriggers",
                "canAccumulateCoreOilTriggers",
                "canAccumulateDecolonizeTriggers",
                "canAccumulateDecontaminateTriggers",
                "canAccumulateLegitimizeClaimTriggers",
                "canBuildSpaceDefenses",
                "canBuildSTOSquadrons",
                "canDecontaminate",
                "improveRelationsCooldowns",
                "improveRelationsDeclinedUnderCurrentExecutivePair",
                "oldRivalsCount",
                "rivalryCooldowns",
            ),
        ),
    ),
    "TIControlPoint": _reasons(
        (UnsupportedReason.DERIVED_CACHE, ("numPrioritiesWithWeight", "totalWeightsForControlPoint")),
    ),
    "TIRegionState": _reasons(
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "accumulatedCoreEconomyRegionTriggers",
                "accumulatedCoreMiningRegionTriggers",
                "accumulatedCoreOilRegionTriggers",
                "accumulatedDecolonizeTriggers",
                "accumulatedDecontaminateTriggers",
                "annualPopGrowthModifier",
                "STOFighterCooldownExpiry",
            ),
        ),
    ),
    "TICouncilorState": _reasons(
        (UnsupportedReason.AI_INTERNAL, ("autofailMissionsValue",)),
        (
            UnsupportedReason.UI_CACHE,
            (
                "appearanceTemplateName",
                "everBeenAvailable",
                "familyName",
                "learnedMissionsTemplateNames",
                "locationIllustration",
                "missionsExcludedFromDefenseMode",
                "permanentAssignment",
                "permanentDefenseMode",
                "personalName",
                "repeatOrder",
                "voiceTemplateName",
            ),
        ),
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "imBeingTargeted",
                "possibleFaction",
                "preMissionPhaseLocation",
                "priorMissionTarget",
                "targetedLastTurn",
            ),
        ),
    ),
    "TIArmyState": _ARMY_ACKNOWLEDGED,
    "TIMegafaunaArmyState": _ARMY_ACKNOWLEDGED,
    "TISpaceFleetState": _reasons(
        (
            UnsupportedReason.VECTOR,
            (
                "_epoch_JYears",
                "_fleetTrajectoryData",
                "_meanAnomalyAtEpoch_Rad",
                "_rnd_rotationOffset_Deg",
                "bombardmentAltitude_km",
                "dockOffset",
                "epoch_DateTime",
                "firstHitFromBombardmentRun",
            ),
        ),
        (UnsupportedReason.DERIVED_HISTORY, ("Logs",)),
        (UnsupportedReason.STALE_REFERENCES, ("unreachableLocations",)),
        (UnsupportedReason.AI_INTERNAL, ("AI_FailedAttackEnemyStrength",)),
        (UnsupportedReason.UI_CACHE, ("alwaysShowOrbitTrailDuringTransfer", "formation", "savedFormation")),
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "campaignStartLocation",
                "delayedTransferAbortNotification",
                "dummyFleet",
                "fleetOperationCompleteName",
                "officerTransferPlan",
                "propellantSharingPlan",
                "proposedTrajectories",
                "returnToOperationsTime",
                "waitingToInitiateCombatDatas",
            ),
        ),
    ),
    "TISpaceShipState": _reasons(
        (UnsupportedReason.VECTOR, ("currentFleetOffset", "currentRotation", "damagePoints", "fleetFormationOffset")),
        (UnsupportedReason.REFERENCE_GRAPH, ("ammo", "batteryCharge", "hullWeapons", "noseWeapons", "utilityModules")),
        (UnsupportedReason.DERIVED_CACHE, ("missionControlConsumption",)),
        (UnsupportedReason.UI_CACHE, ("homeRegion",)),
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "accumulatedHeat_GJ",
                "activeCombatManeuvers",
                "angular_acceleration_rads2",
                "availablePower_GJ",
                "canSuicide",
                "combatAIControl",
                "combatManeuverTarget",
                "combatPrimaryTarget",
                "combatSecondCounter",
                "currentHeatSinkCapacity_GJ",
                "currentManeuver",
                "disengageFromCombat",
                "generatorWorking",
                "hasDisengaged",
                "isDummy",
                "max_angular_velocity_rad_s",
                "plannedResupplyAndRepair",
                "prevPartsBeingRepaired",
                "prevSystemsBeingRepaired",
                "propulsionValuesDataDirty",
                "radiatorsExtended",
                "radiatorsExtending",
                "radiatorsRetracting",
                "spaceCombatValueDataDirty",
                "systemsDepowered",
                "thrustersActive",
            ),
        ),
    ),
    "TIHabState": _reasons(
        (
            UnsupportedReason.VECTOR,
            (
                "_epoch_JYears",
                "_meanAnomalyAtEpoch_Rad",
                "_rnd_rotationOffset_Deg",
                "epoch_DateTime",
            ),
        ),
        (UnsupportedReason.DERIVED_CACHE, ("FarmProvidedResources",)),
        (UnsupportedReason.STALE_REFERENCES, ("conflictFleets",)),
        (UnsupportedReason.AI_INTERNAL, ("habSchematic", "HabSchematicAssignedDate", "habSchematicTemplateName")),
        (UnsupportedReason.UI_CACHE, ("connStruct", "customHabIconResource", "ringStruct")),
        (UnsupportedReason.RUNTIME_INTERNAL, ("_dockedShipAbovePositions", "createdFromTemplate")),
    ),
    "TIMetadataState": _reasons(
        (
            UnsupportedReason.UI_CACHE,
            (
                "lastCompletedObjectiveArtPath",
                "lastCompletedObjectiveName",
                "playerFactionGradientPath",
                "playerFactionIconPath",
            ),
        ),
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "alienProgressionSpeed",
                "averageMonthlyEvents",
                "controlPointMaintenanceFreebieBonus",
                "controlPointMaintenanceFreebieBonusAI",
                "customDifficulty",
                "miningProductivityMultiplier",
                "missionControlBonus",
                "missionControlBonusAI",
                "nationalIPMultiplier",
                "requiredDLC",
                "researchSpeedMultiplier",
            ),
        ),
    ),
    "TIGlobalResearchState": _reasons(
        (UnsupportedReason.RUNTIME_INTERNAL, ("useHarshTree",)),
    ),
}
"""Observed fields that are known and deliberately not copied, with the reason (``domain-field-map.md``).

Only names observed in real saves belong here, each listed explicitly; a field that is neither normalized nor
acknowledged is reported as unknown and recorded in ``docs/game-data-notes/unknowns/registry.json``.
"""


def _known(state_type: str, copied: tuple[str, ...]) -> frozenset[str]:
    return (
        frozenset(copied)
        | frozenset(SERIALIZATION_FIELDS)
        | frozenset(RECORD_FIELDS.get(state_type, {}))
        | frozenset(ACKNOWLEDGED_FIELDS.get(state_type, {}))
    )


KNOWN_FIELDS: dict[str, frozenset[str]] = {
    **{state_type: _known(state_type, names) for state_type, names in ENTITY_FIELDS.items()},
    **{state_type: _known(state_type, COMMON_FIELDS + names) for state_type, names in SINGLETON_FIELDS.items()},
}
"""Every field name the parser describes per scanned state type: copied, record, serializer, or acknowledged."""
