# Domain field map for `terra_invicta_json_v1`

This is a field-level handoff for normalizers and analyzers described in [`docs/architecture.md`](../architecture.md). It records *serialized field names only*—not player values—from the inspected complete save. The state collections use the pair-map decoding in [Containers, identity, and references](containers-and-references.md).

## Observed facts

| Normalized domain | State type | Observed fields relevant to the architecture |
| --- | --- | --- |
| Campaign time | `TITimeState` | `daysInCampaign`, `currentQuarterSinceStart`, `currentDateTime` (`year`, `month`, `day`, `hour`, `minute`, `second`, `millisecond`), `masterMetaTemplateName`, `scenarioMetaTemplateName` (`TIME_FIELDS`) |
| Campaign metadata | `TIMetadataState` | `gameTimeString`, `playerFactionName`, `difficulty`, `playedWithMods` (`METADATA_FIELDS`); the scenario/difficulty setting strings are acknowledged as `runtime_internal`, not narratively relevant |
| Factions | `TIFactionState` | `player`, `councilors`, `knownSpies`, `fleets`, `habSectors`, `controlPoints`, `armies`, `resources`, `finishedProjectNames`, `currentProjectProgress`, `researchWeights`, `intel`, `factionGoals` |
| Nations | `TINationState` | `capital`, `regions`, `allies`, `rivals`, `claims`, `wars`, `armies`, `publicOpinion`, `GDP`, `inequality`, `education`, `democracy`, `cohesion`, `unrest`, `militaryTechLevel`, `controlPoints`, `federation`, `breakawayParent`, `breakaways` |
| Control points | `TIControlPoint` | `nation`, `faction`, `benefitsDisabled`, `defended`, `crackdownExpiration`, `defendExpiration`, `controlPointType`, `positionInNation` |
| Regions | `TIRegionState` | `nation`, `leadOccupier`, `occupations`, `populationInMillions`, `alienFacility`, `alienActivity`, `xenoforming`, `isBeingAnnexed`, `annexingArmy`, `adjacencies`, `armies`, `abductions` |
| Armies | `TIArmyState`, `TIMegafaunaArmyState` | `currentRegion`, `faction`, `homeRegion`, `priorRegion`, `strength`, `operationTarget`, `destroyed`, `armyType`, `deploymentType`, `destinationQueue`; megafauna armies add `bonusTechLevel` |
| Councilors | `TICouncilorState` | `faction`, `agentForFaction`, `location`, `priorLocation`, `homeRegion`, `detainingFaction`, `recruitDate`, `detainedReleaseDate`, `attributes`, `activeMission`, `completedMission`, `orgs`, `status`, `XP`, `typeTemplateName`, `traitTemplateNames` |
| Organizations | `TIOrgState` | `assignedCouncilor`, `factionOrbit`, `homeRegion`, `tier`, costs, monthly incomes, research/mission-control income, and attribute/priority bonuses |
| Fleets | `TISpaceFleetState` | `ships`, `trajectory`, `inAccelerationPhase`, `inDecelerationPhase`, `homeport`, `barycenter`, `combatState`, `parentFleet`, `faction`, `orbitState`, `dockedLocation`, `inCombat`, `globalPosition` |
| Ships | `TISpaceShipState` | `fleet`, `launchDate`, `lastRefitDate`, `propellant_tons`, `kills` (list of strings), `officers`, `storedFaction`, `cruiseAcceleration_mps2`, `combatAcceleration_mps2`, `currentDeltaV_kps`, `currentMaxDeltaV_kps`, `currentMass_kg`, `armor` (`Nose`/`Left`/`Right`/`Tail`, each `armorValue`, `chippedPct`, `maxArmor`), `damagedParts`, `damagedSystems`, `isDamageControlSuspended` |
| Habs | `TIHabState` | `faction`, `orbitState`, `habSite`, `barycenter`, `sectors`, `districts`, `dockedFleets`, `councilorsOnBoard`, `habType`, `tier`, `inCombat`, `underAssault`, `underBombardment`, `anyCoreCompleted`, `staticHab` |
| Hab modules | `TIHabModuleState` | `sector`, `slot`, `constructionCompleted`, `decommissioning`, `destroyed`, `powered`, `priorModuleCompleted`, `startBuildDate`, `completionDate`, `decommissionDate` (strings), `destroyedTime`, `buildCost`; not normalized |
| Research | `TIGlobalResearchState` | `finishedTechsNames`, `finishedOneTimeOnlyProjectNames`, `techProgress` (elements: `techTemplateName`, `accumulatedResearch`, `factionContributions`, `selector`), `campaignStartYear`, `endGameTechsCompletedByCategory` |
| Federation and war | `TIFederationState`, `TIWarState` | federation `members`, name/adjective fields; `TIWarState` was present but empty in this sample |

Every inspected entity in the normalized types also carried `templateName`, `displayName`, `archived`, and `exists`. Observed on 2026-10-09 in two private complete saves (structure only): every field named above for councilors, armies, fleets, ships, habs, hab modules, and research is present in every entry of its type, and the field-name sets of both saves are identical.

Further 2026-10-09 observations (structure only):

- Every `techProgress` element's `techTemplateName` also appeared in `finishedTechsNames` (3 of 3 in both saves), so a progress entry is not evidence that research is *unfinished*.
- `TISpaceShipState.damagePoints` holds `{w, x, y, z}` vectors, not hit points; actual damage is in `armor`, `damagedParts`, and `damagedSystems`.
- `TISpaceShipState.kills` is a list of strings, not references.
- Ship module objects (`hullWeapons`, `noseWeapons`, `utilityModules`, `ammo`, `batteryCharge`, `damagedParts[].module`) and fleet `trajectory.Segments` sometimes contain `$id`/`$ref` members or a `{"$id", "$content"}` wrapper. *Hypothesis:* JSON.NET reference preservation. The normalizer keeps these values raw.
- `TIHabState.orbitState` was non-null in 73 of 269 habs and `habSite` in the other 196 (counts only, not checked per entry). *Hypothesis:* exactly one of the two is set.
- Ship `templateName` is a design name shared by many ships; hab `templateName` was null in 267 of 269 habs. Neither is a secondary key.

### Observed reference targets

Observed on 2026-10-09 in one private complete save (the same source saves; structure only). For each reference-shaped field, the ID resolved to the state type below in every non-null case. A list field may be empty.

| State type | Field | Shape | Target state type |
| --- | --- | --- | --- |
| `TIControlPoint` | `nation` | reference | `TINationState` |
| `TIControlPoint` | `faction` | reference or `null` | `TIFactionState` |
| `TIControlPoint` | `crackdownExpiration`, `defendExpiration` | `null` or componentized date object (same members as `currentDateTime`) | — |
| `TINationState` | `capital` | reference or `null` | `TIRegionState` |
| `TINationState` | `regions`, `claims` | list of references | `TIRegionState` |
| `TINationState` | `allies`, `rivals`, `wars`, `breakaways` | list of references | `TINationState` |
| `TINationState` | `breakawayParent` | reference or `null` | `TINationState` |
| `TINationState` | `federation` | reference or `null` | `TIFederationState` |
| `TINationState` | `controlPoints` | list of references | `TIControlPoint` |
| `TINationState`, `TIRegionState`, `TIFactionState` | `armies` | list of references; megafauna elements carry `$type` | `TIArmyState`, `TIMegafaunaArmyState` |
| `TIRegionState` | `nation` | reference | `TINationState` |
| `TIRegionState` | `alienFacility`, `alienActivity`, `xenoforming` | reference | `TIRegionAlienFacilityState`, `TIRegionAlienActivityState`, `TIRegionXenoformingState` |
| `TIRegionState` | `leadOccupier`, `annexingArmy` | `null` in every inspected region | not observed |
| `TIFactionState` | `player` | reference | `TIPlayerState` |
| `TIFactionState` | `councilors` | list of references | `TICouncilorState` |
| `TIFactionState` | `controlPoints` | list of references | `TIControlPoint` |
| `TIFactionState` | `fleets`, `habSectors` | list of references | `TISpaceFleetState`, `TISectorState` |
| `TIPlayerState` | `faction` | reference | `TIFactionState` |
| `TICouncilorState` | `faction`, `detainingFaction` | reference or `null` | `TIFactionState` |
| `TICouncilorState` | `homeRegion` | reference or `null` | `TIRegionState` |
| `TICouncilorState` | `location`, `priorLocation` | typed reference (`$type`), `priorLocation` may be `null` | `TIRegionState` **or** `TIHabState` |
| `TICouncilorState` | `orgs` | list of references | `TIOrgState` |
| `TICouncilorState` | `activeMission` | reference or `null` | `TIMissionState` |
| `TICouncilorState` | `agentForFaction`, `completedMission` | `null` in every inspected councilor | not observed |
| `TIArmyState`, `TIMegafaunaArmyState` | `currentRegion`, `homeRegion`, `priorRegion` | reference | `TIRegionState` |
| `TIArmyState`, `TIMegafaunaArmyState` | `faction` | reference | `TIFactionState` |
| `TIArmyState`, `TIMegafaunaArmyState` | `operationTarget` | `null` in every inspected army | not observed |
| `TISpaceFleetState` | `ships` | list of references | `TISpaceShipState` |
| `TISpaceFleetState` | `parentFleet` | reference or `null`; 14 of 31 non-null IDs were absent from the save | `TISpaceFleetState` |
| `TISpaceFleetState` | `faction` | reference | `TIFactionState` |
| `TISpaceFleetState` | `orbitState` | plain reference, typed reference, or `null` | `TIOrbitState`, `TIAdHocOrbitState` |
| `TISpaceFleetState` | `barycenter` | typed reference | `TISpaceBodyState` |
| `TISpaceFleetState` | `dockedLocation` | typed reference or `null` | `TIHabState` |
| `TISpaceFleetState` | `homeport`, `combatState` | `null` in every inspected fleet | not observed |
| `TISpaceShipState` | `fleet` | reference | `TISpaceFleetState` |
| `TISpaceShipState` | `officers` | list of references | `TIOfficerState` |
| `TISpaceShipState` | `storedFaction` | `null` in every inspected ship | not observed |
| `TIHabState` | `faction` | reference | `TIFactionState` |
| `TIHabState` | `orbitState`, `habSite` | reference or `null` | `TIOrbitState`, `TIHabSiteState` |
| `TIHabState` | `barycenter` | typed reference | `TISpaceBodyState` |
| `TIHabState` | `sectors` | list of references | `TISectorState` |
| `TIHabState` | `dockedFleets` | list of references | `TISpaceFleetState` |
| `TIHabState` | `councilorsOnBoard` | list of references | `TICouncilorState` |
| `TIHabState` | `districts` | `null` in every inspected hab | not observed |
| `TIHabModuleState` | `sector` | reference | `TISectorState` |
| `TIGlobalResearchState` | `techProgress[].selector`, `techProgress[].factionContributions[].Key` | reference | `TIFactionState` |
| `TIFactionState` | `HabDestructionLog[].Destroyer` | reference (never the owner itself) | `TIFactionState` |
| `TIFactionState` | `HabDestructionLog[].SpaceBody` | reference | `TISpaceBodyState` |
| `TIFactionState` | `Kills[].Key`, `factionAssassinations[].Key`, `factionHate[].Key` | pair-map key reference | `TIFactionState` |
| `TIFactionState` | `intelSharingFactions` | list of references | `TIFactionState` |
| `TIFactionState` | `knownAlienSites[].Key` | typed pair-map key reference (`$type` present); a few IDs absent from the save | `TIRegionState` (most), `TIHabState`, `TISpaceShipState` (one) |
| `TIFactionState` | `lostControlPoints[].Key` | pair-map key reference | `TIControlPoint` |
| `TINationState` | `lastExecutiveChange.newExecutive` | reference or `null` | `TIFactionState` |

The inspected `TIFactionState.resources` object had these named resource members: `Money`, `Influence`, `Operations`, `Research`, `Projects`, `Boost`, `MissionControl`, `Water`, `Volatiles`, `Metals`, `NobleMetals`, `Fissiles`, `Antimatter`, and `Exotics`. The inspected `TICouncilorState.attributes` object had `Persuasion`, `Investigation`, `Espionage`, `Command`, `Administration`, `Science`, `Security`, `Loyalty`, and `ApparentLoyalty`.

### Save-carried records

Observed on 2026-10-13 in five private complete saves of one campaign (2045-08 to 2046-10, structure only); shapes and growth re-checked on 2026-10-14 across the four consecutive intervals of the same saves. These fields are dated logs or cumulative counters that no other field of the same snapshot can re-derive. Growth, per interval: `HabDestructionLog`, `milestones` and every `Kills` value list only grew (the earlier value is a strict prefix of the later one, 8 of 8 factions and 24 of 24 kill lists in every interval); `knownAlienSites` and `lostControlPoints` never lost a key; `Transactions` grew by appending for 359–448 of its per-faction labels per interval while 39–128 labels were rewritten (the later list shared no entry with the earlier one in three intervals, so it is *not* append-only; the oldest entries, dated at campaign start, were always kept). *Hypothesis:* some ledger labels hold a bounded recent window per label rather than the full history; the rule is not known. They are the *save-carried records* layer of [`docs/architecture.md`](../architecture.md) section 4.3: `RECORD_FIELDS` in `src/tinarrative/parsing/fields.py` lists them with a `RecordKind`, `src/tinarrative/parsing/records.py` decodes them into `SaveSnapshot.records`, and they are not copied into the entity state.

| State type | Field | Kind | Observed shape | Reference targets |
| --- | --- | --- | --- | --- |
| `TIFactionState` | `Transactions` | `ledger` | object: label -> list of `{Resource, Amount, Date}`; 500–2.2k entries per faction; labels are cause strings and mission template names plus a few hashed numeric labels (opaque; never logged); not strictly append-only (see above) | — |
| `TIFactionState` | `HabDestructionLog` | `destruction_log` | list of `{Date, Destroyer, HabType, SpaceBody}`; habs this faction lost | `Destroyer` -> `TIFactionState`, `SpaceBody` -> `TISpaceBodyState` |
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
| `TINationState` | `lastExecutiveChange` | `executive_change` | object `{newExecutive, date, cause}`; `newExecutive` and `date` may be `null`; causes seen: `None`, `Politics`, `Independence`, `Coup`, `RegimeChange`, `Enthrall` | `newExecutive` -> `TIFactionState` |

*Hypothesis:* `knownAlienSites` keys whose ID is absent from the save are sites on bodies or habs that no longer exist; not checked.

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
TIOrgState            -> organizations (not normalized yet)
TISpaceFleetState     -> fleets
TISpaceShipState      -> ships
TIHabState            -> habs (domain: space object)
TIGlobalResearchState -> research (singleton) + technologies (name-keyed)
```

Use the state type and numeric map ID as the factual provenance key, for example `TINationState:123`. Save the original state type, map ID, and source path with every normalized object. Field-level domain code should resolve reference IDs through the target state map and report an unresolved reference as unknown rather than guessing a target.

`src/tinarrative/parsing/fields.py` implements this for `TIFactionState`, `TINationState`, `TIRegionState`, `TIControlPoint`, `TICouncilorState`, `TIArmyState`, `TIMegafaunaArmyState`, `TISpaceFleetState`, `TISpaceShipState`, and `TIHabState`: it copies exactly the fields in the table above (plus the common entity metadata), resolves a reference field only when its observed target type has an entity domain and the ID exists in the same save, keeps other reference-shaped values raw, and records every object's state type, map ID, and `/gamestates/<type>/<index>/Value` path. A field observed to point at more than one domain (councilor `location`) resolves against the set of observed domains; the owning state type decides the resulting domain. The fields of the "Save-carried records" table are decoded by `src/tinarrative/parsing/records.py` into `SaveSnapshot.records` with a `/gamestates/<type>/<index>/Value/<field>` path per set, using the field-level pair-map decoder of [containers and references](containers-and-references.md#field-level-dictionaries) and the same reference resolution.

Every `Value` object also carries the serializer members `$type`, `ID`, `finderSortOverride` and `gameStateSubjectCreated` (`SERIALIZATION_FIELDS`); they are known and never normalized. The following observed fields are deliberately not copied; `ACKNOWLEDGED_FIELDS` in `fields.py` lists them with the same `UnsupportedReason`, so the unknowns scan does not report them. The reasons: `vector` (spatial or physics values, including orbital elements and epochs), `reference_graph` (JSON.NET `$id`/`$ref` graphs), `derived_history` (rolling windows and running histories derivable from the snapshot), `derived_cache` (values recomputable from other fields of the same snapshot), `stale_references` (lists pointing mostly at absent IDs), `ai_internal` (AI planning scratch), `ui_cache` (presentation assets, display strings, player preferences and order settings) and `runtime_internal` (engine plumbing: event-bus names, dirty flags, combat-simulation scratch, timers, setup flags). Decided on 2026-10-13 against five private saves of one campaign (structure only); the per-field reasoning is in the triage record beside the [unknowns registry](unknowns/README.md). Every `TIHabModuleState`/`TIOrgState` field is likewise left raw, because those types are not normalized at all.

| State type | Reason | Fields |
| --- | --- | --- |
| `TIFactionState` | `derived_history` (`highestIntel` is the running maximum of the normalized `intel`) | `LocalTransferDVLog`, `SolarTransferDVLog`, `highestIntel`, `history_CPCapOverageByDay`, `history_MCCapOverageByDay` |
| `TIFactionState` | `derived_cache` | `PassiveTechSlot`, `activeProjectTriggers`, `availableCouncilors`, `availableOrgs`, `availableProjectNames`, `baseIncomes_year`, `cachedSTOFighterMinimumBoost`, `cachedYearlyRevenue`, `councilorsGenerated`, `factionFleetsEncountered`, `fleetWetMassDuringHighestShipMaintainence`, `globalResearchPurse`, `habProjectSlotUnlocked`, `hiddenProjects`, `highestRecordedExpenditurePerDay`, `lastMonthsSpoils`, `lastWeeksSpoils`, `missionControlUsage`, `nextRefitNumber`, `obsoleteShipDesigns`, `obsoletedShipParts`, `orgProjectSlotUnlocked`, `savedHabDesigns`, `shipDesignCount`, `shipRefitDesignNames`, `shipRefitDesigns`, `techRaceSlot`, `thisMonthsCumulativeSpoils`, `thisWeeksCumulativeSpoils`, `turnedCouncilors` |
| `TIFactionState` | `ai_internal` (`internalCouncilorSuspicion` and `lastRecordedLoyalty` keys were mostly absent from the save) | `AIReviewProjects`, `AISavingTarget`, `aiValues`, `alienProxyNeedsHelp`, `assessedAlienHateOfMe`, `crazyIvan`, `currentRiskAversion`, `desiredShipClass`, `desiredStaticFleetFraction`, `factionEarlyToDoList`, `factionLateToDoList`, `favoredProjects`, `focusGoal`, `habDesigns`, `highestSpaceStrengthSinceLastAlienKnockdown`, `ignoreContacts`, `ignoreInterstateDiplomacy`, `initialAINationGoals`, `internalCouncilorSuspicion`, `lastRecordedLoyalty`, `lastTechRaceDate`, `lastUnaffordableShipShipyard`, `longtermTechTarget`, `majorCPTrouble`, `minorCPTrouble`, `missedProjects`, `mostPowerfulHumanEnemy`, `perceivedEnemyFleetStrengthFactors`, `permaAbandonedNations`, `plannedPolicies`, `primaryHab`, `resourceIncomeDeficiencies`, `selfAssessement`, `thisTurnsReveralScore`, `updateHabPlanningFlag`, `updateShipDesignsFlag` |
| `TIFactionState` | `ui_cache` | `alarms`, `alertSpaceTimerNotifications`, `checkNotificationOverrides`, `customPresets`, `defaultFleetArrivalAlert`, `defaultFleetArrivalAlert_Earth`, `defaultFleetArrivalAlienModifier`, `defaultFleetArrivalAlienModifier_Earth`, `defaultHullAppearanceIndex`, `defaultPriorityPresetTemplateName`, `lastDateOfFixedAlienHate`, `mapColorationStyle`, `notificationOverrides`, `showAlerts`, `showMonthlyIncomesInTopBarAndIntel`, `showObsoleteParts`, `showRegularNotifications`, `showSummaryLogs`, `showTimerNotifications` |
| `TIFactionState` | `runtime_internal` | `CombatLogs`, `LastObjectiveProjectCompletionDate`, `dailyResourceTransfers`, `factionOperationCompleteName`, `nShipyardQueues`, `specialRegionAdjacencies` |
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
| `TIMetadataState` | `runtime_internal` | `alienProgressionSpeed`, `averageMonthlyEvents`, `controlPointMaintenanceFreebieBonus`, `controlPointMaintenanceFreebieBonusAI`, `customDifficulty`, `miningProductivityMultiplier`, `missionControlBonus`, `missionControlBonusAI`, `nationalIPMultiplier`, `researchSpeedMultiplier` |
| `TIGlobalResearchState` | `runtime_internal` | `useHarshTree` |

Every other field observed on a normalized type or singleton that is neither in the table above, nor copied, nor a save-carried record is an open item in the [unknowns registry](unknowns/README.md); triage moves it into one of the three tables (`ENTITY_FIELDS`, `RECORD_FIELDS`, `ACKNOWLEDGED_FIELDS`). The 105 entries left after the 2026-10-13 triage were decided as *normalize* or as *save-carried records* and are tracked as GitHub issues; the 19 record fields landed on 2026-10-14 (issue #40), leaving the *normalize* entries open.

Research has no state objects. `normalization._research` keeps the five singleton fields on `ResearchState` (with the singleton's path) and derives one name-keyed `technology` state per string in `finishedTechsNames` and per `techProgress` element with a string `techTemplateName`, each with `finished` (membership in the finished list), `progress` (the raw element or unknown), and a path into the list it came from. Elements of another shape create no identity and stay visible raw on `ResearchState`.

A fleet's `parentFleet` frequently names an ID that no longer exists (merged fleets vanish, see [entity identity](entity-identity.md)). The normalizer keeps that as `Unknown(unresolved_reference, raw=<id>)`; downstream code must treat a fleet ID as valid only for its own lifetime and use ship `fleet` references for continuity.

For sequence ordering, use the componentized time state and raw-byte hash rules in [chronology and duplicate snapshots](chronology-and-deduplication.md), not a filename sort.

The more specific diff candidates are directly represented: control-point `faction`/`crackdown`/`defended`; nation relation and statistic fields; army `currentRegion`/`strength`/`destroyed`; councilor `faction`/`status`/`location`; fleet `trajectory`/`orbitState`/`inCombat`; ship `fleet`/`propellant_tons`/damage; and completed research collections.

See [snapshot-diff observations](diff-observations.md) for aggregate evidence that these fields change across a real save interval and for conservative event-evidence rules.

## Hypotheses and limits

- `currentDateTime` is the best candidate for normalized chronology because it is componentized, but the project has not yet compared it against `gameTimeString` across a sequence.
- A missing entity from a later map may mean destruction, archival, a filter, or a serialization change. Diff code must preserve that ambiguity.
- Field names suggest domain semantics, but a field's units, lifecycle, and causal meaning require before/after validation before an analyzer labels an event.
