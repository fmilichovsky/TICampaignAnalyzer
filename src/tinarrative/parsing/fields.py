"""Observed field names per normalized state type.

This is the code form of ``docs/game-data-notes/domain-field-map.md``: only fields observed in real saves
are listed, and a reference field is resolved only when its observed target type has an entity domain.
"""

from __future__ import annotations

from ..model.entities import EntityDomain

COMMON_FIELDS = ("templateName", "displayName", "archived", "exists")

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
}
"""Fields copied into each ``EntityState``; anything else serialized on the object is ignored."""

_ARMY_LIST = (EntityDomain.ARMY, True)

REFERENCE_FIELDS: dict[str, dict[str, tuple[EntityDomain, bool]]] = {
    "TIFactionState": {
        "councilors": (EntityDomain.COUNCILOR, True),
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
}
"""Reference fields and their observed target domain; ``True`` marks a list of references."""

NORMALIZED_DOMAINS: tuple[tuple[EntityDomain, str, str], ...] = (
    (EntityDomain.FACTION, "TIFactionState", "factions"),
    (EntityDomain.NATION, "TINationState", "nations"),
    (EntityDomain.REGION, "TIRegionState", "regions"),
    (EntityDomain.CONTROL_POINT, "TIControlPoint", "control_points"),
)
"""(domain, short state type, ``SaveSnapshot`` attribute) for each normalized collection."""
