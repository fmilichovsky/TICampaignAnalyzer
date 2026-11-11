"""Hand-assigned groups and display names of the councilor trait templates, keyed by ``traitTemplateNames``."""

from __future__ import annotations

from collections.abc import Mapping

# Effects from the game's trait templates (`detectionEspBonus`, `easilyVisible`, additive `Espionage` statMods), as
# the wiki trait list gives them. Implants are left out of the Espionage mods: `attributes` already counts them.
DETECTION_BONUS: Mapping[str, int] = {
    "Billionaire": -1,
    "LowProfile": 2,
    "PuppetMaster": 1,
    "Eminent": -2,
    "Famous": -4,
    "Megastar": -8,
    "OpinionLeader": -2,
    "MediaDarling": -4,
    "ElderStatesman": -4,
    "Firebrand": -3,
    "Demagogue": -6,
    "Undercover": 1,
    "Streetwise": 1,
    "Careless": -2,
    "HardTarget": 1,
    "Expert": -1,
    "Addict": -1,
    "Suspicious": 1,
    "Paranoid": 2,
    "PersonalProtectionMonitor": 1,
    "Scrambler": 1,
    "PersonalDefenseSystem": 1,
    "Countermeasures": 1,
    "GuardianAngelImplant": 1,
    "StealthField": 1,
    "Delinquent": -4,
    "Marked": -4,
}
"""How much harder (positive) or easier (negative) a trait makes the councilor to detect."""
EASILY_VISIBLE = frozenset(
    {
        "Eminent",
        "Famous",
        "Megastar",
        "OpinionLeader",
        "MediaDarling",
        "ElderStatesman",
        "Firebrand",
        "Demagogue",
        "NationalHero",
        "Brazen",
        "Untouchable",
        "Beloved",
        "Martyr",
    }
)
"""The traits the game always reveals: public figures by definition."""
LOW_PROFILE = frozenset({"LowProfile", "PuppetMaster", "Undercover"})
"""The traits of a deliberately kept low public profile."""
ESPIONAGE_MODS: Mapping[str, int] = {
    "Furtive": 3,
    "LoneWolf": 2,
    "Suspicious": 1,
    "Corrupt": 2,
    "Vengeful": 5,
    "SecondWave": 3,
    "AceAssassin": 3,
}
"""Espionage a trait adds on top of ``attributes``."""
