"""Labels in faction ledgers that are normalized into transaction events."""

from __future__ import annotations

COUNCILOR_MISSIONS: frozenset[str] = frozenset(
    {
        "Coup",
        "Purge",
        "Crackdown",
        "HostileTakeover",
        "Propaganda",
        "Stabilize",
        "Inspire",
        "Unrest",
        "Assassinate",
        "Detain",
        "Turn",
        "Advise",
        "Extract",
        "Augmentation",
        "SetNationalPolicy",
        "DefendInterests",
        "InvestigateCouncilor",
        "StealProject",
        "SabotageProject",
        "SabotageFacilities",
        "Abductions",
        "EnthrallElites",
        "TerrorizeRegion",
        "Xenoform",
        "AssaultAlienAsset",
        "Contact",
    }
)

SPACE_OPERATIONS: frozenset[str] = frozenset(
    {
        "FoundColonyOperation",
        "FoundOrbitalOperation",
        "FoundOutpostOperation",
        "FoundPlatformOperation",
        "FoundRingOperation",
        "FoundSettlementOperation",
        "LaunchProbeOperation",
        "LaunchAllProbeOperation",
        "RepairFleetOperation",
        "ResupplyOperation",
        "ResupplyAndRepairOperation",
        "TransferOfficersOperation",
    }
)

ASSET_CHARGES: frozenset[str] = frozenset({"Ship Construction", "Hire Councilor", "Global Milestone"})

ALLOWED_LEDGER_LABELS: frozenset[str] = COUNCILOR_MISSIONS | SPACE_OPERATIONS | ASSET_CHARGES
