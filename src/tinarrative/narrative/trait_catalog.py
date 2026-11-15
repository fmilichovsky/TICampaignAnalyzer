"""Effects of the councilor trait templates that the dossier measures, keyed by ``traitTemplateNames``."""

from __future__ import annotations

from collections.abc import Mapping

# Effects from the game's trait templates (`detectionEspBonus`, `easilyVisible`, additive attribute `statMods`), as
# the wiki trait table gives them (docs/game-data-notes/wiki-sources/trait-templates.csv).
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
SKILL_MODS: Mapping[str, Mapping[str, int]] = {
    "PhysicistII": {"Science": 1},
    "ChemistII": {"Science": 1},
    "AstronomerII": {"Science": 1},
    "DoctorII": {"Science": 1},
    "SocialScientistII": {"Science": 1},
    "MilitaryScientistII": {"Science": 1},
    "ComputerScientistII": {"Science": 1},
    "PhysicistIII": {"Science": 2},
    "ChemistIII": {"Science": 2},
    "AstronomerIII": {"Science": 2},
    "DoctorIII": {"Science": 2},
    "SocialScientistIII": {"Science": 2},
    "MilitaryScientistIII": {"Science": 2},
    "ComputerScientistIII": {"Science": 2},
    "Brazen": {"Security": -1},
    "Furtive": {"Espionage": 3, "Persuasion": -1, "Administration": -1},
    "Extremist": {"Investigation": 1},
    "Fanatic": {"Investigation": -1},
    "Sociopath": {"Persuasion": 1},
    "Pacifist": {"Command": -3},
    "Averse": {"Security": 1},
    "HardTarget": {"Security": 2},
    "LoneWolf": {"Administration": -1, "Command": -1, "Espionage": 2},
    "AwkwardGenius": {"Persuasion": -3, "Command": -3, "Science": 3, "Investigation": 2},
    "Crew": {"Security": 1},
    "Expert": {"Persuasion": 1, "Science": 1, "Security": -1},
    "Academic": {"Command": -1},
    "Technocrat": {"Science": 1, "Administration": 3},
    "Addict": {"Security": -2},
    "Veteran": {"Command": 1, "Security": 1},
    "Cynic": {"Investigation": 1},
    "Suspicious": {"Investigation": 2, "Security": 2, "Espionage": 1},
    "ConspiracyTheorist": {"Investigation": 2, "Security": 1, "Persuasion": -2},
    "Paranoid": {"Investigation": 2, "Security": 3, "Persuasion": -2},
    "Corrupt": {"Espionage": 2},
    "Survivor": {"Security": 1},
    "Vengeful": {"Espionage": 5, "Security": 3, "Command": 3},
    "Declining": {"Investigation": -1, "Command": -1},
    "SecondWave": {"Espionage": 3, "Security": 3},
    "Indebted": {"Persuasion": -2},
    "Delinquent": {"Persuasion": -4, "Security": -3},
    "Marked": {"Security": -10},
    "Untouchable": {"Security": 3},
    "Beloved": {"Persuasion": 1},
    "Demanding": {"Administration": 2, "Command": 1},
    "Martyr": {"Persuasion": 1, "Security": -1},
    "AceAssassin": {"Espionage": 3},
    "ProjectDirector": {"Administration": 1},
    "ProjectAdministrator": {"Administration": 2},
    "Innovative": {"Science": 1},
    "CombatAstronaut": {"Command": 1},
}
"""The attribute points a trait adds on top of ``attributes``, which leaves trait bonuses out.

Only unconditional additive modifiers: one that depends on where the councilor is or on the nation (democracy,
education, inequality, unrest, the home nation) is not modelled. Implants are left out, since ``attributes``
already counts them.
"""
