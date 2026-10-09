"""Observed field names per normalized state type.

This is the code form of ``docs/game-data-notes/domain-field-map.md``: only fields observed in real saves
are listed, and a reference field is resolved only when its observed target type has an entity domain.
"""

from __future__ import annotations

from ..model.entities import EntityDomain
from .references import ExpectedDomains

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
        "habType",
        "tier",
        "inCombat",
        "underAssault",
        "underBombardment",
        "anyCoreCompleted",
        "staticHab",
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

_ARMY_LIST = (EntityDomain.ARMY, True)
_FACTION = (EntityDomain.FACTION, False)
_REGION = (EntityDomain.REGION, False)
_SPACE_OBJECT = (EntityDomain.SPACE_OBJECT, False)
_PLACE = (frozenset((EntityDomain.REGION, EntityDomain.SPACE_OBJECT)), False)
"""A councilor location: observed to point at a ``TIRegionState`` or a ``TIHabState``."""

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
    },
    "TINationState": {
        "capital": (EntityDomain.REGION, False),
        "regions": (EntityDomain.REGION, True),
        "claims": (EntityDomain.REGION, True),
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
        "armies": _ARMY_LIST,
    },
    "TICouncilorState": {
        "faction": _FACTION,
        "detainingFaction": _FACTION,
        "homeRegion": _REGION,
        "location": _PLACE,
        "priorLocation": _PLACE,
        "orgs": (EntityDomain.ORGANIZATION, True),
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
hab modules) or whose target was never observed non-null (``agentForFaction``, ``storedFaction``) are
deliberately absent and stay raw.
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
