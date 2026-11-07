"""Observed field names per normalized state type: the code form of ``docs/game-data-notes/domain-field-map.md``.

A member is copied (``ENTITY_FIELDS``), decoded as a record (``RECORD_FIELDS``) or known and deliberately not
normalized (``ACKNOWLEDGED_FIELDS``); anything else is reported as unknown.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..model.entities import EntityDomain
from ..model.records import RecordKind
from .references import ExpectedDomains, as_domains

COMMON_FIELDS = ("templateName", "displayName", "archived", "exists")

REGION_ALIEN_STATE_TYPES = (
    "TIRegionUFOCrashdownState",
    "TIRegionUFOLandingState",
    "TIRegionAlienFacilityState",
    "TIRegionXenoformingState",
    "TIRegionAlienActivityState",
)
"""The per-region alien sub-states: one entry per region each, with a ``region`` back-reference."""

GLOBAL_VALUES_STATE_TYPE = "TIGlobalValuesState"
"""Normalized as a one-entity collection (``SaveSnapshot.global_values``)."""

NOTIFICATION_QUEUE_STATE_TYPE = "TINotificationQueueState"
"""Normalized as a one-entity collection that owns the notification log record."""
NOTIFICATION_LOG = "notificationSummaryQueue"
COMBAT_LOG = "CombatLogs"

_ARMY_FIELDS = COMMON_FIELDS + (
    "currentRegion",
    "faction",
    "homeRegion",
    "strength",
    "destroyed",
    "armyType",
    "deploymentType",
)

ENTITY_FIELDS: dict[str, tuple[str, ...]] = {
    "TIFactionState": COMMON_FIELDS
    + (
        "player",
        "councilors",
        "fleets",
        "controlPoints",
        "armies",
        "finishedProjectNames",
        "unassignedOrgs",
        "shipDesigns",
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
        "controlPointType",
        "positionInNation",
    ),
    "TIRegionState": COMMON_FIELDS
    + (
        "nation",
        "leadOccupier",
        "occupations",
        "populationInMillions",
        "xenoforming",
        "missionControlFacility",
        "isBeingAnnexed",
        "annexingArmy",
        "armies",
        "antiSpaceDefenses",
        "boostPerYear_dekatons",
        "missionControl",
        "numSTOFighters",
        "nuclearDetonations",
        "underBombardment",
        "coreEconomicRegion",
        "oilRegion",
        "resourceRegion",
    ),
    "TICouncilorState": COMMON_FIELDS
    + (
        "faction",
        "location",
        "homeRegion",
        "detainingFaction",
        "recruitDate",
        "attributes",
        "orgs",
        "status",
        "XP",
        "typeTemplateName",
        "traitTemplateNames",
        "gender",
        "dateBorn",
    ),
    "TIMissionState": COMMON_FIELDS + ("councilor", "target"),
    "TIArmyState": _ARMY_FIELDS,
    "TIMegafaunaArmyState": _ARMY_FIELDS,
    "TISpaceFleetState": COMMON_FIELDS
    + (
        "ships",
        "barycenter",
        "parentFleet",
        "faction",
        "orbitState",
        "dockedLocation",
        "inCombat",
    ),
    "TISpaceShipState": COMMON_FIELDS
    + (
        "fleet",
        "lastRefitDate",
        "kills",
    ),
    "TIWarState": COMMON_FIELDS
    + (
        "attacker",
        "defender",
        "_attackingAlliance",
        "_defendingAlliance",
    ),
    "TIFederationState": COMMON_FIELDS + ("members", "federationName"),
    "TIOrgState": COMMON_FIELDS
    + (
        "assignedCouncilor",
        "factionOrbit",
        "homeRegion",
        "tier",
        "incomeMoney_month",
        "incomeInfluence_month",
        "incomeOps_month",
        "incomeResearch_month",
        "MCBonus",
        "investigation",
        "espionage",
        "command",
        "administration",
        "science",
        "security",
        "economyBonus",
        "welfareBonus",
        "governmentBonus",
        "unityBonus",
        "oppressionBonus",
        "spoilsBonus",
        "environmentBonus",
        "miningBonus",
        "spaceDevBonus",
        "spaceflightBonus",
    ),
    "TIRegionUFOCrashdownState": COMMON_FIELDS + ("region", "crashdownPresent"),
    "TIRegionUFOLandingState": COMMON_FIELDS + ("region", "landingPresent"),
    "TIRegionAlienFacilityState": COMMON_FIELDS + ("region", "built"),
    "TIRegionXenoformingState": COMMON_FIELDS + ("region", "xenoformingLevel"),
    "TIRegionAlienActivityState": COMMON_FIELDS + ("region",),
    "TISpaceBodyState": COMMON_FIELDS + ("barycenter",),
    "TIMissionControlFacilityState": COMMON_FIELDS + ("region", "spaceFacilityType"),
    "TIHabState": COMMON_FIELDS
    + (
        "faction",
        "orbitState",
        "barycenter",
        "dockedFleets",
        "habType",
        "tier",
        "inCombat",
        "underAssault",
        "underBombardment",
        "anyCoreCompleted",
    ),
    GLOBAL_VALUES_STATE_TYPE: COMMON_FIELDS
    + (
        "interstateWars",
        "nuclearStrikes",
        "looseNukes",
        "currentNuclearExchanges",
        "earthAtmosphericCO2_ppm",
        "earthAtmosphericCH4_ppm",
        "earthAtmosphericN2O_ppm",
        "stratosphericAerosols_ppm",
        "globalSeaLevelAnomaly_cm",
        "globalSeaLevelRise1Triggered",
        "globalSeaLevelRise2Triggered",
    ),
    # Every member other than templateName/displayName/archived/exists is a record or acknowledged.
    NOTIFICATION_QUEUE_STATE_TYPE: COMMON_FIELDS,
}
"""Fields copied into each ``EntityState``."""


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

METADATA_FIELDS = (
    "playerFactionName",
    "difficulty",
    "playedWithMods",
    "gameTimeString",
    "selectedFactionsForScenario",
)

SINGLETON_FIELDS: dict[str, tuple[str, ...]] = {
    "TITimeState": TIME_FIELDS,
    "TIMetadataState": METADATA_FIELDS,
    RESEARCH_STATE_TYPE: RESEARCH_FIELDS,
}

_ARMY_LIST = (EntityDomain.ARMY, True)
_FACTION = (EntityDomain.FACTION, False)
_REGION = (EntityDomain.REGION, False)
_COUNCILOR = (EntityDomain.COUNCILOR, False)
_NATION = (EntityDomain.NATION, False)
_MISSION = (EntityDomain.MISSION, False)
_NATION_LIST = (EntityDomain.NATION, True)
_SPACE_OBJECT = (EntityDomain.SPACE_OBJECT, False)
_SPACE_BODY = (EntityDomain.SPACE_BODY, False)
_ALIEN_STATE = (EntityDomain.REGION_ALIEN_STATE, False)
_PLACE = (frozenset((EntityDomain.REGION, EntityDomain.SPACE_OBJECT, EntityDomain.SHIP)), False)
"""A councilor location: a ``TIRegionState``, a ``TIHabState`` or a ``TISpaceShipState``."""

_MISSION_TARGET = (
    frozenset(
        (
            EntityDomain.NATION,
            EntityDomain.COUNCILOR,
            EntityDomain.REGION,
            EntityDomain.CONTROL_POINT,
            EntityDomain.ORGANIZATION,
            EntityDomain.SPACE_OBJECT,
            EntityDomain.SHIP,
            EntityDomain.REGION_ALIEN_STATE,
            EntityDomain.MISSION_CONTROL_FACILITY,
        )
    ),
    False,
)
"""A mission target: any of the entity kinds a mission can be aimed at."""

_ARMY_REFERENCES: dict[str, tuple[ExpectedDomains, bool]] = {
    "currentRegion": _REGION,
    "homeRegion": _REGION,
    "faction": _FACTION,
}

REFERENCE_FIELDS: dict[str, dict[str, tuple[ExpectedDomains, bool]]] = {
    "TIMissionState": {"councilor": _COUNCILOR, "target": _MISSION_TARGET},
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
        "federation": (EntityDomain.FEDERATION, False),
    },
    "TIControlPoint": {
        "nation": (EntityDomain.NATION, False),
        "faction": (EntityDomain.FACTION, False),
    },
    "TIRegionState": {
        "nation": (EntityDomain.NATION, False),
        "leadOccupier": (EntityDomain.NATION, False),
        "armies": _ARMY_LIST,
        "xenoforming": _ALIEN_STATE,
        "missionControlFacility": (EntityDomain.MISSION_CONTROL_FACILITY, False),
    },
    "TICouncilorState": {
        "faction": _FACTION,
        "detainingFaction": _FACTION,
        "homeRegion": _REGION,
        "location": _PLACE,
        "orgs": (EntityDomain.ORGANIZATION, True),
    },
    "TIArmyState": _ARMY_REFERENCES,
    "TIMegafaunaArmyState": _ARMY_REFERENCES,
    "TIWarState": {
        "attacker": _NATION,
        "defender": _NATION,
        "_attackingAlliance": _NATION_LIST,
        "_defendingAlliance": _NATION_LIST,
    },
    "TIFederationState": {
        "members": _NATION_LIST,
    },
    GLOBAL_VALUES_STATE_TYPE: {
        "interstateWars": (EntityDomain.WAR, True),
    },
    "TIOrgState": {
        "assignedCouncilor": _COUNCILOR,
        "factionOrbit": _FACTION,
        "homeRegion": _REGION,
    },
    **{state_type: {"region": _REGION} for state_type in REGION_ALIEN_STATE_TYPES},
    "TIMissionControlFacilityState": {"region": _REGION},
    "TISpaceFleetState": {
        "ships": (EntityDomain.SHIP, True),
        "parentFleet": (EntityDomain.FLEET, False),
        "faction": _FACTION,
        "orbitState": _SPACE_OBJECT,
        "barycenter": _SPACE_BODY,
        "dockedLocation": _SPACE_OBJECT,
    },
    "TISpaceShipState": {
        "fleet": (EntityDomain.FLEET, False),
    },
    "TISpaceBodyState": {"barycenter": _SPACE_BODY},
    "TIHabState": {
        "faction": _FACTION,
        "orbitState": _SPACE_OBJECT,
        "barycenter": _SPACE_BODY,
        "dockedFleets": (EntityDomain.FLEET, True),
    },
}
"""Reference fields and their observed target domain(s); ``True`` marks a list of references.

Reference-shaped fields whose target has no ``EntityDomain`` or was never observed non-null stay raw, as do a
fleet's ``bombardmentTarget`` and ``currentOperations`` (operation dates can be ``$ref`` graph nodes).
"""

KEYED_LIST_FIELDS: dict[str, dict[str, str]] = {
    "TIFactionState": {"shipDesigns": "dataName"},
}
"""List-of-object fields copied as a ``FrozenMap`` keyed by the named (unique) string member.

Keying lets the diff compare elements one by one instead of the whole list as one value.
"""

DATE_FIELDS: dict[str, tuple[str, ...]] = {
    "TICouncilorState": ("recruitDate", "dateBorn"),
}
"""Entity fields holding a componentized date; the snapshot carries ISO-8601 text (see ``parsing/dates.py``)."""

HAB_CORE_FIELDS = (
    "coreConstructionCompleted",
    "coreStartBuildDate",
    "coreCompletionDate",
    "corePriorCompletionDate",
)
"""Copied from the hab's core module, the ``TIHabModuleState`` in slot 0 of its first sector (``parsing/cores.py``).

``coreStartBuildDate`` and ``coreCompletionDate`` are projected until the core is built; ``corePriorCompletionDate``
is the completion of the core an upgrade replaced. Dates are ISO-8601 text or ``None``.
"""

DERIVED_FIELDS: dict[str, tuple[str, ...]] = {"TIHabState": HAB_CORE_FIELDS}
"""Entity fields joined from other state types; appended after ``ENTITY_FIELDS``, never raw ``Value`` members."""

PAIR_MAP_FIELDS: dict[str, dict[str, ExpectedDomains | None]] = {
    "TINationState": {"factionUnrestAttempts": EntityDomain.FACTION, "tracker_PCGDP_ByQuarter": None},
    "TIRegionState": {"occupations": EntityDomain.NATION},
}
"""Entity fields serialized as a field-level pair map, with the keys' target domain(s); ``None`` marks integer
keys, which are not references.

Each is also in ``ENTITY_FIELDS`` and is copied as a ``FrozenMap`` keyed by ``EntityId`` text (or the integer's
decimal text), so the diff compares it key by key.
"""

NORMALIZED_DOMAINS: tuple[tuple[EntityDomain, str, str], ...] = (
    (EntityDomain.FACTION, "TIFactionState", "factions"),
    (EntityDomain.NATION, "TINationState", "nations"),
    (EntityDomain.REGION, "TIRegionState", "regions"),
    (
        EntityDomain.MISSION_CONTROL_FACILITY,
        "TIMissionControlFacilityState",
        "mission_control_facilities",
    ),
    (EntityDomain.CONTROL_POINT, "TIControlPoint", "control_points"),
    (EntityDomain.COUNCILOR, "TICouncilorState", "councilors"),
    (EntityDomain.MISSION, "TIMissionState", "missions"),
    (EntityDomain.ARMY, "TIArmyState", "armies"),
    (EntityDomain.ARMY, "TIMegafaunaArmyState", "armies"),
    (EntityDomain.FLEET, "TISpaceFleetState", "fleets"),
    (EntityDomain.SHIP, "TISpaceShipState", "ships"),
    (EntityDomain.SPACE_OBJECT, "TIHabState", "habs"),
    (EntityDomain.SPACE_BODY, "TISpaceBodyState", "space_bodies"),
    (EntityDomain.WAR, "TIWarState", "wars"),
    (EntityDomain.FEDERATION, "TIFederationState", "federations"),
    (EntityDomain.ORGANIZATION, "TIOrgState", "organizations"),
    *((EntityDomain.REGION_ALIEN_STATE, state_type, "region_alien_states") for state_type in REGION_ALIEN_STATE_TYPES),
    (EntityDomain.GLOBAL_VALUES, GLOBAL_VALUES_STATE_TYPE, "global_values"),
    (EntityDomain.NOTIFICATION_QUEUE, NOTIFICATION_QUEUE_STATE_TYPE, "notification_queue"),
)
"""(domain, short state type, ``SaveSnapshot`` attribute) for each normalized collection.

Several state types may feed one attribute.
"""

SINGLETON_ENTITY_TYPES = frozenset((GLOBAL_VALUES_STATE_TYPE, NOTIFICATION_QUEUE_STATE_TYPE))
"""Normalized state types expected to have one entry; more than one is reported."""

SERIALIZATION_FIELDS = ("$type", "ID", "finderSortOverride", "gameStateSubjectCreated")
"""Serializer members on every ``Value`` object; known, never normalized."""


@dataclass(frozen=True)
class RecordField:
    """How one save-carried record field is decoded.

    ``targets`` are the expected domains of the field's references; kinds with fixed members resolve each member
    against ``RECORD_MEMBER_TARGETS`` instead.
    """

    kind: RecordKind
    targets: ExpectedDomains | None = None


_FACTION_KEYED = RecordField(RecordKind.REFERENCE_VALUES, EntityDomain.FACTION)

RECORD_FIELDS: dict[str, dict[str, RecordField]] = {
    "TIFactionState": {
        COMBAT_LOG: RecordField(RecordKind.COMBAT_LOG),
        "HabDestructionLog": RecordField(RecordKind.DESTRUCTION_LOG),
        "Kills": _FACTION_KEYED,
        "Transactions": RecordField(RecordKind.LEDGER),
        "lostControlPoints": RecordField(RecordKind.DATED_REFERENCES, EntityDomain.CONTROL_POINT),
        "milestones": RecordField(RecordKind.NAME_LOG),
    },
    "TINationState": {
        "dateOfNewGovernment": RecordField(RecordKind.DATE),
        "lastExecutiveChange": RecordField(RecordKind.EXECUTIVE_CHANGE),
    },
    "TIWarState": {
        "startDate": RecordField(RecordKind.DATE),
        "dateOfLastFighting": RecordField(RecordKind.DATE),
    },
    "TIRegionUFOCrashdownState": {
        "crashdownTime": RecordField(RecordKind.DATE),
    },
    GLOBAL_VALUES_STATE_TYPE: {
        "globalMilestones": RecordField(RecordKind.LABELLED_REFERENCES, EntityDomain.FACTION),
        "triggeredOncePerCampaignEvents": RecordField(RecordKind.NAME_LOG),
        "triggeredOncePerTargetEvents": RecordField(RecordKind.LABELLED_REFERENCES, EntityDomain.FACTION),
    },
    NOTIFICATION_QUEUE_STATE_TYPE: {
        NOTIFICATION_LOG: RecordField(RecordKind.NOTIFICATION_LOG),
    },
}
"""Dated logs and cumulative counters not derivable from the snapshot (``domain-field-map.md``, "Save-carried
records"); decoded into ``SaveSnapshot.records`` rather than the entity state."""

RECORD_MEMBER_TARGETS: dict[str, ExpectedDomains] = {
    "HabDestructionLog.SpaceBody": EntityDomain.SPACE_BODY,
    "HabDestructionLog.Destroyer": EntityDomain.FACTION,
    "lastExecutiveChange.newExecutive": EntityDomain.FACTION,
    f"{NOTIFICATION_LOG}.gotoGameState": frozenset(
        domain for domain in EntityDomain if domain is not EntityDomain.TECHNOLOGY
    ),
    f"{NOTIFICATION_LOG}.newsFeedFactions": EntityDomain.FACTION,
    f"{NOTIFICATION_LOG}.summaryLogFactions": EntityDomain.FACTION,
    f"{COMBAT_LOG}.Ships": EntityDomain.FACTION,
    f"{COMBAT_LOG}.HabFaction": EntityDomain.FACTION,
    f"{COMBAT_LOG}.winner": EntityDomain.FACTION,
}
"""Reference members inside record entries, as ``Field.member``, with their target domain.

A notification's ``gotoGameState`` can point at almost any domain, so it resolves against all of them.
"""

UNTRACKED_REFERENCE_TARGETS: dict[str, frozenset[str]] = {
    f"{NOTIFICATION_LOG}.gotoGameState": frozenset(("TIGlobalResearchState", "TIMissionPhaseState")),
}
"""Known target state types of a record reference member that have no in-save-ID domain.

Such a reference stays unresolved but is not reported as an unexpected reference domain.
"""

NOTIFICATION_ENTRY_MEMBERS = (
    "templateName",
    "dateTime",
    "itemSummary",
    "outcome",
    "gotoGameState",
    "alienRelated",
    "newsFeedFactions",
    "summaryLogFactions",
)

NOTIFICATION_ACKNOWLEDGED_MEMBERS = (
    "$id",  # JSON.NET object ID, the target of panelSummaryQueue $ref pointers
    "dateTimeString",  # display text of dateTime
    "timerFactions",  # not modelled
    "iconResource",  # presentation
    "iconBackgroundResource",  # presentation
    "backgroundColor",  # presentation
)
"""Members of a notification log entry that are known and deliberately not decoded."""

COMBAT_ENTRY_MEMBERS = ("Date", "Ships", "HabFaction", "Attacks", "winner", "WasSurprising")

RECORD_ENTRY_MEMBERS: dict[str, dict[str, frozenset[str]]] = {
    "TIFactionState": {
        COMBAT_LOG: frozenset(COMBAT_ENTRY_MEMBERS),
    },
    NOTIFICATION_QUEUE_STATE_TYPE: {
        NOTIFICATION_LOG: frozenset(NOTIFICATION_ENTRY_MEMBERS + NOTIFICATION_ACKNOWLEDGED_MEMBERS),
    },
}
"""Known members of open-ended record entries; any other is reported as the unknown field ``Field[].member``."""


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
    """Why an observed field is deliberately not normalized."""

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
            UnsupportedReason.DERIVED_CACHE,
            (
                "resources",
                "currentProjectProgress",
                "researchWeights",
                "intel",
                "shipsBuiltInClass",
                "techNameContributionHistory",
            ),
        ),
        (UnsupportedReason.AI_INTERNAL, ("knownSpies", "factionGoals", "sabotagedProjects")),
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            ("habSectors", "knowsWinCondition", "unlockedVictoryObjective", "defeated"),
        ),
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "abductions",
                "alienInvestigations",
                "aliensRemoved",
                "armiesLost",
                "atrocities",
                "boostAccounts",
                "factionAssassinations",
                "factionHate",
                "intelSharingFactions",
                "knownAlienSites",
                "numAtrocitiesByCause",
                "objectiveNames",
            ),
        ),
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
        (
            UnsupportedReason.DERIVED_CACHE,
            ("benefitsDisabled", "controlPointPriorities", "numPrioritiesWithWeight", "totalWeightsForControlPoint"),
        ),
        (UnsupportedReason.RUNTIME_INTERNAL, ("defended", "crackdownExpiration", "defendExpiration")),
    ),
    "TIRegionState": _reasons(
        (
            UnsupportedReason.DERIVED_CACHE,
            ("adjacencies", "spaceFacilities", "annexationDaysLeft", "permanentlyDecolonized"),
        ),
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "alienFacility",
                "alienActivity",
                "abductions",
                "alienCrashdown",
                "alienLanding",
                "boostFacility",
                "spaceDefenseFacility",
                "originalColony",
                "annexationBeginDate",
                "isCounterfiring",
                "colonyRegion",
                "oceanType",
            ),
        ),
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
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "agentForFaction",
                "priorLocation",
                "detainedReleaseDate",
                "activeMission",
                "completedMission",
                "ancestry",
                "assassinations",
                "knowsIveBeenSeenBy",
                "priorMissionTemplateName",
                "protectingTarget",
            ),
        ),
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
    "TIMissionState": _reasons(
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            ("missionOutcome", "resources", "startTime", "resolveTime", "resolveTimeAssigned"),
        ),
    ),
    "TIArmyState": _reasons(
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "priorRegion",
                "operationTarget",
                "destinationQueue",
                "currentOperations",
                "destinationSeaDate",
                "embarkDate",
                "huntingXenofauna",
            ),
        ),
    )
    | _ARMY_ACKNOWLEDGED,
    "TIMegafaunaArmyState": _reasons(
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "priorRegion",
                "operationTarget",
                "destinationQueue",
                "currentOperations",
                "destinationSeaDate",
                "embarkDate",
                "huntingXenofauna",
                "bonusTechLevel",
            ),
        ),
    )
    | _ARMY_ACKNOWLEDGED,
    "TISpaceFleetState": _reasons(
        (UnsupportedReason.VECTOR, ("trajectory", "globalPosition")),
        (
            UnsupportedReason.DERIVED_CACHE,
            (
                "inAccelerationPhase",
                "inDecelerationPhase",
                "homeport",
                "combatState",
                "displayNameByFaction",
                "currentOperations",
                "huntingXenofauna",
                "unavailableForOperations",
                "bombardmentTargetBracketStatus",
                "endBombardmentReason",
                "timeOfLastFireMission",
            ),
        ),
        (UnsupportedReason.RUNTIME_INTERNAL, ("bombardmentTarget",)),
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
        (
            UnsupportedReason.DERIVED_CACHE,
            (
                "propellant_tons",
                "cruiseAcceleration_mps2",
                "combatAcceleration_mps2",
                "currentDeltaV_kps",
                "currentMaxDeltaV_kps",
                "currentMass_kg",
                "armor",
                "damagedParts",
                "damagedSystems",
            ),
        ),
        (UnsupportedReason.RUNTIME_INTERNAL, ("launchDate", "officers", "storedFaction", "isDamageControlSuspended")),
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
    "TISpaceBodyState": _reasons(
        (UnsupportedReason.VECTOR, ("_rnd_rotationOffset_Deg", "epoch_DateTime", "globalPosition")),
        (
            UnsupportedReason.DERIVED_CACHE,
            ("HohmannDates", "habSites", "maxHabTier", "nations", "orbits", "solarMirrorBonus"),
        ),
        (UnsupportedReason.UI_CACHE, ("currentModelResource", "playerTag")),
    ),
    "TIHabState": _reasons(
        (
            UnsupportedReason.DERIVED_CACHE,
            (
                "sectors",
                "districts",
                "councilorsOnBoard",
                "officersOnBoard",
                "advisingCouncilors",
                "staticHab",
                "inEarthLEO",
                "globalPosition",
            ),
        ),
        (UnsupportedReason.RUNTIME_INTERNAL, ("habSite", "coreDefended", "coreDefendExpiration")),
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
    "TIFederationState": _reasons(
        (UnsupportedReason.UI_CACHE, ("adjective",)),
        (UnsupportedReason.UI_CACHE, ("displayNameWithArticle", "displayNameWithArticleCapitalized", "flagResource")),
        (UnsupportedReason.RUNTIME_INTERNAL, ("lastAttemptToLeaveDarkFederation",)),
    ),
    "TIOrgState": _reasons(
        (
            UnsupportedReason.DERIVED_CACHE,
            (
                "applyingBonuses",
                "takeoverDefense",
                "XPModifier",
                "projectCapacityGranted",
                "costMoney",
                "costInfluence",
                "costOps",
                "costBoost",
                "incomeBoost_month",
                "incomeMissionControl",
                "persuasion",
                "knowledgeBonus",
                "militaryBonus",
            ),
        ),
        (UnsupportedReason.UI_CACHE, ("orgIconPath", "orgIconTemplateName", "displayNameWithArticle")),
    ),
    "TIRegionUFOLandingState": _reasons(
        (UnsupportedReason.RUNTIME_INTERNAL, ("deployingArmy", "supportingArmyBuildup", "currentHP"))
    ),
    "TIRegionAlienFacilityState": _reasons((UnsupportedReason.RUNTIME_INTERNAL, ("currentHP",))),
    "TIRegionAlienActivityState": _reasons((UnsupportedReason.RUNTIME_INTERNAL, ("alienMissionsDetected",))),
    "TIWarState": _reasons(
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "originalAttacker",
                "originalDefender",
                "nukedRegions",
                "annexedRegions",
                "defensiveNukes",
                "peaceOfferHistory",
                "cohesionGainByNation",
            ),
        )
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
    GLOBAL_VALUES_STATE_TYPE: _reasons(
        (
            UnsupportedReason.DERIVED_CACHE,
            ("bestGlobalHumanMiltech", "bestGlobalHumanEducation", "alienInvaderArmies", "endOfOil"),
        ),
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "campaignStartVersion",
                "latestSaveVersion",
                "realWorldCampaignStart",
                "narrativeEventsOnCooldown_months",
                "removedNarrativeEvents",
            ),
        ),
        (
            UnsupportedReason.DERIVED_HISTORY,
            ("pastEarthAtmosphericCH4_ppm", "pastEarthAtmosphericCO2_ppm", "pastEarthAtmosphericN2O_ppm"),
        ),
        (
            UnsupportedReason.DERIVED_CACHE,
            (
                "baselineUnnormalizedSpaceCombatValue",
                "CH4SourcesRecord_ppm",
                "CO2SourcesRecord_ppm",
                "controlPointMaintenanceFreebies",
                "fixedPCGDPToRaiseBaseCPMaintenanceCostBy1",
                "fixedPCGDPToRaiseMissionBaseDifficultyBy1",
                "fixedPCGDPToReduceUnrestBy1",
                "initialSustainabilityMin",
                "maxGlobalExpectedHabSiteProduction_day",
                "N2OSourcesRecord_ppm",
                "resourceMarketValues",
            ),
        ),
        (
            UnsupportedReason.UI_CACHE,
            (
                "currentProjectSort",
                "currentTechSort",
                "fleetScreenClassShowObsolete",
                "habQuickBuildToggle",
                "habQuickBuildWithBoostToggle",
                "projectSortAscend",
                "projectSortShowObsolete",
                "showFinderArmies",
                "showFinderCouncilors",
                "showFinderFleets",
                "showFinderHabs",
                "techSortAscend",
            ),
        ),
        (
            UnsupportedReason.RUNTIME_INTERNAL,
            (
                "altWeightConditionTriggered",
                "difficulty",
                "inactiveNarrativeEvents",
                "moddingActive",
                "moddingUsedAnytime",
                "narrativeEvents",
                "narrativeEventsTargetSpecificCooldowns",
                "pendingNarrativeEvents",
                "priorNarrativeEventData",
                "randomState",
                "repairCPMaintenanceScaling",
                "savedInit",
                "scenarioCustomizations",
                "startDifficulty",
                "storedRandomSeed",
                "tutorialMode",
            ),
        ),
    ),
    "TIGlobalResearchState": _reasons(
        (UnsupportedReason.RUNTIME_INTERNAL, ("useHarshTree",)),
    ),
    NOTIFICATION_QUEUE_STATE_TYPE: _reasons(
        (UnsupportedReason.REFERENCE_GRAPH, ("panelSummaryQueue",)),
        (UnsupportedReason.RUNTIME_INTERNAL, ("alienEvents", "firstTimeTracker", "timerNotificationQueue")),
    ),
}
"""Observed fields that are known and deliberately not copied, with the reason (``domain-field-map.md``).

Only names observed in real saves belong here, each listed explicitly.
"""


def _known(state_type: str, copied: tuple[str, ...]) -> frozenset[str]:
    return (
        frozenset(copied)
        | frozenset(SERIALIZATION_FIELDS)
        | frozenset(RECORD_FIELDS.get(state_type, {}))
        | frozenset(ACKNOWLEDGED_FIELDS.get(state_type, {}))
        | frozenset(
            entry_member_name(field, member)
            for field, members in RECORD_ENTRY_MEMBERS.get(state_type, {}).items()
            for member in members
        )
    )


def entry_member_name(field: str, member: str) -> str:
    """The unknowns-registry name of a member of a record entry: ``Field[].member``."""
    return f"{field}[].{member}"


KNOWN_FIELDS: dict[str, frozenset[str]] = {
    **{state_type: _known(state_type, names) for state_type, names in ENTITY_FIELDS.items()},
    **{state_type: _known(state_type, COMMON_FIELDS + names) for state_type, names in SINGLETON_FIELDS.items()},
}
"""Every field name the parser describes per scanned state type, including record entry members."""
