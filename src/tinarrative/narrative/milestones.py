"""The curated milestone list: which technology and project completions are turning points, and how much each matters.

The list is interpretation, not a fact of the save format and not exhaustive. Each entry weighs how much of the tree
the completion opens (directly and through what it unlocks), how much the concept means in the real world, and how
concrete it is: a named capability ranks above a vague stepping stone. A name absent here is a routine
completion: minor, and no milestone.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ..kinds.technology import FACTION_PROJECT_COMPLETED
from ..kinds.technology import TECHNOLOGY_COMPLETED as TECHNOLOGY_COMPLETED_KIND
from ..model.events import Event, Significance

TECHNOLOGY_COMPLETED = TECHNOLOGY_COMPLETED_KIND.event_type
PROJECT_COMPLETED = FACTION_PROJECT_COMPLETED.event_type


@dataclass(frozen=True)
class Milestone:
    significance: Significance
    rationale: str


_DEFINING = Significance.CAMPAIGN_DEFINING
_MAJOR = Significance.MAJOR
_MINOR = Significance.MINOR


def _tier(significance: Significance, entries: Mapping[str, str]) -> dict[str, Milestone]:
    return {name: Milestone(significance, rationale) for name, rationale in entries.items()}


MILESTONE_TEMPLATES: Mapping[str, Milestone] = MappingProxyType(
    {
        **_tier(
            _DEFINING,
            {
                # The two peaks of the energy tree: everything after them is refinement.
                "DeuteriumTritiumFusion": (
                    "first controlled fusion, which opens every fusion reactor family and with them the fusion drives"
                ),
                "AntimatterPropulsion": "antimatter drives, the top of the propulsion tree",
                # Faction endgames: the final project of each faction's path.
                "Project_KilltheHive": "Humanity First's endgame, the destruction of the alien hive",
                "Project_APermanentPeace": "the Academy's endgame, a permanent peace with the aliens",
                "Project_TheGreatJourney": "the Exodus endgame, humanity leaving the solar system",
                "Project_EnslavetheMasters": "the Initiative's endgame, mastery over the aliens",
                "Project_TheFinalAssault": "the Resistance's endgame, the final assault on the invaders",
                "Project_TheOneTruePath": "the Servants' endgame, humanity's submission to the aliens",
                "Project_CoexistencePact": "the Protectorate's endgame, a negotiated coexistence with the aliens",
            },
        ),
        **_tier(
            _MAJOR,
            {
                # Fission and pulse propulsion.
                "NuclearFissioninSpace": "nuclear power leaves Earth, the root of the fission and fusion lines",
                "SolidCoreFissionSystems": "the first space reactors and nuclear-thermal drives",
                "GasCoreFissionSystems": "gas-core fission, the high end of fission and a base of antimatter reactors",
                "FissionPulseDrives": "nuclear-pulse propulsion, the first high-thrust nuclear drives",
                # Fusion.
                "NuclearFusioninSpace": "the methods behind every fusion confinement technique",
                "MagneticPlasmaConfinementTechniques": "magnetic confinement, needed by tokamaks and fusion nozzles",
                "MagneticNozzles": "magnetic nozzles, which open nearly every fusion drive",
                "DeuteriumHelium3Fusion": "helium-3 fusion, and with it helium-3 mining",
                "AneutronicFusion": "aneutronic fusion, fusion power without neutron damage",
                "ProtonProtonFusion": "proton-proton fusion, the reaction of stars and the top of the fusion line",
                "CleanEnergy": "clean energy, the end of fossil power on Earth",
                # Antimatter.
                "AntimatterContainment": "the first stored antimatter",
                "AntimatterMassProduction": "industrial antimatter production, the road to antimatter drives",
                "AntimatterWeaponry": "antimatter weapons",
                # Computing and matter.
                "QuantumComputing": "practical quantum computers",
                "AppliedArtificialIntelligence": "applied AI, behind automation and the hab institutes",
                "MolecularAssemblers": "nanotechnology: matter assembled molecule by molecule",
                # Reach and habitats.
                "MissiontotheMoon": "the Moon opened to habitats",
                "MissiontoMars": "Mars opened to habitats",
                "MissiontoJupiter": "the Jovian system opened to habitats",
                "MissiontotheOuterPlanets": "the outer planets opened to habitats",
                "OutpostHabs": "the first habitats on other bodies",
                "SpaceMiningandRefining": "off-world mining and refining",
                "IndustrializationofSpace": "industry in space: shipyards and orbital construction",
                "ColonyHabs": "permanent colonies, the largest surface habitats",
                "OrbitalTorusHabs": "ring habitats, the largest orbital stations",
                "ClimateChangeMitigation": "the means to reverse climate change",
                # Shipbuilding and navies.
                "OrbitalShipbuilding": "the first ships built in orbit",
                "ImprovedShipbuildingTechniques": "the shipbuilding that opens capital hulls",
                "TitanicSpacecraft": "the largest hulls",
                "MilitarizationofSpace": "armed space activity and space marines",
                "SpaceNavies": "standing navies in space",
                # Geopolitics: techs that open the redrawing of Earth's map.
                "UnityMovements": "the regional unification projects",
                "GreatNations": "the continental unification projects",
                "FallofEmpires": "the breakup projects of the great powers",
                # Alien knowledge.
                "Project_TheirTechnology": "the start of reverse-engineering alien technology",
                "Project_Exotics": "exotic materials, the alien matter behind the late tree",
                "Project_ExoticHybridSystems": "human and exotic technology combined",
                "Project_TheirWarships": "reverse-engineered alien warships",
                "Project_TheirOrigin": "where the aliens come from",
                "Project_HydraLanguage": "the alien language, the first real communication",
                "Project_HydraDiplomacy": "diplomatic contact with the aliens",
                "Project_HydraInterrogation": "interrogation of captured aliens",
                "Project_Pherocytes": "the alien mind-control agent understood",
                "Project_TheirPurpose": "why the aliens came",
                "Project_Wormholes": "the wormhole the aliens came through",
                "Project_TheChokePoint": "the wormhole choke point, the gate to most faction endgames",
                "Project_TheAlienNation": "the project about the alien nation",
                "Project_PublicizeAlienThreat": "the project that makes the alien threat public",
                "Project_AlienMasterProject": "the first alien master project",
                "Project_AlienAdvancedMasterProject": "the advanced alien master project",
                # Faction path commitments: the first project of each faction's endgame path.
                "Project_AppeaseVictory": "the Protectorate commits to appeasing the invaders",
                "Project_CooperateVictory": "the Academy commits to a cooperative resolution",
                "Project_DestroyVictory": "Humanity First commits to purifying the Earth",
                "Project_EscapeVictory": "Exodus commits to leaving the cradle",
                "Project_ExploitVictory": "the Initiative commits to exploiting the aliens",
                "Project_ResistVictory": "the Resistance commits to defending the Earth",
                "Project_SubmitVictory": "the Servants commit to the path to paradise",
                # Warships.
                "Project_Warships": "the first interplanetary warships",
                "Project_ShipsoftheLine": "capital warships",
                "Project_Titans": "titan-class warships, the largest hulls",
                # Drives and reactors.
                "Project_NervaDrive": "the first nuclear-thermal drive",
                "Project_OrionDrive": "the first nuclear-pulse drive",
                "Project_AntimatterPlasmaCoreReactorI": "the first antimatter reactor",
                "Project_AntimatterPlasmaCoreTorch": "an antimatter plasma-core torch",
                "Project_AdvancedAntimatterPlasmaCoreTorch": "an advanced antimatter plasma-core torch",
                "Project_AntimatterBeamCoreTorch": "the pion torch, the antimatter beam-core drive",
                "Project_ProtiumNovaTorch": "a protium nova torch, a top fusion drive",
                "Project_ProtiumConverterTorch": "the protium converter torch, the strongest fusion drive",
                # Habitats.
                "Project_ColonyCore": "the faction's first colony",
                "Project_RingCore": "the faction's first ring habitat",
                "Project_InterstellarLaunchingLaser": "an interstellar launch facility",
                # Earth.
                "Project_CivilianFusionReactors": "fusion power on Earth's grids",
                "Project_MethuselahTherapies": "human life extension",
                "Project_GlobalEmpire": "the project for a global empire",
                # Continental unifications: the project opens the claims a merger needs.
                "Project_UnitedNorthAmerica": "the claims for a united North America",
                "Project_GreaterUnitedNorthAmerica": "the claims for a greater united North America",
                "Project_GreatEuropa": "the claims for a united Europe",
                "Project_Pan-AsianCooperative": "the claims for a pan-Asian combine",
                "Project_AfricanUnion": "the claims for an African union",
                "Project_SouthAmericanUnion": "the claims for a South American union",
                "Project_GreaterIndia": "the claims for a greater India",
                "Project_ForwardRussia": "the claims for a restored greater Russia",
                "Project_TheGreaterCaliphate": "the claims for a greater caliphate",
                "Project_TheHouseofIslam": "the claims for a house of Islam",
                "Project_GreaterAustronesia": "the claims for a greater Austronesia",
                # Fall of empires: the project opens the breakup of a great power.
                "Project_EndofAmerica": "the breakup of the United States",
                "Project_EndofChina": "the breakup of China",
                "Project_EndofIndia": "the breakup of India",
                "Project_DissolutionofRussia": "the breakup of Russia",
            },
        ),
        **_tier(
            _MINOR,
            {
                # Propulsion and fission stepping stones.
                "DeepSpacePropulsionConcepts": "the concepts behind every deep-space drive",
                "ElectromagneticPropulsion": "electromagnetic propulsion",
                "ElectrostaticPropulsion": "ion drives",
                "MoltenCoreFissionSystems": "molten-core fission",
                "AdvancedFissionSystems": "advanced fission, the top of the fission line",
                "HeavyPulsedPropulsion": "heavy nuclear-pulse propulsion",
                # Fusion techniques.
                "Tokamaks": "tokamak fusion reactors",
                "InertialPlasmaConfinementTechniques": "inertial confinement fusion",
                "ZPinchTechniques": "z-pinch fusion",
                "ElectrostaticPlasmaConfinement": "electrostatic confinement fusion",
                "DeuteriumDeuteriumFusion": "deuterium-deuterium fusion",
                "TerawattFusionReactors": "terawatt fusion reactors",
                # Weapons.
                "HighEnergyLasers": "high-energy lasers",
                "ArcLasers": "arc lasers",
                "PhasedArrayLasers": "phased-array lasers",
                "ParticleCannon": "particle beams",
                "MassDrivers": "mass drivers",
                "Railguns": "railguns",
                "Coilguns": "coilguns",
                "PlasmaWeapons": "plasma weapons",
                "UltravioletCombatLasers": "ultraviolet combat lasers",
                "TargetedBiologicalWarfare": "targeted biological weapons",
                # Computing.
                "PhotonicComputing": "photonic computing",
                "AdvancedNeuralNetworks": "advanced neural networks",
                "Cybernetics": "cybernetics",
                "QuantumEncryption": "quantum encryption",
                "WhiteCollarAutomation": "automation of office work",
                "AdministrationAlgorithms": "algorithmic administration",
                # Life and habitats.
                "SettlementHabs": "settlements, the middle surface habitats",
                "OrbitalRingHabs": "orbitals, the middle orbital stations",
                "ExtendedSpaceSurvival": "long-term survival in space",
                "DesignerLifeforms": "designer life forms",
                "Genies": "genetically engineered humans",
                "MindandMachine": "the merging of mind and machine",
                # Materials.
                "CarbonNanotubes": "carbon nanotubes",
                "Superalloys": "superalloys",
                "AdvancedAtomicManipulation": "atomic-scale manipulation",
                "AdvancedSuperconductors": "advanced superconductors",
                "SuperconductingMagnets": "superconducting magnets",
                "HighTemperatureSuperconductors": "high-temperature superconductors",
                "Diamondoids": "diamondoid materials",
                # Military.
                "PrinciplesofSpaceWarfare": "the doctrine that opens space warfare",
                "TerrestrialMilitaryScience": "military science against the alien threat on Earth",
                "ArrivalSecurity": "security against the alien threat",
                "NetworkedGlobalDefense": "a networked global defense",
                "FleetLogistics": "fleet logistics",
                # Space and missions.
                "MissionToSpace": "the first step to space",
                "AdvancedHeatManagementConcepts": "the heat management behind reactors and radiators",
                "InSituResourceUtilization": "living off local resources in space",
                "MissiontotheAsteroids": "the asteroid belt opened to habitats",
                "MissiontoVenus": "Venus opened to habitats",
                "MissiontotheInnerPlanets": "Mercury opened to habitats",
                "MissiontoSaturn": "the Saturnian system opened to habitats",
                # Vague social stepping stones: wide gateways, little concrete capability of their own.
                "WeAreNotAlone": "the acknowledgement that humanity is not alone",
                "AdAstra": "the turn of humanity's ambitions to space",
                "DirectedSpaceResearch": "directed research in space",
                "ArrivalInternationalDevelopment": "international development after the arrival",
                "SpaceCommerce": "commerce in space",
                "OurSpaceFuture": "humanity's future in space",
                "ArrivalGovernance": "governance after the arrival",
                "IntegratedEarthSpaceEconomy": "an integrated Earth and space economy",
                "InterplanetaryPolities": "polities across the planets",
                "Accelerando": "the accelerating pace of change",
                "IndependenceMovements": "the independence movement projects",
                # Hulls.
                "Project_PatrolVessels": "patrol vessels",
                "Project_FleetCombatants": "fleet combatants",
                # Drives and reactors.
                "Project_LarsDrive": "the entry molten-core fission drive",
                "Project_HelionNovaTorch": "a helion nova torch",
                "Project_ZetaDeuteronTorch": "a zeta deuteron torch",
                "Project_BoranePlasmajetTorch": "a borane plasmajet torch",
                "Project_NeutronFluxTorch": "the Poseidon neutron-flux torch",
                "Project_SolidCoreFissionReactorI": "the first fission reactor for ships",
                "Project_FusionPile": "the first fusion power plant on a habitat",
                "Project_FusionTokamakI": "the first tokamak fusion reactor",
                "Project_InertialConfinementFusionReactorI": "the first inertial confinement fusion reactor",
                "Project_ZPinchFusionReactorI": "the first z-pinch fusion reactor",
                "Project_MirrorCellFusionReactorI": "the first mirror-cell fusion reactor",
                "Project_ElectrostaticConfinementFusionReactorI": "the first electrostatic confinement fusion reactor",
                "Project_HybridConfinementFusionReactorI": "the first hybrid confinement fusion reactor",
                "Project_AntimatterBeamCoreReactor": "the antimatter beam-core reactor",
                "Project_InertialConfinementFusionReactorVII": "the last inertial confinement fusion reactor",
                # Habitats.
                "Project_OrbitalCore": "the faction's first orbital",
                "Project_SettlementCore": "the faction's first settlement",
                "Project_Shipyard": "shipyards",
                "Project_Spaceworks": "spaceworks",
                "Project_Helium-3Mine": "helium-3 mines",
                "Project_AntimatterFarm": "antimatter farms",
                "Project_Supercollider": "the supercollider",
                # Alien knowledge.
                "Project_TheirSignatures": "the first study of alien signatures",
                "Project_TheirOperations": "the study of alien operations",
                "Project_AlienContainment": "alien containment",
                "Project_TheirComputers": "alien computers",
                "Project_TheirDemands": "the alien demands",
                "Project_TheirWeakness": "the alien weakness",
                "Project_PherocyteResistance": "resistance to pherocytes",
                "Project_PherocyteMastery": "mastery of pherocytes",
                "Project_HydraBiowarfare": "biowarfare against the aliens",
                "Project_ANewHome": "a new home for humanity",
                # Earth.
                "Project_Cyborging": "cyborging",
                "Project_DNARepairs": "DNA repair therapies",
                "Project_SingletonViruses": "singleton viruses",
                "Project_CarbonRecaptureTechnologies": "carbon recapture",
                "Project_IndependentHabitats": "independent habitats",
                "Project_GlobalAmbition": "the project for global ambition",
                "Project_GlobalArmsControlRegime": "a global arms control regime",
                "Project_GlobalCounterproliferationRegime": "a global counterproliferation regime",
                # Regional unifications: the project opens the claims a merger needs.
                "Project_EuropeAscendant": "the claims for a European union",
                "Project_TheCaliphate": "the claims for a caliphate",
                "Project_UnitedArabLeague": "the claims for a united Arab league",
                "Project_SlavicCommonwealth": "the claims for the Intermarium",
                "Project_LiberatingMainlandChina": "the claims for liberating mainland China",
                "Project_GreaterIndonesia": "the claims for a greater Indonesia",
                "Project_UnitedTurkestan": "the claims for a united Turkestan",
                "Project_GranColombia": "the claims for Gran Colombia",
                "Project_GreaterDominion": "the claims for a greater dominion",
                "Project_UnidadColombia": "the claims for Unidad Colombia",
                "Project_SoutheastAsianAlliance": "the claims for a Southeast Asian alliance",
                "Project_GreaterMalaysia": "the claims for a greater Malaysia",
                "Project_CommonwealthRestored": "the claims for a restored Commonwealth",
                "Project_PacificLeague": "the claims for a Pacific defense league",
            },
        ),
    }
)


def completed_template(event: Event) -> str | None:
    if event.event_type == PROJECT_COMPLETED:
        name = event.attribute("project")
        return name if isinstance(name, str) else None
    if event.event_type == TECHNOLOGY_COMPLETED and event.entities:
        return event.entities[0].entity_id.key
    return None


def milestone_of(event: Event) -> Milestone | None:
    name = completed_template(event)
    return MILESTONE_TEMPLATES.get(name) if name is not None else None
