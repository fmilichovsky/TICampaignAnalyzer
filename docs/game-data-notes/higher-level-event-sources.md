# Sources for higher-level events

Evidence base for the roadmap item *rule-based reconstruction of higher-level events*. It records which
serialized structures, beyond the ones the normalizer already copies, carry the facts a campaign narrative
needs (wars, federations, metric shifts with causes, notable councilors, colonization, alien activity on
Earth), and what was observed about their shape and lifecycle. It follows the rules of the
[notes README](README.md): structure, counts and dates only; template identifiers are named, player and
campaign values are not.

Observed on 2026-10-14 in eight private complete saves of two campaigns: five consecutive saves of a
long-running campaign (2045-08 to 2046-10, four intervals, an older game build) and three consecutive
saves of a campaign begun under a newer build (2026-02 to 2026-03, two intervals). "Older" and "newer"
below refer to these two samples. Nothing here is a claim about other builds.

The work items derived from this page are issues #64 to #73, listed under the reconstruction item in the
[roadmap](../roadmap.md).

## Summary

| Source | Normalized today? | Supports | Lifecycle observed |
| --- | --- | --- | --- |
| `TIWarState` | Yes (`war` domain, issue #64) | war declared, nation joins, peace | appears with `startDate` in the interval, disappears at peace |
| `TIFederationState` | Yes (`federation` domain, issue #64) | nation joins or leaves a federation | `members` grew 4 → 5 → 7 across the older sample |
| `TIGlobalValuesState` | No (singleton not read) | campaign-wide firsts, interstate war list, nuclear and climate counters, narrative-event bookkeeping, serialized build version | scalars drift; `interstateWars` mirrors `TIWarState` presence |
| Five `TIRegion*State` alien substates | No (referenced raw from the region) | crashdowns (record-dated), landings, facilities, xenoforming levels | `xenoformingLevel` changed in 13–14 regions per older interval |
| `TIMegafaunaArmyState` | Yes (army domain) | megafauna spawn and removal | 0 or 1 per save; one removed, one added across the older intervals |
| `TIOrgState` | No (organization domain declared, never filled) | notable councilors, hostile takeovers | `assignedCouncilor` changed on 60–83 orgs per older interval |
| `TINotificationQueueState` | No (singleton not read) | the game's own dated event log, player-centric | rolling five-year window with further pruning |
| `TIFactionState.CombatLogs` | Acknowledged as `runtime_internal` | space battles: sides, hull classes, winner | undated; grows mostly by appending |
| Nation `tracker_*ChangeReason_AllTime` | Yes | cause attribution for metric shifts | per-cause deltas between saves |
| Hab `barycenter` per faction | Yes | first presence on a body | 6 of 6 habs appearing in the last older interval were on a body new to their faction |

## `TIWarState`

One entry per interstate war. Fields: `attacker`, `defender`, `originalAttacker`, `originalDefender`
(nation references), `_attackingAlliance`, `_defendingAlliance` (lists of nation references),
`startDate`, `dateOfLastFighting` (componentized dates), `nukedRegions`, `annexedRegions` (lists, empty in
every observed war), `defensiveNukes` (number), `peaceOfferHistory` (`{}` or a pair map nation → list),
`cohesionGainByNation` (pair map nation → number), `displayName` (a generated war name string),
`templateName` (`null`), plus the common serializer members.

Observed: one war in the first save of each campaign. In the older sample a second war appeared in the
third interval with a `startDate` inside the interval and the nation `wars` lists of five attackers and one
defender changing in step (the existing `nation.relation_changed` events), and disappeared in the fourth
interval while `TIGlobalValuesState.interstateWars` went from two references to one and the same `wars`
pairs were removed. `peaceOfferHistory` changed in three of four older intervals; `dateOfLastFighting`
moved in both newer intervals while `attacker`/`defender` did not. *Hypothesis:* `nukedRegions` and
`annexedRegions` hold region references; `attacker`/`defender` can differ from the `original*` pair when
leadership of an alliance passes (observed once, not explained).

Re-checked on 2026-10-15 in the same eight saves (structure and set equality only): `attacker` was a member of
`_attackingAlliance` and `defender` of `_defendingAlliance` in every war; the set of nation `wars` entries equalled the
attacking × defending alliance pairs, in both directions, in every save (2 to 16 entries), with no entry outside a
war. The war analyzer relies on this to cite the `wars` entries as corroboration of a war appearing, disappearing or
gaining an alliance member; an entry that no war explains is still reported on its own.

## `TIFederationState`

Fields: `members` (list of nation references), `federationName` (string or `null`), `adjective`,
`displayName`, `displayNameWithArticle`, `displayNameWithArticleCapitalized`, `flagResource` (resource
path string), `lastAttemptToLeaveDarkFederation` (`{}` in every observed entry), `templateName` (`null`).
One federation in the older sample, two in the newer; `nation.federation` references resolve to these
entries. A federation ID was stable across all saves of its campaign. Re-checked on 2026-10-15: in every save each
federation member's `federation` named that federation, and the number of nations with a non-null `federation`
equalled the total member count (4 to 29), so the two are exact mirrors.

## `TIGlobalValuesState` (singleton)

Observed members, grouped by what they are good for. Unless stated otherwise every member was present in
both samples.

- **Interstate wars:** `interstateWars`, a list of references to `TIWarState` (counts matched the war
  entries in every save).
- **Campaign-wide firsts:** `globalMilestones`, an object milestone name → faction reference (`{}` early
  in the newer campaign, 9 named milestones in the latest older save; names are template identifiers
  such as first base on a named body, first warship, first space-combat victory against the aliens).
- **Nuclear and alien counters:** `nuclearStrikes`, `looseNukes` (numbers, 0 throughout),
  `currentNuclearExchanges` (empty list throughout), `alienInvaderArmies` (0 throughout).
- **Climate:** `earthAtmosphericCO2_ppm`, `earthAtmosphericCH4_ppm`, `earthAtmosphericN2O_ppm`,
  `stratosphericAerosols_ppm`, `globalSeaLevelAnomaly_cm` (numbers that drift every interval),
  `globalSeaLevelRise1Triggered`, `globalSeaLevelRise2Triggered`, `endOfOil` (booleans),
  `CO2SourcesRecord_ppm`, `CH4SourcesRecord_ppm`, `N2OSourcesRecord_ppm` (objects cause → number),
  `pastEarthAtmosphericCO2_ppm`, `pastEarthAtmosphericCH4_ppm`, `pastEarthAtmosphericN2O_ppm`
  (12-element lists; rolling history, `derived_history`), `initialSustainabilityMin`.
- **Human progress:** `bestGlobalHumanMiltech`; `bestGlobalHumanEducation` (newer build only).
- **Narrative-event bookkeeping:** `narrativeEvents` (object event name → weight),
  `narrativeEventsOnCooldown_months` (object event name → months), `narrativeEventsTargetSpecificCooldowns`
  (object event name → list of `{coolingState, cooldown_months}`), `removedNarrativeEvents` (list of event
  names; grew from 242 to 249 across the older sample and from 0 to 15 across the newer),
  `triggeredOncePerCampaignEvents` (list of names), `triggeredOncePerTargetEvents` (object name → list of
  faction references), `pendingNarrativeEvents` (empty list), `priorNarrativeEventData` (object name →
  list of `{priorEventTemplateName, actorState, selectedTarget, secondaryTarget, allTargetsandSeconds}`),
  `inactiveNarrativeEvents`, `altWeightConditionTriggered` (lists of names).
- **Build and settings:** `campaignStartVersion` and `latestSaveVersion` (version strings;
  `latestSaveVersion` differed from `campaignStartVersion` in the older campaign and changed between its
  fourth and fifth save, so a serialized game build *does* exist, contrary to the "not serialized" status in
  the notes README), `realWorldCampaignStart` (componentized date), `difficulty`, `startDifficulty`,
  `scenarioCustomizations` (large object, changed every interval), `resourceMarketValues` (object resource →
  price), `maxGlobalExpectedHabSiteProduction_day`, `controlPointMaintenanceFreebies`,
  `baselineUnnormalizedSpaceCombatValue`, `moddingActive`, `moddingUsedAnytime`, `tutorialMode`,
  `savedInit`, `storedRandomSeed`, `randomState`, `fixedPCGDPToRaiseBaseCPMaintenanceCostBy1`,
  `fixedPCGDPToRaiseMissionBaseDifficultyBy1`, `fixedPCGDPToReduceUnrestBy1`, `repairCPMaintenanceScaling`
  (the last four newer build only).
- **UI state:** `currentProjectSort`, `currentTechSort`, `projectSortAscend`, `projectSortShowObsolete`,
  `techSortAscend`, `fleetScreenClassShowObsolete`, `habQuickBuildToggle`, `habQuickBuildWithBoostToggle`,
  `showFinderArmies`, `showFinderCouncilors`, `showFinderFleets`, `showFinderHabs`.

*Hypothesis:* `removedNarrativeEvents` is an append-only log of fired narrative events (names only, no
dates or targets); `narrativeEventsOnCooldown_months` names events fired within their cooldown.

## Region alien substates

Five state types with exactly one entry per region (363 each), each carrying a `region` back-reference,
`templateName` equal to the region's template name and a fixed `displayName`. The region's `alienFacility`,
`alienActivity`, `xenoforming`, `alienCrashdown` and `alienLanding` fields point at them.

| State type | Fields beyond the common ones | Observed |
| --- | --- | --- |
| `TIRegionUFOCrashdownState` | `crashdownPresent` (boolean), `crashdownTime` (componentized date or `null`) | present on 15 of 363 regions (older) and 1 (newer); the time is literally carried, so a crashdown is datable without having seen the transition |
| `TIRegionUFOLandingState` | `landingPresent`, `deployingArmy`, `supportingArmyBuildup` (booleans), `currentHP` (number) | all false / 0 in every save |
| `TIRegionAlienFacilityState` | `built` (boolean), `currentHP` (number) | `built` false everywhere; `currentHP` non-zero on 3 regions with `built` false (*hypothesis:* under construction or damaged) |
| `TIRegionXenoformingState` | `xenoformingLevel` (number) | non-zero on 8 regions in the latest older save; changed in 13–14 regions per older interval, rising, falling and dropping to 0 |
| `TIRegionAlienActivityState` | `alienMissionsDetected` (pair map faction → list) | non-empty on 94 of 363 regions (older), `{}` everywhere (newer); never changed across any interval |

`TIMegafaunaArmyState` shares the army fields plus `bonusTechLevel`; it is already normalized into the army
domain, and the state type on the entity reference distinguishes it. One entry was removed in the third
older interval and a different one added in the fourth.

## `TIOrgState`

Fields: `assignedCouncilor` (councilor reference or `null`), `factionOrbit` (faction reference or `null`),
`homeRegion` (region reference), `tier` (1–3), `applyingBonuses`, `takeoverDefense`, `XPModifier`,
`projectCapacityGranted`, the costs `costMoney`, `costInfluence`, `costOps`, `costBoost`, the incomes
`incomeMoney_month`, `incomeInfluence_month`, `incomeOps_month`, `incomeBoost_month`,
`incomeResearch_month`, `incomeMissionControl`, `MCBonus`, the attribute bonuses `persuasion`,
`investigation`, `espionage`, `command`, `administration`, `science`, `security`, the priority bonuses
`economyBonus`, `welfareBonus`, `knowledgeBonus`, `governmentBonus`, `unityBonus`, `militaryBonus`,
`oppressionBonus`, `spoilsBonus`, `environmentBonus`, `miningBonus`, `spaceDevBonus`,
`spaceflightBonus`, and `orgIconPath`, `orgIconTemplateName`, `displayNameWithArticle` (presentation).
Counts: 798–813 per older save, 270–293 per newer; 12–58 added and 0–57 removed per interval. Councilor
`orgs` lists, faction `unassignedOrgs` and `TIOrgState.assignedCouncilor` describe the same ownership.

## `TINotificationQueueState` (singleton)

Members: `notificationSummaryQueue` and `timerNotificationQueue` (lists of entries), `panelSummaryQueue`
(object with the five category keys `Missions`, `CouncilorSightings`, `EarthEvents`, `SpaceEvents`,
`Bombardment`, each a list of entries or `{"$ref"}` pointers into the summary queue), `alienEvents`
(number), `firstTimeTracker` (pair map).

An entry has `templateName` (a log template identifier), `itemSummary` (localized free text with colour
markup), `dateTimeString`, `dateTime` (componentized), `outcome` (`None`, `Success`, `CriticalSuccess`,
`Aborted` observed), `gotoGameState` (typed reference or `null`; observed targets include fleets, regions,
the five alien substates, councilors, habs, hab sites, orbits, control points, nations, armies, the
megafauna army, the research singleton, a faction and the mission-phase singleton), `alienRelated`
(boolean), `timerFactions`, `newsFeedFactions`, `summaryLogFactions` (lists of faction references),
`iconResource`, `iconBackgroundResource`, `backgroundColor`, and sometimes a JSON.NET `$id`.

Template identifiers observed (older sample unless marked): `LogFleetDetected` (about three quarters of
all entries), `LogXenoformingDetected`, `LogAlienHabDetected`, `LogSpaceBattleTakesPlace`,
`LogFleetLaunchesTowardMyAsset`, `LogMissionOutcome`, `LogMissionOutcome_Uncontested`,
`LogMissionOutcome_Permanent`, `LogMissionOutcome_Spy`, `LogEnemyMissionFailure`, `LogAlienFaunaArmySpawned`,
`LogArmyArrivesInRegion`, `LogNewCouncilorTurn`, `LogInitiateOrbitalBombardment`, `LogAbductions`,
`LogTerrorize`, `LogEnthrallElites`, `LogAlienCrashdown`, `LogMyControlPointCrackedDown`,
`LogMyControlPointPurged`, `LogControlConsolidated`, `LogProjectComplete`, `LogProjectTriggered`,
`LogIPassivelyCapturedACouncilor`, `LogMyCouncilorDetained`, `LogMyCouncilorReleased`, `LogSpyLost`,
`LogMyTechStolen`, `LogHabDestroyed`, `LogOurCriticalHabModuleDestroyed`, `LogNationJoinsWar`,
`LogNarrativeEventResolution`, `AlertNarrativeEvent`; newer sample adds `LogCampaignStart`,
`LogObjectiveUnlocked`, `LogFirstFactionEncounter`, `LogTechCompleteAndNewTechSelected`. The timer queue
held `LogShipComplete`, `LogHabModuleComplete`, `LogCriticalHabModuleComplete`,
`LogFleetAvailableForOperations`, `LogOurFleetRepaired`, `LogOurFleetRefueled`, `LogCrackdownExpires`,
`LogControlPointDefenseExpires`, `LogFleetUndocked`, `LogAlarmTriggered`.

Retention, observed across the older sample (summary queue sizes 771, 732, 733, 737, 691; timer queue 60
in every save): the oldest entry was dated five years before the save date in all five saves, so the queue
is a five-year window. It is not only age-pruned: between consecutive saves 82, 19, 79 and 136 entries
disappeared, of which 51, 15, 41 and 59 were dated *later* than the oldest surviving entry. Each save held
4–6 entries identical in type, date and text. `newsFeedFactions` named a single faction in about nine of
ten entries and all eight factions in most of the rest. In the newer sample the queue grew 4 → 15 → 41 with
nothing removed. *Hypotheses:* the single faction is the player's, so the log is player-centric; the extra
pruning is a per-category cap or player dismissal; neither rule is known.

Privacy: `itemSummary` carries councilor, fleet, hab and nation names and must be treated like the `Kills`
display names: never logged, never documented, never placed in a fixture.

## `TIFactionState.CombatLogs`

Currently in `ACKNOWLEDGED_FIELDS` as `runtime_internal`. Observed shape: a list of
`{Date, Ships, HabFaction, Attacks, winner, WasSurprising}` where `Date` was `null` in all 106 entries of
the largest list, `Ships` is a pair map faction → list of `{Item1, Item2}` (a ship design name and a hull
class identifier), `HabFaction` a faction reference or `null`, `Attacks` a list of
`{WeaponDataName, Range_km, ArmorFacing, Angle, TargetingBonus}` (empty in many entries), `winner` a
faction reference, `WasSurprising` one of `Indeterminate`, `No` (and presumably `Yes`). Sizes per faction
in the latest older save: 0–106; empty on every faction in the newer sample. Growth: 101 → 101 (contents
changed) → 102 → 106; the earlier list was a prefix of the later one in the last interval but not in the
first. It is the only per-battle record in the save and should become a save-carried record rather than an
acknowledged field, with its undated nature stated.

## Observations on already-normalized fields

- **Recruit pool.** In the latest older save 110 of 158 councilors had `faction = null`, and exactly those
  110 had an empty `orgs` list and no `priorMissionTemplateName`; every faction's `councilors` list held 6.
  All 52 councilors absent from the later save and all 60 present only there had `faction = null` on their
  existing side, in every older interval checked. Councilor presence changes with a null faction are the
  candidate pool, not councilor fates.
- **Metric cause attribution.** Between saves the six `tracker_*ChangeReason_AllTime` maps change on the
  same nations as the statistics themselves, and the per-cause deltas sum to the statistic's change.
  Reason identifiers observed: `GDPReason_TerritoryChange`, `GDPReason_Independence`,
  `GDPReason_ClimateChange`, `GDPReason_PopulationChange`, `GDPReason_EconomyPriority`,
  `GDPReason_EventEffect`; `InqReason_Annexation`, `InqReason_EconomyPriority`, `InqReason_SpoilsPriority`,
  `InqReason_WelfarePriority`, `InqReason_ClimateChange`, `InqReason_EventEffects`;
  `CohesionReason_Annexation`, `CohesionReason_Independence`, `CohesionReason_UnityPriority`,
  `CohesionReason_MovementToRestValue`, `CohesionReason_Effect`; `UnrestReason_RegionTransfer`,
  `UnrestReason_Independence`, `UnrestReason_MovementToRestValue`; `EducationReason_RegionTransfer`,
  `EducationReason_UnityPriority`, `EducationReason_PopulationLoss`, `EducationReason_EventEffect`;
  `DemReason_AmicableRelease`, `DemReason_SpoilsPriority`, `DemReason_LowCohesion`,
  `DemReason_NearbyDemocracies`. Two nations changed GDP by more than two orders of magnitude within one
  interval, each with the delta under `GDPReason_TerritoryChange`, matching `region.nation_changed` events
  on their regions and `numControlPoints` changes.
- **First presence on a body.** Of the habs appearing in the four older intervals (6, 1, 3, 6), the ones on
  a body where the owning faction had no hab in the earlier save were 0, 0, 2 and 6. `TIHabSiteState.hab`
  and `pendingHab` changed in step (1–10 sites per interval).
- **Battle outcomes.** Faction `Kills` lists grew by up to 36 names in one older interval while the
  destruction log of the opposing faction gained 9 entries and 10 habs disappeared; `armiesLost` changed
  once (`AlienMegafauna`). Ship `kills` lists changed on 2–19 ships per interval.
- **Nuclear.** `numNuclearWeapons` went from 0 to 1 on two nations in the last older interval while
  `nuclearProgram` changed on two; `nuclearDetonations` stayed 0 everywhere.

## Structures looked at and set aside

- `TIHistoricalData` (one entry, `Data`: pair map faction → object of resource-use series): graph data,
  `derived_history`.
- `FactionGoal_*` collections and `TIFactionState.factionGoals`: AI planning, per the inventory's
  interpretation boundary.
- `TIMissionState` (337 per older save, 27–30 per newer): the missions currently assigned, fully replaced
  each interval; `startTime`, `resolveTime` null, `missionOutcome` `None` or `Aborted`. Current intent only.
- `TIMissionPhaseState`, `TIPromptQueueState`, `TITimeEvent`, `TIEffectsState`: engine phase, pending
  prompts, scheduled ticks, effect tables.
- `TIOfficerState` (353–380 per older save, none in the newer): ship officers with `rank`, `maxRank`,
  `ship`/`hab` references and JSON.NET-linked dates; promotions appear in the notification queue instead.
- `TISpaceBodyState` (`habSites`, `nations`, `orbits` lists, `playerTag` string, `maxHabTier`) and
  `TIHabSiteState` (`parentBody`, `hab`, `pendingHab`, `landedFleets`, daily yields, coordinates):
  reference targets and colonization corroboration only.
