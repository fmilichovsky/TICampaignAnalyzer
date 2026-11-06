# Domain field map for `terra_invicta_json_v1`

This is a field-level handoff for normalizers and analyzers described in [`docs/architecture.md`](../architecture.md). It records *serialized field names only*—not player values—from the inspected complete save. The state collections use the pair-map decoding in [Containers, identity, and references](containers-and-references.md).

## Observed facts

| Normalized domain | State type | Observed fields relevant to the architecture |
| --- | --- | --- |
| Campaign time | `TITimeState` | `daysInCampaign`, `currentQuarterSinceStart`, `currentDateTime` (`year`, `month`, `day`, `hour`, `minute`, `second`, `millisecond`), `masterMetaTemplateName`, `scenarioMetaTemplateName` (`TIME_FIELDS`) |
| Campaign metadata | `TIMetadataState` | `gameTimeString`, `playerFactionName`, `difficulty`, `playedWithMods`, `selectedFactionsForScenario` (`METADATA_FIELDS`; a list of faction template-name strings, observed as 8 entries each matching a `TIFactionState.templateName` in the same save, copied without resolution); the scenario/difficulty setting strings are acknowledged as `runtime_internal`, not narratively relevant |
| Factions | `TIFactionState` | `player`, `councilors`, `knownSpies`, `fleets`, `habSectors`, `controlPoints`, `armies`, `resources`, `finishedProjectNames`, `currentProjectProgress`, `researchWeights`, `intel`, `factionGoals`, `knowsWinCondition`, `unlockedVictoryObjective`, `defeated`, `sabotagedProjects`, `unassignedOrgs`, `shipDesigns` (keyed by `dataName`, see below), `shipsBuiltInClass`, `techNameContributionHistory` |
| Nations | `TINationState` | `capital`, `regions`, `allies`, `rivals`, `claims`, `wars`, `armies`, `publicOpinion`, `GDP`, `inequality`, `education`, `democracy`, `cohesion`, `unrest`, `militaryTechLevel`, `controlPoints`, `federation`, `breakawayParent`, `breakaways`, `originalCapital`, `hostileClaims`, `advisingCouncilors` (empty on every nation; copied raw), the flags `aggregateNation`, `alienNation`, `military`, `nuclearProgram`, `spaceFlightProgram`, `policy_closedBorders`, `policy_noMineralDevelopment`, `policy_noNukes`, `policy_noOilDevelopment`, the numbers `numNuclearWeapons`, `numControlPoints`, `spaceFunding_year`, `sustainability`, `factionUnrestAttempts` (pair map, see below), the six `tracker_<Statistic>ChangeReason_AllTime` objects (`Cohesion`, `Democracy`, `Education`, `GDP`, `Inequality`, `Unrest`: cause name -> cumulative number, copied as a map), and `tracker_PCGDP_ByQuarter` (see below) |
| Control points | `TIControlPoint` | `nation`, `faction`, `benefitsDisabled`, `defended`, `crackdownExpiration`, `defendExpiration`, `controlPointType`, `positionInNation`, `controlPointPriorities` |
| Regions | `TIRegionState` | `nation`, `leadOccupier`, `occupations`, `populationInMillions`, `alienFacility`, `alienActivity`, `xenoforming`, `isBeingAnnexed`, `annexingArmy`, `adjacencies`, `armies`, `abductions`, `alienCrashdown`, `alienLanding`, `boostFacility`, `missionControlFacility`, `spaceDefenseFacility`, `spaceFacilities`, `originalColony`, `annexationBeginDate`, `annexationDaysLeft`, `antiSpaceDefenses`, `boostPerYear_dekatons`, `missionControl`, `numSTOFighters`, `isCounterfiring`, `nuclearDetonations`, `underBombardment` (the region's own flag, distinct from the hab field of the same name), `colonyRegion`, `permanentlyDecolonized`, `coreEconomicRegion`, `oilRegion`, `resourceRegion`, `oceanType` |
| Mission control facilities | `TIMissionControlFacilityState` | `region`, `spaceFacilityType` |
| Armies | `TIArmyState`, `TIMegafaunaArmyState` | `currentRegion`, `faction`, `homeRegion`, `strength`, `destroyed`, `armyType`, `deploymentType` |
| Councilors | `TICouncilorState` | `faction`, `location`, `homeRegion`, `detainingFaction`, `recruitDate`, `attributes`, `orgs`, `status`, `XP`, `typeTemplateName`, `traitTemplateNames`, `gender`, `dateBorn` (componentized dates normalized to ISO text) |
| Missions | `TIMissionState` | `councilor`, `target` (typed reference, see below), `missionOutcome` (`None` or `Aborted`), `resources`; `startTime`, `resolveTime` (always `null`) and `resolveTimeAssigned` are acknowledged `runtime_internal` |
| Organizations | `TIOrgState` | `assignedCouncilor`, `factionOrbit`, `homeRegion`, `tier`, `applyingBonuses`, `takeoverDefense`, `XPModifier`, `projectCapacityGranted`, the costs (`costMoney`, `costInfluence`, `costOps`, `costBoost`), the monthly incomes and mission-control income, and the attribute and priority bonuses; the presentation fields `orgIconPath`, `orgIconTemplateName` and `displayNameWithArticle` are acknowledged `ui_cache` |
| Fleets | `TISpaceFleetState` | `ships`, `barycenter`, `parentFleet`, `faction`, `orbitState`, `dockedLocation`, `inCombat`; the trajectory, operations, bombardment, and presentation fields are acknowledged below |
| Ships | `TISpaceShipState` | `fleet`, `lastRefitDate`, `kills` (list of strings) |
| Habs | `TIHabState` | `faction`, `orbitState`, `barycenter`, `dockedFleets`, `habType`, `tier`, `inCombat`, `underAssault`, `underBombardment`, `anyCoreCompleted`; joined from the core module (slot 0 of the first sector): `coreConstructionCompleted`, `coreStartBuildDate`, `coreCompletionDate`, `corePriorCompletionDate` (ISO text or `null`) |
| Space bodies | `TISpaceBodyState` | `barycenter` (the parent body: `null` on Sol only, Sol on about two thirds of the rest, otherwise a planet; 2026-10-19, eight private saves, 240 and 373 bodies) alongside `templateName`/`displayName`. No kind member is serialized, so a moon is told from a planet by its parent. `habSites`, `nations`, `orbits`, `maxHabTier`, `playerTag`, `currentModelResource`, `solarMirrorBonus`, `HohmannDates` and the vectors are acknowledged, not normalized |
| Hab modules | `TIHabModuleState` | `sector`, `slot`, `constructionCompleted`, `decommissioning`, `destroyed`, `powered`, `priorModuleCompleted`, `startBuildDate`, `completionDate`, `decommissionDate` (strings), `destroyedTime`, `buildCost`; not normalized, only the core's construction state and dates are copied onto its hab |
| Research | `TIGlobalResearchState` | `finishedTechsNames`, `finishedOneTimeOnlyProjectNames`, `techProgress` (elements: `techTemplateName`, `accumulatedResearch`, `factionContributions`, `selector`), `campaignStartYear`, `endGameTechsCompletedByCategory` |
| Wars | `TIWarState` | `attacker`, `defender`, `originalAttacker`, `originalDefender`, `_attackingAlliance`, `_defendingAlliance`, `nukedRegions`, `annexedRegions` (empty in every observed war; copied raw), `defensiveNukes`, `peaceOfferHistory`, `cohesionGainByNation` (pair maps, see below); `startDate` and `dateOfLastFighting` are save-carried records. The container was an empty `{}` in the first inspected sample |
| Federations | `TIFederationState` | `members`, `federationName` (string or `null`), `adjective` |
| Region alien states | `TIRegionUFOCrashdownState`, `TIRegionUFOLandingState`, `TIRegionAlienFacilityState`, `TIRegionXenoformingState`, `TIRegionAlienActivityState` (one `region alien state` domain) | every type: `region`; crashdown: `crashdownPresent` (`crashdownTime` is a save-carried record); landing: `landingPresent`, `deployingArmy`, `supportingArmyBuildup`, `currentHP`; facility: `built`, `currentHP`; xenoforming: `xenoformingLevel`; activity: `alienMissionsDetected` (pair map, see below). 363 entries of each type in each of eight private saves (2026-10-15) |
| Global values | `TIGlobalValuesState` (singleton, one `global values` entity) | `interstateWars` (list of references), `nuclearStrikes`, `looseNukes`, `currentNuclearExchanges` (empty list throughout), the atmospheric and sea-level values and trigger flags; `globalMilestones`, `triggeredOncePerTargetEvents` and `triggeredOncePerCampaignEvents` are save-carried records. Acknowledged fields are listed below. `latestSaveVersion` remains available to raw-save game-version detection; `realWorldCampaignStart` remains available to raw-save campaign profiling. One entry per save with an ID stable within each campaign (2026-10-16, eight private saves of two campaigns) |
| Notification queue | `TINotificationQueueState` (singleton, one `notification queue` entity) | only the common fields; `notificationSummaryQueue` is a save-carried record (the game's notification log). Acknowledged: `panelSummaryQueue` (`reference_graph`: an object of the five category lists `Missions`, `CouncilorSightings`, `EarthEvents`, `SpaceEvents`, `Bombardment`, each holding inline entries or `{"$ref"}` pointers, some into the summary queue and some elsewhere), `timerNotificationQueue` (the same entry shape, 0 or 60 entries; pending timers), `firstTimeTracker` (pair map) and `alienEvents` (number) (`runtime_internal`). One entry per save (2026-10-16, eight private saves of two campaigns) |

Every inspected entity in the normalized types also carried `templateName`, `displayName`, `archived`, and `exists`. Observed on 2026-10-09 in two private complete saves (structure only): every field named above for councilors, armies, fleets, ships, habs, hab modules, and research is present in every entry of its type, and the field-name sets of both saves are identical.

Further 2026-10-09 observations (structure only):

- Every `techProgress` element's `techTemplateName` also appeared in `finishedTechsNames` (3 of 3 in both saves), so a progress entry is not evidence that research is *unfinished*.
- `TISpaceShipState.damagePoints` holds `{w, x, y, z}` vectors, not hit points; actual damage is in `armor`, `damagedParts`, and `damagedSystems`.
- `TISpaceFleetState.currentOperations` elements (2026-10-14, five private saves; structure only) carry `startDate` as a componentized date, but `completionDate` was either a componentized date with an extra `$id` member or a bare `{"$ref"}` object pointing at another date. It is the JSON.NET reference preservation seen in ship modules. Because the dates form a `$id`/`$ref` graph, the list is not normalized (its observed targets include `TIRegionXenoformingState`, which has its own domain).
- `TISpaceShipState.kills` is a list of strings, not references.
- The nation statistics (`GDP`, `inequality`, `education`, `democracy`, `cohesion`, `unrest`, `sustainability`, `militaryTechLevel`, `spaceFunding_year`, `numNuclearWeapons`, `numControlPoints`, each `publicOpinion` key) and the six `tracker_<Statistic>ChangeReason_AllTime` maps feed the `nation.statistic_shifted` event (`analyzers/politics/nation_metrics.py`): a shift past an interval-scaled threshold, with the tracker's per-reason deltas as `causes`. Sub-threshold changes and tracker-only changes stay in the diff; nations without regions are skipped (2026-10-18, six private saves: their values never changed).
- The nation flags `nuclearProgram` and `policy_closedBorders`, `policy_noMineralDevelopment`, `policy_noNukes`, `policy_noOilDevelopment` feed `nation.nuclear_program_changed` and `nation.policy_changed` (`analyzers/politics/nations.py`), one event per changed flag.
- `TINationState.tracker_PCGDP_ByQuarter` (2026-10-14, five private saves) is a list of `{Key, Value}` objects: an integer quarter index and a number. The keys are distinct in every nation of every save. In the latest save they are contiguous up to `currentQuarterSinceStart` in every nation; 163 of 295 nations start at quarter 0, 121 at quarter 1, and 11 at a negative quarter (-44 to -20) with the list not in key order. It is not a reference pair map; `PAIR_MAP_FIELDS` lists it with integer keys and the normalizer copies it as a quarter (decimal text) -> number map, so a new quarter diffs as one added key. *Hypothesis:* the negative quarters are history inherited from before the campaign start; not checked.
- Ship module objects (`hullWeapons`, `noseWeapons`, `utilityModules`, `ammo`, `batteryCharge`, `damagedParts[].module`) and fleet `trajectory.Segments` sometimes contain `$id`/`$ref` members or a `{"$id", "$content"}` wrapper. *Hypothesis:* JSON.NET reference preservation. The normalizer keeps these values raw.
- `TIHabState.orbitState` was non-null in 73 of 269 habs and `habSite` in the other 196 (counts only, not checked per entry). *Hypothesis:* exactly one of the two is set.
- Observed on 2026-10-14 in five private complete saves of one campaign (2045-08 to 2046-10, structure only): `TIHabState.globalPosition` is an `{x, y, z}` object of floats in every hab, like the fleet field; `inEarthLEO` was true in 18 habs of each save; `coreDefended` was false and `coreDefendExpiration` `null` in every hab, and `advisingCouncilors` was empty in every hab; all six fields were present in every hab. *Hypothesis:* `coreDefended`/`coreDefendExpiration` mirror the control-point `defended`/`defendExpiration` pair, so a non-null `coreDefendExpiration` is a componentized date object; these fields are acknowledged rather than normalized.
- Observed on 2026-10-14 in five private saves of one campaign (363 regions each, structure only): every
  `TIRegionState` field added for the region normalization is present on every region. `annexationBeginDate` was `null` and
  `annexationDaysLeft` `0` on every region; `isCounterfiring`, `underBombardment` and `oilRegion` were `false` and
  `nuclearDetonations` `0` everywhere, so their non-default shapes are not observed. *Hypothesis:* a set
  `annexationBeginDate` is a componentized date like `TIControlPoint.crackdownExpiration`. `oceanType` is a string with
  two distinct values; the remaining flags and counters held both default and non-default values.
- Observed on 2026-10-19 in eight private saves of two campaigns (363 regions each, structure and counts only):
  `populationInMillions` is a float on every region, from 0.046 to about 300. Summed over a nation's `regions` (or
  over the regions a territory event moved) it is the `population` attribute of `nation.appeared`/`disappeared` and
  `nation.territory_gained`/`lost`; a region without a number makes the sum unknown.
- Ship `templateName` is a design name shared by many ships; hab `templateName` was null in 267 of 269 habs. Neither is a secondary key.
- Observed on 2026-10-14 in five private complete saves of one campaign (structure only): every `TIArmyState` (19 per save) and `TIMegafaunaArmyState` (0 or 1 per save) carried `currentOperations` as an empty list, `destinationSeaDate` and `embarkDate` as `null`, and `huntingXenofauna` as `false`. These fields are acknowledged rather than normalized. *Hypothesis:* army operation elements share the fleet element keys (`operationDataName`, `target`, `startDate`, `completionDate`) and the two transit dates use the componentized date object; neither was seen on an army.

Faction fields observed on 2026-10-14 in five private complete saves of one campaign (2045-08 to 2046-10, structure only; 8 factions per save, every field present on every faction):

- `knowsWinCondition` and `unlockedVictoryObjective` are booleans. `sabotagedProjects` is a list of project-name strings (0–8 per faction).
- `defeated` is a boolean. Observed on 2026-10-14 in three private complete saves of a second campaign written by a newer game build (8 factions per save, `false` on every faction); it is absent from all five saves of the older campaign, so it normalizes to unknown there rather than `false`. *Hypothesis:* it turns `true` when a faction is eliminated; no `true` value has been observed.
- `unassignedOrgs` is a list of `{"value": id}` references (63–73 in total per save); every ID resolved to a `TIOrgState` entry.
- `shipsBuiltInClass` is an object: design name -> integer count (0–91 keys per faction). `techNameContributionHistory` is an object: tech name -> float (148 keys on 7 factions, empty on the eighth).
- `shipDesigns` is a list of design objects (0–117 per faction, 334–405 per save), each with the same 25 members, among them `dataName` (string), `_displayName` (string), `friendlyName` (`null` in all 1,765 designs inspected), `hullName`, `driveName`, `powerPlantName`, `radiatorName`, `noseArmor`/`lateralArmor`/`tailArmor` (objects), the weapon/module template-entry lists and `_unnormalizedCombatValue` (float). No design contained `$id`/`$ref`. `dataName` was unique within each faction and across all factions of a save, and every ship `templateName` (545–588 ships per save) matched a design `dataName`. Between consecutive saves designs were added and removed (up to 111 added and 44 removed per interval); a design kept under the same `dataName` changed only in `_unnormalizedCombatValue` (0–293 per interval). *Hypothesis:* that member is a recomputed rating, not a player edit. Some `shipsBuiltInClass` keys (7 of 8 factions) name no current design of the faction; *hypothesis:* they are designs since removed.

Organization templates observed on 2026-11-03 in the Protectorate benchmark samples (structure and game identifiers only):

- A generated organization has a `templateName` of the form `Random<Category><n><m>`. Observed categories: `Aerospace`, `BusinessManagement`, `Commercial`, `Criminal`, `Engineering`, `Influence`, `InformationTechnology`, `Investigations`, `NGO`, `Research`, `Resource`, `Security`, `SpaceMining` and `Vigilante` (`Vigilante` in 3 of about 1,400 organizations over three saves).
- A real-world organization has a named template (`CentralIntelligenceAgency`); about 590 of about 1,400 organizations over three saves, 270 per save in the largest. Its `displayName` is a real institution, and its nature shows only in the effects it grants.
- *Hypothesis:* the effects tell the nature. `spoilsBonus` of at least 0.02 with a positive money income marks criminal groups; `spaceflightBonus`, `spaceDevBonus` or `MCBonus` marks space bodies; `miningBonus` marks resource companies; `incomeResearch_month` marks research bodies; `espionage` plus `investigation` of at least 2, or `oppressionBonus`, marks security services; `incomeOps_month` with `command` or `security` marks special forces, since commando units carry `security` but little espionage or investigation. A hand check of one save's 270 organizations found the labels plausible except a handful (for example `Drug Enforcement Administration`, `Kopassus`) left as `other`. A second check on 2026-11-03 against the game's organization templates found more misses (commando units without `command`, `Mossad` as military), so named templates are now categorized by hand and the effects, reordered as above, serve only as a fallback (127 of the 196 named templates then match the hand categories, against 111 before; several hand categories, such as `engineering_industry` or `militant`, have no effect signature).
- Observed on 2026-11-03 in all 20 private saves of the Protectorate and Resist campaigns: 237 distinct named organization templates; every one is a key of the hand-assigned catalog.

Organization effects on councilors observed on 2026-11-05 in all 20 private saves of the Protectorate and Resist campaigns (structure and counts only), read by the councilor dossier:

- The seven skill bonuses of `TIOrgState` (`persuasion` … `security`, lowercase) are non-negative integers (0–15); the 13 priority and space bonuses (`economyBonus` … `MCBonus`) are non-negative floats (0–0.2).
- Distribution of the 13 priority and space bonuses, observed on 2026-11-06 in all 20 private saves of the Protectorate and Resist campaigns: values step by 0.01, most often 0.02–0.03, with 0.10 a frequent larger step. In the latest save of each campaign 58% (Protectorate) and 56% (Resist) of organizations carry none; most of the rest carry one, at most five. The sum per organization is at most 0.09 at tier 1, 0.24 at tier 2 and 0.45 at tier 3. Ceilings differ per field: `economyBonus` never exceeds 0.06 though it is among the most common, `oppressionBonus` is 0.10 in 111 organization-save pairs, `militaryBonus` and `spoilsBonus` reach 0.20. Summed over a human-faction councilor's organizations, per cause: Protectorate (474 councilor-save pairs) median 0.04, 90th percentile 0.10, and 31% of councilors have none; Resist (208) median 0.06, 90th percentile 0.15, and 3% have none. The effective number of causes, (sum)² / sum of squares, has median 1.8 in Protectorate and 3.0 in Resist.
- `TICouncilorState.attributes` leaves organization bonuses out. No attribute value of a faction councilor is above 25 (Protectorate at most 17, Resist at most 25, reached in every save), while the attribute plus the bonuses of the councilor's organizations goes above 25 in 0–2 of 217–280 councilor skill pairs per Protectorate save and 15–18 of 322–336 per Resist save. In one Protectorate interval, all six attribute drops were unrelated to the bonus of an organization the councilor lost. *Hypothesis:* 25 is the game's cap on attribute plus organization bonuses.
- *Hypothesis:* implants are counted in `attributes`. Of 13 implant gains over consecutive saves, several came with a one-point attribute step and no organization change (`Datajack` and `Science`, `ForceTracker` and `Persuasion`), but others moved nothing, and every `IntelligentAssistant` gain moved two or three attributes in both directions, so the step size per implant is not established. On 2026-11-06, both `Scrambler` gains (+1 Espionage in the trait template) came with a one-point `Espionage` step, one of them without an organization change, and no holder of `Scrambler`, `Countermeasures` or `StealthField` had an `Espionage` below the implant's bonus.
- `TICouncilorState.attributes` leaves the additive attribute bonuses of non-implant traits out. Observed on 2026-11-06 in all 20 private saves of the Protectorate and Resist campaigns: `Espionage` is 0 or more, yet it is below the trait's own Espionage bonus in 53 councilor-save pairs with `LoneWolf` (+2), 17 with `Furtive` (+3), 17 with `Corrupt` (+2) and 1 with `Suspicious` (+1).
- `homeRegion` is `null` only on faction organizations: the `<Council>Special` templates (0–7 per save), and in Resist also `AppeaseWinner`, `SubmitWinner` and `SubmitAdministration`. All of them were held, at tier 3. Every other organization's `homeRegion` resolved to a region.

Observed on 2026-10-19 in eight private complete saves of two campaigns (structure, counts and game identifiers only), read by the narrative-layer atomic events:

- `templateName` of `TIFactionState` names the faction's council: `ResistCouncil`, `DestroyCouncil`, `ExploitCouncil`, `SubmitCouncil`, `AppeaseCouncil`, `CooperateCouncil`, `EscapeCouncil` and `AlienCouncil`, one faction each in every save (8 factions). The analyzers name a faction `alien` when its template is `AlienCouncil` and `human` otherwise (`faction_kinds`).
- `hullName` of every design (78–405 per save) is a string game identifier, 14–26 distinct per save; the alien faction's hulls are prefixed `Alien` (`AlienGunship`, `AlienFrigate`, ...), the councils' are not (`Escort`, `Corvette`, `Titan`, ...). In three intervals every ship present in one save only (0–71 per interval) resolved its hull through its fleet's faction.
- `finishedProjectNames` is a list of project-name strings (57–1,223 per save). A name may repeat: one faction of the older campaign listed `Project_ManagementResearch` 48 times in the earliest save and 64 times in the latest, growing between saves. *Hypothesis:* a repeatable project is listed once per completion.

The normalizer copies `shipDesigns` as a map from `dataName` to the whole design object (`KEYED_LIST_FIELDS` in `fields.py`), so the diff compares designs by name; a list that is not made of objects with unique string `dataName` members stays raw as `unparseable` and is reported as `unexpected_field_shape` with detail `array_of_keyed_objects`. Design display names may be player-authored free text (*hypothesis*); like every save string they are never logged or documented.

### Observed reference targets

Observed on 2026-10-09 in one private complete save (the same source saves; structure only). For each reference-shaped field, the ID resolved to the state type below in every non-null case. A list field may be empty. This table records serialized shapes and targets; fields listed in the acknowledged-fields table below are not normalized.

| State type | Field | Shape | Target state type |
| --- | --- | --- | --- |
| `TIControlPoint` | `nation` | reference | `TINationState` |
| `TIControlPoint` | `faction` | reference or `null` | `TIFactionState` |
| `TIControlPoint` | `crackdownExpiration`, `defendExpiration` | `null` or componentized date object (same members as `currentDateTime`) | — |
| `TINationState` | `capital` | reference or `null` | `TIRegionState` |
| `TINationState` | `regions`, `claims` | list of references | `TIRegionState` |
| `TINationState` | `allies`, `rivals`, `wars`, `breakaways` | list of references | `TINationState` |
| `TINationState` | `breakawayParent` | reference or `null` | `TINationState` |
| `TINationState` | `federation` | reference or `null`; mirrors the federation's `members` in every nation of eight private saves (2026-10-15) | `TIFederationState` |
| `TIWarState` | `attacker`, `defender`, `originalAttacker`, `originalDefender` | reference (2026-10-15, eight private saves of two campaigns) | `TINationState` |
| `TIWarState` | `_attackingAlliance`, `_defendingAlliance` | list of references; `attacker` is always in `_attackingAlliance` and `defender` in `_defendingAlliance`, and the nations' `wars` lists hold exactly the attacking × defending pairs, both directions (2026-10-15, eight saves) | `TINationState` |
| `TIWarState` | `peaceOfferHistory[].Key` | pair-map key reference (`{}` when empty; `Value` a list of objects, copied raw; 2026-10-15) | `TINationState` |
| `TIWarState` | `cohesionGainByNation[].Key` | pair-map key reference (`Value` a number; 2026-10-15) | `TINationState` |
| `TIWarState` | `nukedRegions`, `annexedRegions` | empty list in every observed war | not observed |
| `TIFederationState` | `members` | list of references (2026-10-15, eight saves) | `TINationState` |
| `TINationState` | `originalCapital` | reference or `null` (`null` on one nation; 2026-10-14, five private saves) | `TIRegionState` |
| `TINationState` | `hostileClaims` | list of references (non-empty on 11–12 nations per save; 2026-10-14) | `TIRegionState` |
| `TINationState` | `factionUnrestAttempts[].Key` | pair-map key reference (`{}` when empty; non-empty on 8–9 nations per save, `Value` a number; 2026-10-14) | `TIFactionState` |
| `TINationState` | `controlPoints` | list of references | `TIControlPoint` |
| `TINationState`, `TIRegionState`, `TIFactionState` | `armies` | list of references; megafauna elements carry `$type` | `TIArmyState`, `TIMegafaunaArmyState` |
| `TIRegionState` | `nation` | reference | `TINationState` |
| `TIRegionState` | `alienFacility`, `alienActivity`, `xenoforming` | reference; resolves in every region of eight private saves (2026-10-15) | `TIRegionAlienFacilityState`, `TIRegionAlienActivityState`, `TIRegionXenoformingState` |
| `TIRegionState` | `leadOccupier`, `annexingArmy` | `null` in every inspected region | not observed |
| `TIRegionState` | `originalColony` | reference or `null` (set on 25 of 363 regions; observed 2026-10-14, five saves) | `TINationState` |
| `TIRegionState` | `boostFacility`, `missionControlFacility`, `spaceDefenseFacility` | reference, one per region (observed 2026-10-14, five saves) | `TILaunchFacilityState`, `TIMissionControlFacilityState`, `TISpaceDefensesFacilityState` |
| `TIMissionControlFacilityState` | `region` | reference; resolves to its owning region (observed 2026-11-06, Protectorate and Resist saves) | `TIRegionState` |
| `TIMissionControlFacilityState` | `spaceFacilityType` | string; `displayName` is the common display-name field (observed 2026-11-06, Protectorate and Resist saves) | — |
| `TIRegionState` | `alienCrashdown`, `alienLanding` | reference, one per region (observed 2026-10-14, five saves) | `TIRegionUFOCrashdownState`, `TIRegionUFOLandingState` |
| the five `TIRegion*State` alien sub-states | `region` | reference; every entry's back-reference resolves and names the region whose forward field points at it (2026-10-15, eight private saves) | `TIRegionState` |
| `TIRegionAlienActivityState` | `alienMissionsDetected[].Key` | pair-map key reference (`{}` when empty; non-empty on 94 of 363 regions in the older campaign, never in the newer; every `Value` an empty list; 2026-10-15) | `TIFactionState` |
| `TIRegionState` | `spaceFacilities` | list of three typed references (`$type`), one per facility type above, the same IDs as the three facility fields (observed 2026-10-14, five saves) | `TILaunchFacilityState`, `TIMissionControlFacilityState`, `TISpaceDefensesFacilityState` |
| `TIFactionState` | `player` | reference | `TIPlayerState` |
| `TIFactionState` | `councilors` | list of references | `TICouncilorState` |
| `TIFactionState` | `controlPoints` | list of references | `TIControlPoint` |
| `TIFactionState` | `fleets`, `habSectors` | list of references | `TISpaceFleetState`, `TISectorState` |
| `TIFactionState` | `unassignedOrgs` | list of references (observed 2026-10-14, five saves) | `TIOrgState` |
| `TIOrgState` | `assignedCouncilor` | reference or `null` | `TICouncilorState` |
| `TIOrgState` | `factionOrbit` | reference or `null` | `TIFactionState` |
| `TIOrgState` | `homeRegion` | reference | `TIRegionState` |
| `TIPlayerState` | `faction` | reference | `TIFactionState` |
| `TICouncilorState` | `faction`, `detainingFaction` | reference or `null` | `TIFactionState` |
| `TICouncilorState` | `homeRegion` | reference or `null` | `TIRegionState` |
| `TICouncilorState` | `location`, `priorLocation` | typed reference (`$type`), `priorLocation` may be `null` | `TIRegionState` **or** `TIHabState`; `TISpaceShipState` for one active councilor with a running mission (2026-10-13, `location` in 3 of 5 and `priorLocation` in 4 of 5 private saves) |
| `TICouncilorState` | `knowsIveBeenSeenBy` | list of references (non-empty on 44–48 councilors per save; 2026-10-14, five private saves) | `TIFactionState` |
| `TICouncilorState` | `assassinations[].Key` | pair-map key reference (`{}` when empty; non-empty on 3 councilors per save, `Value` a number; 2026-10-14, five private saves) | `TIFactionState` |
| `TICouncilorState` | `orgs` | list of references | `TIOrgState` |
| `TICouncilorState` | `activeMission` | reference or `null` | `TIMissionState` |
| `TIMissionState` | `councilor` | reference | `TICouncilorState` |
| `TIMissionState` | `target` | typed reference (`$type`, 2026-11-03, Protectorate and Resist saves) | `TINationState`, `TICouncilorState`, `TIRegionState`, `TIControlPoint`, `TIOrgState`, `TIHabState`, `TISpaceShipState`, a region alien state or `TIMissionControlFacilityState` |
| `TICouncilorState` | `agentForFaction`, `completedMission` | `null` in every inspected councilor | not observed |
| `TIArmyState`, `TIMegafaunaArmyState` | `currentRegion`, `homeRegion`, `priorRegion` | reference | `TIRegionState` |
| `TIArmyState`, `TIMegafaunaArmyState` | `faction` | reference | `TIFactionState` |
| `TIArmyState`, `TIMegafaunaArmyState` | `operationTarget` | `null` in every inspected army | not observed |
| `TIArmyState`, `TIMegafaunaArmyState` | `currentOperations` | empty list in every inspected army; copied raw (`normalize-raw`), element targets are not resolved | not observed |
| `TIArmyState`, `TIMegafaunaArmyState` | `destinationSeaDate`, `embarkDate` | `null` in every inspected army; the non-null shape (hypothesis: a date) is unobserved, so both are copied raw | — |
| `TISpaceFleetState` | `ships` | list of references | `TISpaceShipState` |
| `TISpaceFleetState` | `parentFleet` | reference or `null`; 14 of 31 non-null IDs were absent from the save | `TISpaceFleetState` |
| `TISpaceFleetState` | `faction` | reference | `TIFactionState` |
| `TISpaceFleetState` | `orbitState` | plain reference, typed reference, or `null` | `TIOrbitState`, `TIAdHocOrbitState` |
| `TISpaceFleetState` | `barycenter` | typed reference | `TISpaceBodyState` |
| `TISpaceFleetState` | `dockedLocation` | typed reference or `null` | `TIHabState` |
| `TISpaceFleetState` | `homeport`, `combatState` | `null` in every inspected fleet | not observed |
| `TISpaceFleetState` | `displayNameByFaction[].Key` | pair-map key reference (never empty in the sample, 7–8 pairs per fleet, `Value` a string; 2026-10-14, five private saves) | `TIFactionState` |
| `TISpaceFleetState` | `bombardmentTarget` | typed reference or `null`; non-null on one fleet in one of five saves (2026-10-14) | `TIRegionXenoformingState` (no entity domain; kept raw) |
| `TISpaceFleetState` | `currentOperations[].target` | typed reference; 1–3 operations per save, at most one per fleet (2026-10-14, five private saves) | `TISpaceFleetState`, `TIHabState`, `TIRegionXenoformingState` |
| `TISpaceShipState` | `fleet` | reference | `TISpaceFleetState` |
| `TISpaceShipState` | `officers` | list of references | `TIOfficerState` |
| `TISpaceShipState` | `storedFaction` | `null` in every inspected ship | not observed |
| `TIHabState` | `faction` | reference | `TIFactionState` |
| `TIHabState` | `orbitState`, `habSite` | reference or `null` | `TIOrbitState`, `TIHabSiteState` |
| `TIHabState` | `barycenter` | typed reference (269 of 269 in one save) | `TISpaceBodyState` |
| `TISpaceBodyState` | `barycenter` | typed reference or `null` (Sol only) | `TISpaceBodyState` |
| `TIOrbitState` | `barycenter` | typed reference, not normalized (451 bodies and 71 Lagrange points in one save) | `TISpaceBodyState`, `TILagrangePointState` |
| `TIHabState` | `sectors` | list of references | `TISectorState` |
| `TIHabState` | `dockedFleets` | list of references | `TISpaceFleetState` |
| `TIHabState` | `councilorsOnBoard` | list of references | `TICouncilorState` |
| `TIHabState` | `officersOnBoard` | list of references; one element across all habs in each save | `TIOfficerState` |
| `TIHabState` | `advisingCouncilors` | empty list in every inspected hab | not observed |
| `TIHabState` | `coreDefendExpiration` | `null` in every inspected hab | not observed |
| `TIHabState` | `districts` | `null` in every inspected hab | not observed |
| `TIHabModuleState` | `sector` | reference | `TISectorState` |
| `TIGlobalResearchState` | `techProgress[].selector`, `techProgress[].factionContributions[].Key` | reference | `TIFactionState` |
| `TIFactionState` | `HabDestructionLog[].Destroyer` | reference (never the owner itself) | `TIFactionState` |
| `TIFactionState` | `HabDestructionLog[].SpaceBody` | reference | `TISpaceBodyState` |
| `TIFactionState` | `CombatLogs[].Ships[].Key`, `CombatLogs[].HabFaction`, `CombatLogs[].winner` | pair-map key reference; reference or `null` (`HabFaction`); reference (`winner`); every one resolved in the eight saves (2026-10-16) | `TIFactionState` |
| `TIFactionState` | `Kills[].Key`, `factionAssassinations[].Key`, `factionHate[].Key` | pair-map key reference | `TIFactionState` |
| `TIFactionState` | `intelSharingFactions` | list of references | `TIFactionState` |
| `TIFactionState` | `knownAlienSites[].Key` | typed pair-map key reference (`$type` present); a few IDs absent from the save | `TIRegionState` (most), `TIHabState`, `TISpaceShipState` (one) |
| `TIFactionState` | `lostControlPoints[].Key` | pair-map key reference | `TIControlPoint` |
| `TINationState` | `lastExecutiveChange.newExecutive` | reference or `null` | `TIFactionState` |
| `TIGlobalValuesState` | `interstateWars` | list of references (1–2 per save; 2026-10-16, eight private saves) | `TIWarState` |
| `TIGlobalValuesState` | `globalMilestones.<label>` | reference (0 or 9 labels per save) | `TIFactionState` |
| `TIGlobalValuesState` | `triggeredOncePerTargetEvents.<label>[]` | list of references (102 labels per save, 38–102 of them empty) | `TIFactionState` |
| `TINotificationQueueState` | `notificationSummaryQueue[].gotoGameState` | typed reference `{$type, value}` or `null` (null on about 70% of entries; 2026-10-16, eight private saves) | `TISpaceFleetState`, `TIRegionXenoformingState`, `TICouncilorState`, `TIHabSiteState`, `TIHabState`, `TIRegionState`, `TIOrbitState`, `TIRegionAlienActivityState`, `TIArmyState`, `TIControlPoint`, `TINationState`, `TIRegionUFOCrashdownState`, `TISpaceBodyState`, `TIMegafaunaArmyState`, `TIFactionState`; also `TIGlobalResearchState` and `TIMissionPhaseState`, which have no in-save-ID domain (unresolved, not reported) |
| `TINotificationQueueState` | `notificationSummaryQueue[].newsFeedFactions`, `summaryLogFactions` | list of references (one faction in about nine of ten entries; `summaryLogFactions` equals `newsFeedFactions` or is empty) | `TIFactionState` |

The inspected `TIFactionState.resources` object had these named resource members: `Money`, `Influence`, `Operations`, `Research`, `Projects`, `Boost`, `MissionControl`, `Water`, `Volatiles`, `Metals`, `NobleMetals`, `Fissiles`, `Antimatter`, and `Exotics`. The inspected `TICouncilorState.attributes` object had `Persuasion`, `Investigation`, `Espionage`, `Command`, `Administration`, `Science`, `Security`, `Loyalty`, and `ApparentLoyalty`.

Observed on 2026-10-14 in five private complete saves of one campaign (2045-08 to 2046-10, structure only): `TIControlPoint.controlPointPriorities` is a plain JSON object (not a pair map) on every control point (383–386 per save), always with the same 20 named members: `Economy`, `Welfare`, `Environment`, `Knowledge`, `Government`, `Unity`, `Oppression`, `Funding`, `Spoils`, `Civilian_InitiateSpaceflightProgram`, `LaunchFacilities`, `MissionControl`, `Military_FoundMilitary`, `Military`, `Military_BuildArmy`, `Military_BuildNavy`, `Military_InitiateNuclearProgram`, `Military_BuildNuclearWeapons`, `Military_BuildSpaceDefenses`, `Military_BuildSTOSquadron`. Every value is a non-negative integer, most of them zero. Between consecutive saves 70–116 matched control points changed at least one weight (166–359 weights per interval; 142 distinct control points over the sequence). It is copied as a name -> weight map, so the diff reports a weight change as a `map` change naming the changed priorities. *Hypothesis:* the weights are the priorities the controlling faction sets on the nation through this control point.

### Save-carried records

Observed on 2026-10-13 in five private complete saves of one campaign (2045-08 to 2046-10, structure only); shapes and growth re-checked on 2026-10-14 across the four consecutive intervals of the same saves. These fields are dated logs or cumulative counters that no other field of the same snapshot can re-derive. Growth, per interval: `HabDestructionLog`, `milestones` and every `Kills` value list only grew (the earlier value is a strict prefix of the later one, 8 of 8 factions and 24 of 24 kill lists in every interval); `knownAlienSites` and `lostControlPoints` never lost a key; `Transactions` grew by appending for 359–448 of its per-faction labels per interval while 39–128 labels lost entries (so it is *not* append-only). Re-checked on 2026-10-19 over six consecutive pairs of both campaigns: no entry was ever rewritten (same resource, amount and date), and every dropped entry was dated at or before the earlier save's timestamp, so the lists are pruned per label, never rewritten, and an entry dated inside an interval is always present in the later save ([event sources](higher-level-event-sources.md#tifactionstatetransactions)). Only a few labels (`Objective Completed`, early council transfers) still reach back to campaign start. *Hypothesis:* a label is pruned when it is next charged, keeping a bounded recent set; the rule is not known. They are the *save-carried records* layer of [`docs/architecture.md`](../architecture.md) section 4.3: `RECORD_FIELDS` in `src/tinarrative/parsing/fields.py` lists decoded records; the other observed record-shaped fields are acknowledged below and are not decoded into `SaveSnapshot.records`.

| State type | Field | Kind | Observed shape | Reference targets |
| --- | --- | --- | --- | --- |
| `TIFactionState` | `Transactions` | `ledger` | object: label -> list of `{Resource, Amount, Date}`; 500–2.2k entries per faction; label families observed: cause strings (`Daily Income`, `Spoils`, trade, `Transfer to/from <council>`, `Effect.*`, rewards), councilor mission template names (`Coup`, `Purge`, ...), space operation names (`Found*Operation`, `Resupply*Operation`, ...), asset charges (`Ship Construction`, `Hire Councilor`, `Purchase Org`, ...) and 66 hashed numeric labels (opaque; never logged); a multi-resource charge is one entry per resource with one date; pruned per label, never rewritten (see above). Read by `LedgerAnalyzer` for an allow-list of mission, operation and asset labels | — |
| `TIFactionState` | `HabDestructionLog` | `destruction_log` | list of `{Date, Destroyer, HabType, SpaceBody}`; habs this faction lost | `Destroyer` -> `TIFactionState`, `SpaceBody` -> `TISpaceBodyState` |
| `TIFactionState` | `CombatLogs` | `combat_log` | list of `{Date, Ships, HabFaction, Attacks, winner, WasSurprising}`, one per combat the faction logged. `Date` was `null` in every entry (2026-10-16: 145–150 entries across the eight factions of each older save, none in the newer saves). `Ships` is a pair map faction -> list of `{Item1, Item2}` (ship design name, hull class identifier); one side in 21–22 entries, two in the rest. Design names can be chosen by the player: campaign content, not decoded, never logged; hull classes are decoded as counts per side. `HabFaction` was set in 55–58 entries. `Attacks` (list of `{WeaponDataName, Range_km, ArmorFacing, Angle, TargetingBonus}`, often empty) is kept raw; `WasSurprising` `Indeterminate` or `No`. Entry provenance `/CombatLogs/<index>`. Compared across saves as a multiset of whole entries: per older interval 1 removed and 1 added, then 0, 1 and 4 added, so it is mostly but not strictly append-only. The same combat may be logged by more than one faction | `Ships` keys, `HabFaction`, `winner` -> `TIFactionState` |
| `TIFactionState` | `milestones` | `name_log` | list of milestone names (3–14 per faction) | — |
| `TIFactionState` | `knownAlienSites` | `dated_references` | pair map (never empty in the sample): typed reference -> componentized date; ~600 entries total. The date of an existing key moves later between saves (46–64 keys per interval, never earlier), so it is the date the site was last updated, not first discovered | keys -> `TIRegionState`, `TIHabState`, one `TISpaceShipState`, a few absent IDs |
| `TIFactionState` | `lostControlPoints` | `dated_references` | pair map (never empty in the sample): reference -> componentized date; 465 entries total. Keys are only added; the date of an existing key occasionally moves later (0–3 per interval), so it is the date the point was last lost | keys -> `TIControlPoint` |
| `TIFactionState` | `Kills` | `reference_values` | pair map (`{}` when empty): victim faction -> list of display names of destroyed assets (ships, modules, councilors); free text, never logged | keys -> `TIFactionState` |
| `TIFactionState` | `factionAssassinations` | `reference_values` | pair map (`{}` when empty): victim faction -> count | keys -> `TIFactionState` |
| `TIFactionState` | `factionHate` | `reference_values` | pair map (never empty in the sample): faction -> AI hate scalar; the only relation metric in the save | keys -> `TIFactionState` |
| `TIFactionState` | `armiesLost` | `label_values` | object `{Human, AlienMegafauna, AlienInvader}` -> counts | — |
| `TIFactionState` | `numAtrocitiesByCause` | `label_values` | object: cause -> cumulative count | — |
| `TIFactionState` | `objectiveNames` | `label_values` | object: objective name -> `Locked` / `Unlocked` / `Completed`; the same 59 keys on every faction in the latest save | — |
| `TIFactionState` | `boostAccounts` | `dated_labels` | object `{Base, Station, Probe, Org}` -> componentized date or `null` | — |
| `TIFactionState` | `abductions`, `alienInvestigations`, `aliensRemoved`, `atrocities` | `counter` | cumulative number | — |
| `TIFactionState` | `intelSharingFactions` | `reference_list` | list of references (empty or one in the sample) | `TIFactionState` |
| `TINationState` | `dateOfNewGovernment` | `date` | componentized date or `null`; set on 43 of 295 nations | — |
| `TIRegionUFOCrashdownState` | `crashdownTime` | `date` | componentized date or `null` (2026-10-15, eight private saves); non-null exactly when `crashdownPresent` is true (15 of 363 regions in the older campaign, 1 in the newer); never changed within a campaign | — |
| `TIWarState` | `startDate`, `dateOfLastFighting` | `date` | componentized date (2026-10-15, eight private saves); a war that appeared in an interval had its `startDate` inside it; `dateOfLastFighting` moved later in both newer intervals | — |
| `TIGlobalValuesState` | `globalMilestones` | `labelled_references` | object: milestone template name -> faction reference (`{}` early in the newer campaign, 9 labels in every older save); entry provenance `/globalMilestones/<label>` | `TIFactionState` |
| `TIGlobalValuesState` | `triggeredOncePerTargetEvents` | `labelled_references` | object: narrative-event name -> list of faction references | `TIFactionState` |
| `TIGlobalValuesState` | `triggeredOncePerCampaignEvents` | `name_log` | list of narrative-event names | — |
| `TINotificationQueueState` | `notificationSummaryQueue` | `notification_log` | list of entries `{templateName, itemSummary, dateTimeString, dateTime, outcome, gotoGameState, alienRelated, timerFactions, newsFeedFactions, summaryLogFactions, iconResource, iconBackgroundResource, backgroundColor}`, some also with a JSON.NET `$id`. Decoded: template, componentized `dateTime`, `itemSummary` (localized free text naming councilors, fleets, habs and nations: campaign content, never logged, never in a fixture), `outcome` (`None`, `Success`, `CriticalSuccess`, `Aborted` seen), `gotoGameState`, `alienRelated` and the two faction lists. `dateTimeString`, `timerFactions` (empty in every entry), the icon and colour members and `$id` are known and not decoded. Entry provenance `/notificationSummaryQueue/<index>`. Compared across saves as a multiset keyed by (template, date, summary): the game rewrote `gotoGameState` of kept entries (to `null` or to another entity) in 3, 10 and 10 entries of three older intervals, so the subject is not part of the identity. Retention (older sample, sizes 771, 732, 733, 737, 691): the oldest entry was five years before the save date in every save, but 79, 19, 69 and 126 entries disappeared per interval, many newer than the oldest kept, so pruning is not only by age; 4–6 exact duplicates per save. *Hypothesis:* the single faction named by most entries is the player's, so the log is player-centric. It is a supplement to the snapshot evidence, not a complete history | `gotoGameState`, faction lists (see above) |
| `TINationState` | `lastExecutiveChange` | `executive_change` | object `{newExecutive, date, cause}`; `newExecutive` and `date` may be `null`; causes seen: `None`, `Politics`, `Independence`, `Coup`, `RegimeChange`, `Enthrall` | `newExecutive` -> `TIFactionState` |

*Hypothesis:* `knownAlienSites` keys whose ID is absent from the save are sites on bodies or habs that no longer exist; not checked.

### Witnesses across a reload

Observed on 2026-10-29 in 22 private saves archived while playing ([save directory](save-directory.md)): autosaves,
manual, combat and exit saves. They form two lines of the Protectorate campaign (15 saves, forked by a reload at
2028-06) and two of the Resist campaign (7 saves, forked at 2046-02). The player's notes give the true tree. A rule
was tested on every pair of saves A and B of one campaign, A no later than B. That is 87 pairs where B continues A
and 39 pairs on different lines. The *witness set* is the set of rules that no continuing pair broke. Each rule
below states what contradicts "B continues A":

| Witness | Contradiction | Continuing pairs broken | Cross-line pairs contradicted |
| --- | --- | --- | --- |
| `Transactions` | an entry of B dated *strictly before* A's game time is missing from A's list for the same label (entries compared by resource, amount and date, as a multiset) | 0 of 87 | 39 of 39 (8–3,998 entries) |
| entity IDs | an entity of B with an ID at or below A's `currentID` is missing from A, or has another state type in A | 0 of 87 | 39 of 39 (3–66 missing), 35 of 39 (1–38 retyped) |
| `lostControlPoints` | a key of A is missing from B, or B has a new key dated before A's game time | 0 of 87 | 33 of 39 |
| `knownAlienSites` | a key of A is missing from B | 0 of 87 | 22 of 39 |
| `milestones`, `Kills` | A's list is not a prefix of B's | 0 of 87 | 4 of 39 |
| `HabDestructionLog` | A's list is not a prefix of B's | 0 of 87 | 0 of 39 |

The ID rule follows from the observed allocation: one counter, and no ID is ever reused
([entity identity](entity-identity.md)). Compare state types only: display names change along one line. Every
cross-line pair was contradicted by the ledger and the ID rule together. The earliest fork pair (a combat save 10
game-days after the loaded save) was contradicted *only* by those two. The prefix logs are too sparse to find a
young fork, so a witness test that reads only them reports `consistent` for it.

Rules that failed along one line, so they are **not** witnesses:

- `Transactions` with entries dated *at or before* A's game time: broken in 58 of the 87 continuing pairs. An
  autosave is written before the charges dated at its own moment. A manual save taken right after the autosave, at
  the same game time, had 25 more entries dated exactly at that moment. This is also why an autosave and an exit
  save of the same game time differ.
- `knownAlienSites` with a new key dated before A's game time: broken in 20 pairs. A site reappeared in a later
  save with a date years before the earlier save, so the date is not a discovery date.
- `CombatLogs` as a prefix log: broken in 6 pairs. After a battle the list had the same length but different
  content, so entries are rewritten or rotated.

With the witness set above, the parent rule of the lines design (the nearest earlier save B continues) rebuilt the
true tree of both campaigns: the loaded save had two children, and every save of each attempt had its predecessor
on that attempt as parent.

## Implementation guidance

The table gives a direct first-pass mapping to `SaveSnapshot`:

```text
TITimeState           -> date, timestamp, turn-like campaign-day metadata
TIFactionState        -> factions
TINationState         -> nations
TIRegionState         -> regions
TIArmyState +
TIMegafaunaArmyState  -> armies
TICouncilorState      -> councilors
TIOrgState            -> organizations
TISpaceFleetState     -> fleets
TISpaceShipState      -> ships
TIHabState            -> habs (domain: space object)
TISpaceBodyState      -> space_bodies (domain: space body)
TIGlobalResearchState -> research (singleton) + technologies (name-keyed)
TIGlobalValuesState   -> global_values (singleton as one in-save-ID entity)
TINotificationQueueState -> notification_queue (singleton; owns the notification log record)
```

Use the state type and numeric map ID as the factual provenance key, for example `TINationState:123`. Save the original state type, map ID, and source path with every normalized object. Field-level domain code should resolve reference IDs through the target state map and report an unresolved reference as unknown rather than guessing a target.

`src/tinarrative/parsing/fields.py` defines the fields copied into normalized entities (plus common entity metadata), resolves references only when their observed target type has an entity domain and the ID exists in the same save, copies `shipDesigns` as a map keyed by `dataName`, and records each object's state type, map ID, and `/gamestates/<type>/<index>/Value` path. A field observed to point at more than one domain (councilor `location`) resolves against the set of observed domains; the owning state type decides the resulting domain. The nation pair maps in `PAIR_MAP_FIELDS` are copied by key. Fields listed as acknowledged below are omitted from snapshots and diffs. The fields of the "Save-carried records" table are decoded by `src/tinarrative/parsing/records.py` into `SaveSnapshot.records` with a `/gamestates/<type>/<index>/Value/<field>` path per set, using the field-level pair-map decoder of [containers and references](containers-and-references.md#field-level-dictionaries) and the same reference resolution.

Every `Value` object also carries the serializer members `$type`, `ID`, `finderSortOverride` and `gameStateSubjectCreated` (`SERIALIZATION_FIELDS`); they are known and never normalized. The following observed fields are deliberately not copied; `ACKNOWLEDGED_FIELDS` in `fields.py` lists them with the same `UnsupportedReason`, so the unknowns scan does not report them. The reasons: `vector` (spatial or physics values, including orbital elements and epochs), `reference_graph` (JSON.NET `$id`/`$ref` graphs), `derived_history` (rolling windows and running histories derivable from the snapshot), `derived_cache` (values recomputable from other fields of the same snapshot), `stale_references` (lists pointing mostly at absent IDs), `ai_internal` (AI planning scratch), `ui_cache` (presentation assets, display strings, player preferences and order settings) and `runtime_internal` (engine plumbing and state or record fields with no current analyzer consumer). Decided on 2026-10-13 against five private saves of one campaign (structure only); the per-field reasoning is in the triage record beside the [unknowns registry](unknowns/README.md). Every `TIHabModuleState` field is likewise left raw, because that type is not normalized at all.

| State type | Reason | Fields |
| --- | --- | --- |
| `TIFactionState` | `derived_history` (`highestIntel` is the running maximum of the normalized `intel`) | `LocalTransferDVLog`, `SolarTransferDVLog`, `highestIntel`, `history_CPCapOverageByDay`, `history_MCCapOverageByDay` |
| `TIFactionState` | `derived_cache` | `PassiveTechSlot`, `activeProjectTriggers`, `availableCouncilors`, `availableOrgs`, `availableProjectNames`, `baseIncomes_year`, `cachedSTOFighterMinimumBoost`, `cachedYearlyRevenue`, `councilorsGenerated`, `factionFleetsEncountered`, `fleetWetMassDuringHighestShipMaintainence`, `globalResearchPurse`, `habProjectSlotUnlocked`, `hiddenProjects`, `highestRecordedExpenditurePerDay`, `lastMonthsSpoils`, `lastWeeksSpoils`, `missionControlUsage`, `nextRefitNumber`, `obsoleteShipDesigns`, `obsoletedShipParts`, `orgProjectSlotUnlocked`, `savedHabDesigns`, `shipDesignCount`, `shipRefitDesignNames`, `shipRefitDesigns`, `techRaceSlot`, `thisMonthsCumulativeSpoils`, `thisWeeksCumulativeSpoils`, `turnedCouncilors` |
| `TIFactionState` | `ai_internal` (`internalCouncilorSuspicion` and `lastRecordedLoyalty` keys were mostly absent from the save) | `AIReviewProjects`, `AISavingTarget`, `aiValues`, `alienProxyNeedsHelp`, `assessedAlienHateOfMe`, `crazyIvan`, `currentRiskAversion`, `desiredShipClass`, `desiredStaticFleetFraction`, `factionEarlyToDoList`, `factionLateToDoList`, `favoredProjects`, `focusGoal`, `habDesigns`, `highestSpaceStrengthSinceLastAlienKnockdown`, `ignoreContacts`, `ignoreInterstateDiplomacy`, `initialAINationGoals`, `internalCouncilorSuspicion`, `lastRecordedLoyalty`, `lastTechRaceDate`, `lastUnaffordableShipShipyard`, `longtermTechTarget`, `majorCPTrouble`, `minorCPTrouble`, `missedProjects`, `mostPowerfulHumanEnemy`, `perceivedEnemyFleetStrengthFactors`, `permaAbandonedNations`, `plannedPolicies`, `primaryHab`, `resourceIncomeDeficiencies`, `selfAssessement`, `thisTurnsReveralScore`, `updateHabPlanningFlag`, `updateShipDesignsFlag` |
| `TIFactionState` | `ui_cache` | `alarms`, `alertSpaceTimerNotifications`, `checkNotificationOverrides`, `customPresets`, `defaultFleetArrivalAlert`, `defaultFleetArrivalAlert_Earth`, `defaultFleetArrivalAlienModifier`, `defaultFleetArrivalAlienModifier_Earth`, `defaultHullAppearanceIndex`, `defaultPriorityPresetTemplateName`, `lastDateOfFixedAlienHate`, `lastTimeSecretsWereSeen`, `mapColorationStyle`, `newAvailableCouncilors`, `newAvailableOrgs`, `notificationOverrides`, `showAlerts`, `showMonthlyIncomesInTopBarAndIntel`, `showObsoleteParts`, `showRegularNotifications`, `showSummaryLogs`, `showTimerNotifications` |
| `TIFactionState` | `runtime_internal` (`AlienControlPointGiftHistory`: whether a control point transfer was a gift is engine-side knowledge, not narrated) | `AlienControlPointGiftHistory`, `LastObjectiveProjectCompletionDate`, `dailyResourceTransfers`, `factionOperationCompleteName`, `nShipyardQueues`, `specialRegionAdjacencies` |
| `TINationState` | `derived_history` (each `history*` array holds 32 daily samples, newest first, frozen on placeholder nations) | `historyBoost`, `historyCohesion`, `historyCohesionRestState`, `historyDemocracy`, `historyEducation`, `historyGDP`, `historyInequality`, `historyInvestmentPoints`, `historyMiltech`, `historyMissionControl`, `historyNukes`, `historyNumRegions`, `historyPopulation`, `historyPublicOpinion`, `historyResearch`, `historySpaceFunding`, `historySustainability`, `historyUnrest`, `historyUnrestRestState`, `historyWarStatus`, `tracker_CohesionChangeReason_CurrentTrackingPeriod`, `tracker_CohesionChangeReason_PriorTrackingPeriod`, `tracker_Cohesion_ByQuarter`, `tracker_DemocracyChangeReason_CurrentTrackingPeriod`, `tracker_DemocracyChangeReason_PriorTrackingPeriod`, `tracker_Democracy_ByQuarter`, `tracker_EducationChangeReason_CurrentTrackingPeriod`, `tracker_EducationChangeReason_PriorTrackingPeriod`, `tracker_Education_ByQuarter`, `tracker_GDPChangeReason_CurrentTrackingPeriod`, `tracker_GDPChangeReason_PriorTrackingPeriod`, `tracker_GDP_ByQuarter`, `tracker_InequalityChangeReason_CurrentTrackingPeriod`, `tracker_InequalityChangeReason_PriorTrackingPeriod`, `tracker_Inequality_ByQuarter`, `tracker_UnrestChangeReason_CurrentTrackingPeriod`, `tracker_UnrestChangeReason_PriorTrackingPeriod`, `tracker_Unrest_ByQuarter` |
| `TINationState` | `derived_cache` | `StartOfTurnNativeControlPoints`, `_accumulatedInvestmentPoints`, `baseInvestmentPoints_month`, `cohesionRestState_dailyCache`, `directInvestmentedIPsThisYear`, `economyScore`, `maxMilitaryTechLevel`, `missionDifficultyEconomyScore`, `numControlPoints_unclamped`, `numCoreEconomicRegions_dailyCache`, `numMiningRegions_dailyCache`, `numOilRegions_dailyCache`, `priorityEffectPopScaling`, `restofFederationECOBonus_dailyCache`, `unrestRestState_dailyCache` |
| `TINationState` | `ui_cache` | `adjacentNations` |
| `TINationState` | `runtime_internal` | `accumulatedLegitimizeClaimTriggers`, `canAccumulateCoreEconomyTriggers`, `canAccumulateCoreMiningTriggers`, `canAccumulateCoreOilTriggers`, `canAccumulateDecolonizeTriggers`, `canAccumulateDecontaminateTriggers`, `canAccumulateLegitimizeClaimTriggers`, `canBuildSTOSquadrons`, `canBuildSpaceDefenses`, `canDecontaminate`, `improveRelationsCooldowns`, `improveRelationsDeclinedUnderCurrentExecutivePair`, `oldRivalsCount`, `rivalryCooldowns` |
| `TIControlPoint` | `derived_cache` | `numPrioritiesWithWeight`, `totalWeightsForControlPoint` |
| `TIRegionState` | `runtime_internal` | `STOFighterCooldownExpiry`, `accumulatedCoreEconomyRegionTriggers`, `accumulatedCoreMiningRegionTriggers`, `accumulatedCoreOilRegionTriggers`, `accumulatedDecolonizeTriggers`, `accumulatedDecontaminateTriggers`, `annualPopGrowthModifier` |
| `TICouncilorState` | `ai_internal` | `autofailMissionsValue` |
| `TICouncilorState` | `ui_cache` | `appearanceTemplateName`, `everBeenAvailable`, `familyName`, `learnedMissionsTemplateNames`, `locationIllustration`, `missionsExcludedFromDefenseMode`, `permanentAssignment`, `permanentDefenseMode`, `personalName`, `repeatOrder`, `voiceTemplateName` |
| `TICouncilorState` | `runtime_internal` | `imBeingTargeted`, `possibleFaction`, `preMissionPhaseLocation`, `priorMissionTarget`, `targetedLastTurn` |
| `TIArmyState`, `TIMegafaunaArmyState` | `derived_cache` | `controlPointIdx` |
| `TIArmyState`, `TIMegafaunaArmyState` | `ai_internal` | `AI_targetEnemyRegion` |
| `TIArmyState`, `TIMegafaunaArmyState` | `ui_cache` | `displayNameWithArticle` |
| `TIArmyState`, `TIMegafaunaArmyState` | `runtime_internal` | `armyDamageEventName`, `armyOperationCompleteEventName`, `armyStatusUpdateEventName`, `createdFromTemplate` |
| `TISpaceFleetState` | `vector` | `_epoch_JYears`, `_fleetTrajectoryData`, `_meanAnomalyAtEpoch_Rad`, `_rnd_rotationOffset_Deg`, `bombardmentAltitude_km`, `dockOffset`, `epoch_DateTime`, `firstHitFromBombardmentRun` |
| `TISpaceFleetState` | `derived_history` | `Logs` |
| `TISpaceFleetState` | `stale_references` | `unreachableLocations` |
| `TISpaceFleetState` | `ai_internal` | `AI_FailedAttackEnemyStrength` |
| `TISpaceFleetState` | `ui_cache` | `alwaysShowOrbitTrailDuringTransfer`, `formation`, `savedFormation` |
| `TISpaceFleetState` | `runtime_internal` | `campaignStartLocation`, `delayedTransferAbortNotification`, `dummyFleet`, `fleetOperationCompleteName`, `officerTransferPlan`, `propellantSharingPlan`, `proposedTrajectories`, `returnToOperationsTime`, `waitingToInitiateCombatDatas` |
| `TISpaceShipState` | `vector` (`damagePoints` is `{w, x, y, z}`, not hit points) | `currentFleetOffset`, `currentRotation`, `damagePoints`, `fleetFormationOffset` |
| `TISpaceShipState` | `reference_graph` (`$id`/`$ref` module graphs) | `ammo`, `batteryCharge`, `hullWeapons`, `noseWeapons`, `utilityModules` |
| `TISpaceShipState` | `derived_cache` | `missionControlConsumption` |
| `TISpaceShipState` | `ui_cache` | `homeRegion` |
| `TISpaceShipState` | `runtime_internal` | `accumulatedHeat_GJ`, `activeCombatManeuvers`, `angular_acceleration_rads2`, `availablePower_GJ`, `canSuicide`, `combatAIControl`, `combatManeuverTarget`, `combatPrimaryTarget`, `combatSecondCounter`, `currentHeatSinkCapacity_GJ`, `currentManeuver`, `disengageFromCombat`, `generatorWorking`, `hasDisengaged`, `isDummy`, `max_angular_velocity_rad_s`, `plannedResupplyAndRepair`, `prevPartsBeingRepaired`, `prevSystemsBeingRepaired`, `propulsionValuesDataDirty`, `radiatorsExtended`, `radiatorsExtending`, `radiatorsRetracting`, `spaceCombatValueDataDirty`, `systemsDepowered`, `thrustersActive` |
| `TIHabState` | `vector` | `_epoch_JYears`, `_meanAnomalyAtEpoch_Rad`, `_rnd_rotationOffset_Deg`, `epoch_DateTime` |
| `TIHabState` | `derived_cache` | `FarmProvidedResources` |
| `TIHabState` | `stale_references` (51 of 55 `conflictFleets` IDs were stale) | `conflictFleets` |
| `TIHabState` | `ai_internal` | `HabSchematicAssignedDate`, `habSchematic`, `habSchematicTemplateName` |
| `TIHabState` | `ui_cache` | `connStruct`, `customHabIconResource`, `ringStruct` |
| `TIHabState` | `runtime_internal` | `_dockedShipAbovePositions`, `createdFromTemplate` |
| `TIMetadataState` | `ui_cache` | `lastCompletedObjectiveArtPath`, `lastCompletedObjectiveName`, `playerFactionGradientPath`, `playerFactionIconPath` |
| `TIMetadataState` | `runtime_internal` | `alienProgressionSpeed`, `averageMonthlyEvents`, `controlPointMaintenanceFreebieBonus`, `controlPointMaintenanceFreebieBonusAI`, `customDifficulty`, `miningProductivityMultiplier`, `missionControlBonus`, `missionControlBonusAI`, `nationalIPMultiplier`, `requiredDLC`, `researchSpeedMultiplier` |
| `TIGlobalResearchState` | `runtime_internal` | `useHarshTree` |
| `TIFederationState` | `ui_cache` | `displayNameWithArticle`, `displayNameWithArticleCapitalized`, `flagResource` |
| `TIFederationState` | `runtime_internal` (`{}` in every observed federation) | `lastAttemptToLeaveDarkFederation` |
| `TIFactionState` | `derived_cache` | `resources`, `currentProjectProgress`, `researchWeights`, `intel`, `shipsBuiltInClass`, `techNameContributionHistory` |
| `TIFactionState` | `ai_internal` | `knownSpies`, `factionGoals`, `sabotagedProjects` |
| `TIFactionState` | `runtime_internal` | `habSectors`, `knowsWinCondition`, `unlockedVictoryObjective`, `defeated`, `abductions`, `alienInvestigations`, `aliensRemoved`, `armiesLost`, `atrocities`, `boostAccounts`, `factionAssassinations`, `factionHate`, `intelSharingFactions`, `knownAlienSites`, `numAtrocitiesByCause`, `objectiveNames` |
| `TIControlPoint` | `derived_cache` | `benefitsDisabled`, `controlPointPriorities` |
| `TIControlPoint` | `runtime_internal` | `defended`, `crackdownExpiration`, `defendExpiration` |
| `TIRegionState` | `derived_cache` | `adjacencies`, `spaceFacilities`, `annexationDaysLeft`, `permanentlyDecolonized` |
| `TIRegionState` | `runtime_internal` | `alienFacility`, `alienActivity`, `abductions`, `alienCrashdown`, `alienLanding`, `boostFacility`, `spaceDefenseFacility`, `originalColony`, `annexationBeginDate`, `isCounterfiring`, `colonyRegion`, `oceanType` |
| `TICouncilorState` | `runtime_internal` | `agentForFaction`, `priorLocation`, `detainedReleaseDate`, `activeMission`, `completedMission`, `ancestry`, `assassinations`, `knowsIveBeenSeenBy`, `priorMissionTemplateName`, `protectingTarget` |
| `TIMissionState` | `runtime_internal` | `missionOutcome`, `resources` |
| `TIArmyState`, `TIMegafaunaArmyState` | `runtime_internal` | `priorRegion`, `operationTarget`, `destinationQueue`, `currentOperations`, `destinationSeaDate`, `embarkDate`, `huntingXenofauna` |
| `TIMegafaunaArmyState` | `runtime_internal` | `bonusTechLevel` |
| `TISpaceFleetState` | `vector` | `trajectory`, `globalPosition` |
| `TISpaceFleetState` | `derived_cache` | `inAccelerationPhase`, `inDecelerationPhase`, `homeport`, `combatState`, `displayNameByFaction`, `currentOperations`, `huntingXenofauna`, `unavailableForOperations`, `bombardmentTargetBracketStatus`, `endBombardmentReason`, `timeOfLastFireMission` |
| `TISpaceFleetState` | `runtime_internal` | `bombardmentTarget` |
| `TISpaceShipState` | `derived_cache` | `propellant_tons`, `cruiseAcceleration_mps2`, `combatAcceleration_mps2`, `currentDeltaV_kps`, `currentMaxDeltaV_kps`, `currentMass_kg`, `armor`, `damagedParts`, `damagedSystems` |
| `TISpaceShipState` | `runtime_internal` | `launchDate`, `officers`, `storedFaction`, `isDamageControlSuspended` |
| `TIWarState` | `runtime_internal` | `originalAttacker`, `originalDefender`, `nukedRegions`, `annexedRegions`, `defensiveNukes`, `peaceOfferHistory`, `cohesionGainByNation` |
| `TIFederationState` | `ui_cache` | `adjective` |
| `TIOrgState` | `derived_cache` | `applyingBonuses`, `takeoverDefense`, `XPModifier`, `projectCapacityGranted`, `costMoney`, `costInfluence`, `costOps`, `costBoost`, `incomeBoost_month`, `incomeMissionControl`, `persuasion`, `knowledgeBonus`, `militaryBonus` |
| `TIHabState` | `derived_cache` | `sectors`, `districts`, `councilorsOnBoard`, `officersOnBoard`, `advisingCouncilors`, `staticHab`, `inEarthLEO`, `globalPosition` |
| `TIHabState` | `runtime_internal` | `habSite`, `coreDefended`, `coreDefendExpiration` |
| `TIRegionUFOLandingState` | `runtime_internal` | `deployingArmy`, `supportingArmyBuildup`, `currentHP` |
| `TIRegionAlienFacilityState` | `runtime_internal` | `currentHP` |
| `TIRegionAlienActivityState` | `runtime_internal` | `alienMissionsDetected` |
| `TIGlobalValuesState` | `derived_cache` | `alienInvaderArmies`, `endOfOil`, `bestGlobalHumanMiltech`, `bestGlobalHumanEducation` |
| `TIGlobalValuesState` | `runtime_internal` | `campaignStartVersion`, `latestSaveVersion`, `realWorldCampaignStart`, `narrativeEventsOnCooldown_months`, `removedNarrativeEvents` |

Every other field observed on a normalized type or singleton that is neither in the table above, nor copied, nor a save-carried record is an open item in the [unknowns registry](unknowns/README.md); triage moves it into one of the three tables (`ENTITY_FIELDS`, `RECORD_FIELDS`, `ACKNOWLEDGED_FIELDS`). The entries remaining after the 2026-10-13 triage were tracked for normalization or record decoding; the tables above record their current disposition.

Research has no state objects. `normalization._research` keeps the five singleton fields on `ResearchState` (with the singleton's path) and derives one name-keyed `technology` state per string in `finishedTechsNames` and per `techProgress` element with a string `techTemplateName`, each with `finished` (membership in the finished list), `progress` (the raw element or unknown), and a path into the list it came from. Elements of another shape create no identity and stay visible raw on `ResearchState`.

A fleet's `parentFleet` frequently names an ID that no longer exists (merged fleets vanish, see [entity identity](entity-identity.md)). The normalizer keeps that as `Unknown(unresolved_reference, raw=<id>)`; downstream code must treat a fleet ID as valid only for its own lifetime and use ship `fleet` references for continuity.

For sequence ordering, use the componentized time state and raw-byte hash rules in [chronology and duplicate snapshots](chronology-and-deduplication.md), not a filename sort.

The more specific diff candidates are directly represented: control-point ownership and type; nation relation and statistic fields; army `currentRegion`/`strength`/`destroyed`; councilor `faction`/`status`/`location`; fleet `orbitState`/`inCombat`; ship `fleet`/`kills`; and completed research collections.

See [snapshot-diff observations](diff-observations.md) for aggregate evidence that these fields change across a real save interval and for conservative event-evidence rules.

## Hypotheses and limits

- `currentDateTime` is the best candidate for normalized chronology because it is componentized, but the project has not yet compared it against `gameTimeString` across a sequence.
- A missing entity from a later map may mean destruction, archival, a filter, or a serialization change. Diff code must preserve that ambiguity.
- `TIGlobalValuesState` carries `campaignStartVersion` and `latestSaveVersion` strings; `detect_game_version` reads `latestSaveVersion` from the raw save into `SaveSnapshot.game_version` without normalizing the field itself.
- Field names suggest domain semantics, but a field's units, lifecycle, and causal meaning require before/after validation before an analyzer labels an event.
