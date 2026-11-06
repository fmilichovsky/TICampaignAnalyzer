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

The work items derived from this page are listed under the reconstruction item in the
[roadmap](../roadmap.md).

## Summary

| Source | Normalized today? | Supports | Lifecycle observed |
| --- | --- | --- | --- |
| `TIWarState` | Yes (`war` domain) | war declared, nation joins, peace | appears with `startDate` in the interval, disappears at peace |
| `TIFederationState` | Yes (`federation` domain) | nation joins or leaves a federation | `members` grew 4 → 5 → 7 across the older sample |
| `TIGlobalValuesState` | Yes (`global values` domain) | campaign-wide firsts, interstate war list, nuclear and climate counters, narrative-event bookkeeping, serialized build version | scalars drift; `interstateWars` mirrors `TIWarState` presence |
| Five `TIRegion*State` alien substates | Yes (`region alien state` domain) | crashdowns (record-dated), landings, facilities, xenoforming levels | `xenoformingLevel` changed in 13–14 regions per older interval |
| `TIMegafaunaArmyState` | Yes (army domain) | megafauna spawn and removal | 0 or 1 per save; one removed, one added across the older intervals |
| `TIOrgState` | Yes (`organization` domain) | notable councilors, hostile takeovers | `assignedCouncilor` changed on 60–83 orgs per older interval |
| `TINotificationQueueState` | Yes (`notification queue` domain, `notificationSummaryQueue` record) | the game's own dated event log, player-centric | rolling five-year window with further pruning; subjects of kept entries rewritten |
| `TIFactionState.CombatLogs` | Yes (`CombatLogs` record) | space battles: sides, hull classes, winner | undated; grows mostly by appending |
| `TIFactionState.Transactions` | Yes (`Transactions` record, `LedgerAnalyzer`) | dated mission and operation charges per faction: corroboration and dating only | per-label pruning of entries dated at or before the earlier save; entries never rewritten |
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

Re-checked on 2026-10-15 in the same eight saves (structure and counts only): `crashdownPresent` was true exactly when
`crashdownTime` was non-null; every `alienMissionsDetected` entry was keyed by a faction reference with an empty list as
its value; the only field that changed within a campaign was `xenoformingLevel` (13–14 regions per older interval, one
per newer interval); every sub-state kept its ID and `region` across consecutive saves. The region alien analyzer emits
`region.crashdown_changed`, `region.landing_changed`, `region.alien_facility_changed` and `region.xenoforming_changed`
from these fields.

`TIMegafaunaArmyState` shares the army fields plus `bonusTechLevel`; it is already normalized into the army
domain, and the state type on the entity reference distinguishes it (`army.appeared`/`army.disappeared` carry
`megafauna = True` for it). One entry was removed in the third
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

Implemented in the `organization.*` analyzer: an `assignedCouncilor` change cites the matching councilor `orgs`
entries as corroboration, and (hypothesis, not separately verified) the holder faction's `unassignedOrgs` entry
when the organization is released or taken; list changes nothing explains stay `councilor.orgs_changed` and
`faction.unassigned_orgs_changed`.

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

Mission outcomes (observed 2026-11-05, all 15 Protectorate saves and two Resist saves): each
`LogMissionOutcome*` entry is one resolved mission, with `gotoGameState` the councilor, `outcome`, the
componentized date and an `iconResource` that differs by mission type (`councilor_missions/ICO_<mission>_off`).
The mission's display name and target region appear only in `itemSummary`, in at least two phrasings
("… completed their Advise mission in the Washington region of …", "… rolled a Success for the Investigate
Councilor mission in the …"). They cover only the last two months or so of each save (Protectorate 5–32
entries per save, Resist 14–15), although other templates reach back to the campaign start. Taking each
outcome once across all 15 Protectorate saves, three to six months apart, gave 376 distinct outcomes;
comparing the covered windows with the gaps between them, that is roughly half of all mission turns
(estimate, not counted).

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

Re-checked on 2026-10-16 against the same eight saves (structure and counts only). In 23 entries over three
older intervals, the game rewrote `gotoGameState` of an entry it kept: 14 to `null` and 9 to another entity. Template,
date and summary did not change. Some of the disappearances counted above are those rewrites, not removals. When
entries are matched by template, date and summary, 79, 19, 69 and 126 entries disappeared per interval, and every
entry that appeared was dated inside its interval. `timerFactions` was empty in every summary entry. Some
`panelSummaryQueue` `$ref` pointers do not target a summary entry's `$id` (*hypothesis:* they point into the
timer queue).

Implemented as the `notificationSummaryQueue` record (`notification_log`, owned by the `notification queue`
singleton) and the `notification.*` analyzer. Each entry that appears becomes `notification.<templateName>`,
dated by the entry. An entry that disappears becomes `notification.entry_removed` and is never called pruned. An
entry whose subject, outcome or faction lists changed becomes `notification.entry_changed`. The summary is an
event attribute and is never rendered.

## `TIFactionState.CombatLogs`

Was in `ACKNOWLEDGED_FIELDS` as `runtime_internal` until it became a record. Observed shape: a list of
`{Date, Ships, HabFaction, Attacks, winner, WasSurprising}` where `Date` was `null` in all 106 entries of
the largest list, `Ships` is a pair map faction → list of `{Item1, Item2}` (a ship design name and a hull
class identifier), `HabFaction` a faction reference or `null`, `Attacks` a list of
`{WeaponDataName, Range_km, ArmorFacing, Angle, TargetingBonus}` (empty in many entries), `winner` a
faction reference, `WasSurprising` one of `Indeterminate`, `No` (and presumably `Yes`). Sizes per faction
in the latest older save: 0–106; empty on every faction in the newer sample. Growth: 101 → 101 (contents
changed) → 102 → 106; the earlier list was a prefix of the later one in the last interval but not in the
first. It is the only per-battle record in the save and should become a save-carried record rather than an
acknowledged field, with its undated nature stated.

Re-checked on 2026-10-16 against the same eight saves (structure and counts only): 145, 145, 145, 146 and 150
entries across all factions of the older saves, none in the newer; `Date` `null` in every entry; every side
faction, `HabFaction` and `winner` resolved; no member outside the six above. Compared as a multiset of whole
entries, the older intervals had 1 removed and 1 added, then 0, 1 and 4 added.

Implemented as the `CombatLogs` record (`combat_log`, owned by each faction) and `CombatAnalyzer`
(`analyzers/space/combat.py`). Each entry that appears becomes `faction.combat_recorded`, dated by the interval
because `Date` is null (a componentized date would date it by the record). An entry that disappears becomes
`faction.combat_entry_removed` and is never called pruned. The sides are kept as hull-class counts per faction;
ship design names are not decoded. One combat logged by two factions yields two events; matching them is left to
reconstruction.

## `TIFactionState.Transactions`

Observed on 2026-10-19 on the eight private saves of two campaigns (Appease: 7 and 21 day intervals; Resist: 92,
21, 92 and 228 day intervals), structure, dates and counts only; this is the evidence step for the ledger mission records in the [roadmap](../roadmap.md).

- **Shape.** An object label -> list of `{Resource, Amount, Date}`; every faction carries it, the alien faction
  included (0-6 labels on campaign day 1, 37-88 labels and 460-2200 entries per faction two decades in). A label
  is a cause string (`Daily Income`, `Spoils`, `Flat Mission Cost`, `GainInfluence`, `Trade Credit`, `Trade
  Debit`, `Transfer to <council>` / `Transfer from <council>`, `Effect.*`, `Narrative Event`, `Project
  Completion`, `Objective Completed`, `Global Milestone`), a councilor mission template name (`Coup`, `Purge`,
  `Crackdown`, `HostileTakeover`, `Propaganda`, `Stabilize`, `Inspire`, `Unrest`, `Assassinate`, `Detain`,
  `Turn`, `Advise`, `Extract`, `Augmentation`, `SetNationalPolicy`, `DefendInterests`, `InvestigateCouncilor`,
  `StealProject`, `SabotageProject`, `SabotageFacilities`, `Abductions`, `EnthrallElites`, `TerrorizeRegion`,
  `Xenoform`, `AssaultAlienAsset`, `Contact`), an observed space operation name (`FoundColonyOperation`,
  `FoundOrbitalOperation`, `FoundOutpostOperation`, `FoundPlatformOperation`, `FoundRingOperation`,
  `FoundSettlementOperation`, `LaunchProbeOperation`, `LaunchAllProbeOperation`, `RepairFleetOperation`,
  `ResupplyOperation`, `ResupplyAndRepairOperation`, `TransferOfficersOperation`; space operation labels are
  excluded from the event allow-list), an asset charge (`Ship
  Construction`, `Hire Councilor`, `Purchase Org`, `Sell Org`, `Cancel Ship`, `Salvage`, `Scuttle`, ...) or one of
  66 hashed numeric labels. A charge that costs several resources is several entries with the same date (`Ship
  Construction` 3-6, `FoundColonyOperation` 2). No entry names a target.
- **Never rewritten, pruned per label.** Compared as (resource, amount, date) across the six consecutive pairs, no
  entry changed; the earlier "rewritten labels" reading was pruning. Of the 3443, 2004, 3522 and 3462 entries
  dropped in the Resist intervals (0 in the Appease intervals), **every one was dated at or before the earlier
  save's timestamp**, and none was dated inside the interval. So an entry dated inside `(earlier save, later
  save]` is reliably present in the later save and can be read by date from it. The pruning rule is not known
  (*hypothesis:* a label is pruned when it is next charged, keeping a bounded recent set): `Coup` entries from
  2043 survived two years and vanished when the same faction was charged for a new `Coup`; `Daily Income` kept
  about one month (122 days in the last save); `Objective Completed`, the early council transfers and a few
  singletons were still dated at campaign start.
- **Not a full history.** Because of that pruning, the ledger does *not* reach further back than the
  notification log for mission labels: in the latest Resist save, 8 of the 9 nations whose `lastExecutiveChange`
  cause is `Coup` are older than any surviving `Coup` charge.
- **Charge before effect** (the 0 to about 4 week hypothesis). For the one testable coup, the new executive's
  ledger carried a `Coup` charge 9 days before the executive record's date and no other faction's ledger had a
  `Coup` in the 28 days before it (1 of 1, unique attribution). One `Coup` charge by another faction on the last
  save day was followed by no coup-caused executive change within 400 days: a charge does not mean success.
  Countable labels agreed with visible effects in all four Resist intervals: `Ship Construction` entries dated
  inside an interval occurred exactly for the factions whose fleets gained ships; `Found*Operation` entries only
  for factions that gained a hab; `Hire Councilor` entries matched the councilors that gained a faction (1 and
  2); `Global Milestone` gained no entry while `globalMilestones` gained none.
- **Boundary.** The saves were written at midnight and charges carry the time of day, so charges made later on
  the earlier save's day fall inside the next interval when timestamps are compared (23 of the 121 events of
  the 21-day Resist interval).
- **Volume** with the allow-list of `analyzers/faction/ledger.py` (missions, operations, `Ship Construction`,
  `Hire Councilor`, `Global Milestone`): 6 and 19 events in the Appease intervals; 130, 121, 245 and 730 in the
  Resist intervals (the last over 228 days), out of 587-14194 ledger entries per later save; `Ship Construction`
  and the operations dominate because each charge is one entry per resource.

Implemented as `LedgerAnalyzer` (`analyzers/faction/ledger.py`): normalization decodes only the analyzer's shared
allow-list and records the count of other ledger entries on each `RecordSet`. Every decoded entry of the later
save dated inside the interval becomes `faction.transaction_recorded`, dated by the entry, with the ledger's
`records` change as its source; `minor`, corroboration and dating only under architecture 11.3. Income, spoils,
trade, transfers, `Effect.*`, org trades, rewards and hashed labels are counted but not decoded.

## Observations on already-normalized fields

- **Recruit pool.** In the latest older save 110 of 158 councilors had `faction = null`, and exactly those
  110 had an empty `orgs` list and no `priorMissionTemplateName`; every faction's `councilors` list held 6.
  All 52 councilors absent from the later save and all 60 present only there had `faction = null` on their
  existing side, in every older interval checked. Councilor presence changes with a null faction are the
  candidate pool, not councilor fates. Implemented as the `trivial` rule for `councilor.appeared` /
  `councilor.disappeared` in `narrative/significance.py`. Checked again on 2026-10-16 on the
  first newer interval (one week, a month into the campaign): 84 of 116 councilors had a null faction, and
  4 councilors absent from the later save had a faction, an empty `orgs` list, no `priorMissionTemplateName`
  and `status = Active`, so the rule ranks them major; that early in a campaign 31 of 32 faction councilors
  share the empty-orgs, no-mission shape, so those two fields do not identify the pool on their own.
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
  The territorial rules in `reconstruction/territorial.py` read these reasons together with the region
  events, executive causes, breakaway links and wars.
- **Releases** (observed 2026-10-18 on the two `nation.independence` intervals of the older sample, structure
  and counts only). In both, the released nation's democracy tracker moved under `DemReason_AmicableRelease`
  (+4.5 and +5.0), and the parent's trackers moved under `CohesionReason_NationReleased` and
  `UnrestReason_NationReleased`, which are reasons not listed above. The released nation also carried
  `*Reason_Independence` on cohesion, GDP and unrest, and `InqReason_Annexation`, `CohesionReason_Annexation`
  and `*RegionTransfer` deltas. So `AmicableRelease` marks the released side of a release, not a unification. In
  both cases the faction holding the parent's `Executive` control point was the same before and after the
  interval and was the released nation's new executive. In one case the released nation's previous
  `lastExecutiveChange` already had cause `Independence`, and only its date moved into the interval. On the
  parent, `breakaways` lost the released nation and a `hostileClaims` entry on the moved region was cleared. No
  `policy_*` field and no notification entry added in the interval named the release (*hypothesis:* the game
  logs it as `LogIndependence`, a template seen only in `panelSummaryQueue`).
- **Unifications** (observed 2026-11-03, the Protectorate saves up to 2028-06 and the Resist saves; four cases:
  three nations absorbed by the European Union, formerly France, in Protectorate and one by the United States in
  Resist; structure and counts only). *Published* (Terra Invicta wiki, transcribed 2026-11-03): a faction can
  unify a nation into another when it holds every control point of the absorbed nation, holds a consolidated
  executive in the absorbing nation, and the two share a federation or the absorbed nation is a breakaway of the
  absorbing one; the executive is consolidated once it has been held for 365 days.
  - *Conditions in the saves.* In all four cases, in the save before the merge, one faction held every control
    point of the absorbed nation and the absorbing nation's `Executive` point. The three Protectorate pairs shared
    a `federation`; in Resist the absorbed nation's `breakawayParent` was the absorbing nation. The absorbing
    nation's other control points do not matter: in Resist one of them was held by another faction before and
    after.
  - *Tenure is not visible.* The absorbing nation's `lastExecutiveChange` named the unifying faction in all four
    cases, but in two it was dated less than 365 days before the later save (at most 337 and 188 days), and no
    control point field dates when its controller took it. *Hypothesis:* `lastExecutiveChange` is rewritten by
    events that keep the controller, so it does not date the tenure.
  - *`LogControlConsolidated`* ("has consolidated executive control in ...") names a nation in its
    `gotoGameState`; for all 21 entries in one later Protectorate save the logging faction held every control
    point of that nation in that save. It was not checked whether the log fires on consolidation by tenure.
  - *Outcome.* Every region of the absorbed nation went to the absorbing nation in one interval. The absorbed
    nation stays in the save with an empty `regions` list (no `nation.disappeared`), `federation` `null`, and empty
    `allies`, `rivals` and `adjacentNations`. Its `Executive` control point disappears and its other points keep
    existing with `faction` `null`. One absorbed nation was renamed (United Kingdom to England) and one absorbing
    nation (France to European Union) in the interval of their merger. The absorbing nation's trackers moved under
    `*Reason_Annexation` and `*RegionTransfer`, as on every territory gain, so no tracker reason marks a
    unification. The absorbed nation's arsenal (`numNuclearWeapons`), armies and space assets moved to the
    absorbing nation in the same interval.
  - *Not unifications.* The 18 other nations that left the European Union's federation in Protectorate lost no
    region in the interval they left.

  Implemented as the unification rule of `reconstruction/territorial.py` (holder only, `executive_since` as
  context) and the `nation.merger` rule of `narrative/geopolitics.py`, which carries the merged nations' side
  effects. Of the 4 Resist cessions under the narrative rules below, the one that emptied its nation is now this
  `nation.merger`.
- **Metric shift magnitudes** (observed 2026-10-18, six private saves of the two campaigns, intervals of 7,
  21, 28, 92 and 113 days, aggregate counts only). Nations with an empty `regions` list (242 of 295 on the
  older build, 121 of 295 on the newer) changed no statistic and no `publicOpinion` share in any interval.
  When a statistic with a tracker changed, the tracker deltas summed to its change in every case but one;
  a tracker changed without its statistic on 0-5 nations per interval. `publicOpinion` maps the same 8 keys
  on every nation (`Appease`, `Cooperate`, `Destroy`, `Escape`, `Exploit`, `Resist`, `Submit`, `Undecided`)
  to shares. Routine change arrives partly in steps: `cohesion` moved 1.1 on all 174 changed nations within
  one week, dominated by `CohesionReason_Effect`, and `unrest` moves in 0.25 steps, mostly
  `UnrestReason_MovementToRestValue` (also seen: `UnrestReason_StabilizeMission`,
  `UnrestReason_OppressionPriority`). Routine magnitudes per statistic, which the thresholds in
  `analyzers/politics/nation_metrics.py` sit above: `GDP` stayed within 3.3% per interval up to 28 days and
  reached 13.9-14.6% over 92-113 days (about 4.6% a month at most), while the territory changes moved it by
  more than 100x; inequality, education and democracy (0-10 scales) moved at most 0.2 per interval, except
  one 0.43 in 21 days and one 0.6 in 92 days; `cohesion` moved up to 1.46 per interval apart from the 1.1
  step above, and 2.47 once in 28 days; `unrest` moved at most 0.5 up to 28 days, p90 0.75-1.0 and at most
  3.47 over 92-113 days; `sustainability` at most 0.31 in 113 days; `militaryTechLevel` at most 0.2 per
  interval; `spaceFunding_year` 4-17% per interval on large budgets and 2.6x once on a small one in 21 days;
  per `publicOpinion` key, the largest change of a nation had p90 0.06-0.10 per interval and reached 0.12 in
  7 days, 0.19 in 21 days and 0.43 in 113 days. With those thresholds 1-5 nation shift events remain per
  interval.
- **First presence on a body.** Of the habs appearing in the four older intervals (6, 1, 3, 6), the ones on
  a body where the owning faction had no hab in the earlier save were 0, 0, 2 and 6. `TIHabSiteState.hab`
  and `pendingHab` changed in step (1–10 sites per interval).
- **Battle outcomes.** Faction `Kills` lists grew by up to 36 names in one older interval while the
  destruction log of the opposing faction gained 9 entries and 10 habs disappeared; `armiesLost` changed
  once (`AlienMegafauna`). Ship `kills` lists changed on 2–19 ships per interval.
- **Space joins** (observed 2026-10-18, the five older and three newer private saves, structure and counts
  only; read by the space rules in `reconstruction/space.py`). A hab's `barycenter` is the body
  it is on or orbits: it equalled the hab site's `parentBody` for 196 of 196 site-based habs and the orbit's
  `barycenter` for 73 of 73 orbiting habs (latest older save). Every `HabDestructionLog` entry added in the
  three older intervals that had any (3, 2, 10 entries) matched at least one hab absent from the later save
  by owning faction (the log's owner, the hab's earlier `faction`), `HabType`/`habType` and
  `SpaceBody`/`barycenter`; 9 of the 15 had two or three such candidates, and every entry's `Date` fell
  inside its interval. One `LogHabDestroyed` notification named the vanished hab and carried the same
  `dateTime` as its destruction entry, to the millisecond. Habs appearing on a body where their faction had
  none before: 0, 0, 2, 5 in the older intervals, 0, 2 in the newer. `Kills` lists also grew under the
  owning faction's own key (three factions); what they count is not known (*hypothesis:* assets of the
  faction's own that it destroyed, or kills of unaligned targets). One faction's kills against another grew
  in an interval in which the victim lost no hab and no fleet. `LogSpaceBattleTakesPlace` subjects were
  fleets in all five observed entries. No `globalMilestones` label was added in any interval of either
  sample; the labels of the latest older save (`FirstBaseOnLuna`, `FirstBaseOnMars`, `FirstAsteroidBase`,
  `FirstMercuryBase`, `FirstKuiperBeltObjectBase`, `FirstJupiterSystemBase`, `FirstUranusSystemBase`,
  `FirstWarship`, `FirstSpaceCombatVictoryAgainstAliens`) name places or achievements, never a body ID.
- **Hab lifecycle** (observed 2026-11-03, Protectorate saves 00087–00102 and Resist saves 00079–00083, every
  consecutive pair, structure and counts only; read by `parsing/cores.py` and the `hab.established` rule in
  `reconstruction/space.py`).
  - *Core module.* A hab is created at launch, and its core module only completes long after. Every hab's
    first sector (`sectorNum` 0) holds the core in slot 0: 52 of 52 Protectorate habs and 269 of 269 Resist
    habs, exactly one core each (`templateName` ending in `Core`).
  - *A launched hab.* Of the habs that appeared with an unfinished core (64 Protectorate, 11 Resist), all had
    `anyCoreCompleted` false and a module `startBuildDate` (the arrival, when construction starts) and
    `completionDate` after the later save, up to 13 months after launch for a Mars base.
  - *Built within the interval.* 13 and 5 habs appeared with a finished core, each with its `completionDate`
    inside the interval.
  - *Completion.* `anyCoreCompleted` flipped false→true once per hab (45 and 12 times), never back, and it
    stays true while a later core upgrade is under construction. The core's `completionDate` fell inside the
    flip's interval in 38 and 12 cases.
  - *Same-interval upgrades.* All 7 exceptions had been upgraded within that interval (an outpost to a
    settlement core, or the alien equivalents). The module keeps its ID, and `priorModuleCompletionDate` (a
    componentized date; `null` on a never-upgraded core) holds the first core's completion, equal to the
    earlier save's projected date each time.
  - *Projections.* Projected dates moved in 1 of 79 pairs in which a core stayed unfinished (an alien
    station's, by three months). 2 Resist habs vanished before their core completed.
  - *Module dates.* They are .NET strings (`2029-03-17T22:42:25.6840000`), with `0001-01-01T00:00:00` meaning
    no date (habs created from a template).
  - *Milestones and notifications.* A `First*Base*` milestone entered `globalMilestones` in the interval in
    which the base's core completed, not the one in which it was launched (`FirstBaseOnMars`, Protectorate).
    `TIHabSiteState.pendingHab` stayed true after completion, so it marks no stage. `LogHabFounded`
    notifications (player faction only) carry the launch day, before the core's arrival.
- **Nuclear.** `numNuclearWeapons` went from 0 to 1 on two nations in the last older interval while
  `nuclearProgram` changed on two; `nuclearDetonations` stayed 0 everywhere.
- **Nation control** (observed 2026-10-18, the five older saves, counts only; evidence for the
  narrative layer's nation-control reconstruction). Every one of the 295 nations with control
  points has exactly one control point with `positionInNation = 0` (295 of 540 points); its
  `controlPointType` is `Executive` on 177 points and another type (`TheParty`, `Aristocracy`,
  `SecurityApparatus`, ...) on the rest. (The reading that position 0 identifies the executive
  seat is superseded by the *Executive seat* entry below.) Between consecutive saves the faction
  holding the position-0 point changed on 1, 2, 5 and 4 nations (faction to faction on 1, 2, 3 and 2); the plurality
  controller changed on 3, 2, 4 and 3; a nation went from one sole controller to another on 1, 2, 2
  and 2. Re-checked on 2026-10-19 on the same saves, reading each scope from the control points'
  own `nation` and `faction`: the executive counts reproduce (1, 2, 5, 4), the plurality
  controller changed on 3, 2, 3 and 4 nations and the sole controller (gaining or losing every
  point included) on 1, 2, 3 and 3, of which sole controller to another sole controller on 1, 2, 0
  and 0; the earlier plurality and sole-to-sole figures are superseded. `events --inferred`
  (`faction.nation_control_changed`) reports exactly these per nation and scope except
  two executive changes, one in each of the last two intervals, on nations that gained or lost a
  control point to another nation in the same interval, which the rule skips as territory: so
  executive 1, 2, 4, 3, plurality 3, 2, 3, 4, sole 1, 2, 3, 3. 23 of the 31 events were high
  (dated by an agreeing `lastExecutiveChange`), the rest medium, none low.
- **Executive seat** (observed 2026-10-20, all eight private saves of the two campaigns, counts only;
  settles the seat read by the situation report and the control rule). A nation has at most one control
  point typed `Executive`, and its position in `positionInNation` varies: of the 295 nations with control
  points, the older build has 177 with one and 118 without, in every save (the sets differ by one nation
  between two saves), and the newer build has 294 with one and 1 without, a nation whose position-0 point
  is typed `Alien`. Every nation without an `Executive` point holds no regions; the reverse does
  not hold, since 124 of the older build's and 120 of the newer build's regionless nations have one, and
  all 53 older-build nations holding regions have one. On the last save of each campaign, among nations
  with a `lastExecutiveChange` record (17 of 295 newer, 184 of 295 older), `newExecutive` names the
  `Executive` point's controller in every nation whose point is not at position 0 (10 of 10 newer, 45 of 45
  older), while the position-0 controller matches in 7 of 10 and 41 of 45. Where the `Executive` point is at
  position 0 the record matches in 7 of 7 (newer) and 8 of 22 (older). In the 117 older-build nations with a
  record and no `Executive` point it never names the position-0 controller, and in 116 of them (those
  present in the first save) the named faction held no point of the nation even in the first save. The
  records of those 117 nations and of the 14 disagreeing `Executive`-at-0 nations are all dated no later
  than the year of the campaign's first save. *Hypothesis:* the game rewrites `lastExecutiveChange` only when the
  `Executive` point changes hands, so a nation without one, or a record never touched since the start,
  keeps its initial record. So the seat is the `Executive`-typed point wherever it sits (observed); for a
  nation without one, position 0 is only a stand-in that the record does not follow.
- **Resource ledger** (observed 2026-10-18, the latest older save, structure and counts only;
  superseded by the `TIFactionState.Transactions` section above on 2026-10-19: the ledger is pruned
  per label and only a few labels still reach back to campaign start). All
  eight factions, AI factions and the alien faction included, carry a `Transactions` ledger whose
  oldest entries are dated on the campaign's first day (1606 to 2209 entries per faction, 37 to
  88 distinct labels). Labels are mission and operation identifiers (`Coup`, `Purge`, `Crackdown`,
  `Assassinate`, `Detain`, `HostileTakeover`, `Propaganda`, `Offer Alliance`, `Stabilize`, `Unrest`,
  `Ship Construction`, `FoundColonyOperation`, `Project Completion`, `Global Milestone`,
  `Daily Income`, `Sell Space Resources To Earth`, `Direct Invest`, ...), faction-council transfer
  labels, and about twenty hashed numeric labels. An entry carries a label, a resource, an amount and
  a date, never a target. *Hypotheses* (from play experience, not yet checked against effects): an
  entry is charged when a mission is assigned, zero days to about four weeks before the mission
  resolves, and a charge does not mean the mission succeeded. Both were checked on 2026-10-19 (see
  above); `LedgerAnalyzer` reads the allow-listed labels under the bounds of architecture 11.3.
- **Names and bodies** (observed 2026-10-18, the latest older save). `displayName` is a string on
  every nation, region, hab, faction and control point, and resolved references carry it as
  `EntityRef.name`. `TISpaceBodyState` is normalized as the `space body` domain, so a hab's
  or fleet's `barycenter` and a destruction entry's `SpaceBody` resolve to a named body with a parent.
- **Projects and technologies** (observed 2026-10-18, the latest older save). `finishedProjectNames`
  held 480 names on one faction and is left in the diff; `technologies` held 148 states, all
  finished, and no `technology.completed` event occurred in the four older intervals, so late in a
  campaign the project list, not the technology list, is where completions appear.
- **Narrative rules (geopolitics)** (observed 2026-10-19, the eight private saves of both campaigns
  (Resist: 92, 21, 92 and 228 day intervals; Appease: 7 and 20 day intervals), counts only, read from
  `events --inferred`; evidence for the geopolitical narrative rules and the defaults of
  `config.GeopoliticsSettings`).
  - *Takeovers.* Executive or sole `faction.nation_control_changed` with a faction as the new
    holder: 8 nation-and-faction pairs in Resist and 32 in Appease. In 5 and 9 of those pairs the
    executive and sole changes fell in the same interval. In 1 and 4 pairs they fell in
    consecutive intervals, so consolidation is seen across intervals. The Resist case straddled
    the 228-day interval. A window that measures the gap between interval dates would split it, so
    windows measure from the earliest date an event can have had (its record date, else its
    `not_before`). 2 of the Resist pairs had `Independence` as the executive cause, on the two newly
    independent nations. They are left to the release rule, which leaves 6 takeovers in Resist and
    32 in Appease. By `GDP` in the report after the anchor's interval, none of the
    38 takeovers was on a nation ranked in the top 10 and 2 (both Appease) were on one ranked 11 to 20, so the default
    threshold of 10 promotes none of the takeovers in these samples. `nation.unrest_attempts_changed` occurred 3 times in Resist and 0
    times in Appease. `Coup` / `Purge` / `Crackdown` charges dated inside an interval numbered
    1 to 23 per interval. Several factions usually carry the same label, so the single-candidate
    bound attaches a charge rarely: 2 Appease takeovers carry one.
  - *Wars.* Resist: one war was present in every save without any event of its own, so no arc is
    reported for it. One war was record-dated by `startDate`, appeared, and disappeared 257 days
    later; one annexation of the sample fell between its belligerents, on opposite sides in the
    report. Appease: one war was present throughout, and only its `dateOfLastFighting` moved
    (2 events). That is a `major` arc, like the war's presence. `nuclearStrikes` stayed at 0.
  - *Federations.* Resist: one federation with 5 member changes (4 added, 1 removed) and no
    appearance, rename or disappearance. Appease: two federations, with no events.
  - *Gains.* Resist: 7 `nation.territory_gained`, 4 without a reading. Every one of those 4 is a
    gained/lost pair with no war between the two, and every one carries `*Reason_Annexation`
    tracker causes. A transfer without a war or an annexation flag can therefore still be
    annexation-like in the game's bookkeeping, which is why a cession stays at medium confidence
    at most. Two of the 4 pairs had the same gainer in consecutive intervals. They are an expansion
    made of cessions, so the expansion rule nests cessions instead of citing their territory
    aggregates. No other gainer had two gains. A territory aggregate accompanies every
    annexation, unification and independence of its gainer, so a gain is counted once per reading.
    Appease had no territory change.
  - *Independence.* Resist: 2, both `released`. The new nation's control event fell in the same
    interval both times, and neither nation appeared (*hypothesis:* it existed before without regions).
  - *Claims.* `nation.claims_changed` occurred 0 times and `nation.hostile_claims_changed` 4 times,
    so `nation.claims_declared` is covered by synthetic tests only.
  - *Alien claims.* The alien administration (`alienNation`) holds claims on far more regions than any human
    nation, which makes its `nation.claims_changed` and `nation.claims_declared` the largest events of a
    package. *Published* (Terra Invicta game rules, transcribed 2026-10-23): the alien nation has implicit claims on
    every region, so the rules treat it separately.
  - *Transformations.* In Resist, 4 nation-intervals had 2 or more distinct statistics among
    democracy, GDP, inequality, cohesion and unrest. Three of those 4 belong to a nation with a
    release, cession or takeover in the same interval, which already carries the shifts. The
    rules built 2 standalone transformations, one of them spanning two intervals. Appease had no
    shifts of these statistics.

- **Narrative rules (space)** (observed 2026-10-20 for the template names, from the latest older save;
  the other counts are the space observations of 2026-10-18 above; evidence for the space narrative
  rules and the defaults of `config.SpaceSettings`).
  - *Space campaign.* `faction.battle_outcome` anchors one campaign per killer and victim pair. The
    older saves had few outcomes per pair, so the campaign gap (365 days) is a *hypothesis* sized to
    the longest observed save interval, not a measured distribution.
  - *Colonisation wave.* `faction.first_hab_on_body` occurred 0, 0, 2 and 5 times per interval in
    the older saves and 0 and 2 in the newer ones, so a wave of two or more needs a window longer
    than one short interval; 180 days is a *hypothesis*.
  - *First milestone.* No `Global Milestone` charge was observed alongside a milestone in the sampled
    intervals, so date narrowing is untested on real data; the rule keeps the interval date
    without one.
  - *Fleet buildup.* `ship.appeared` carries `hull` when the design resolves and now also the owner of
    the ship's fleet as its third entity. The threshold of five ships is a *hypothesis*.
  - *Technology milestones.* The latest older save held 148 finished technologies and 476 distinct
    finished project names on the factions. The tiered `MILESTONE_TEMPLATES` list
    (`narrative/milestones.py`) is interpretation, chosen by the author, not a property of the save. Its
    names were taken from the link targets of the Terra Invicta wiki's tech and project lists (archived
    copies of 2026-10-12 and 2025-09-11), which use save template names: technologies unprefixed,
    projects as `Project_<key>`, with keys that can differ from display names (`OrbitalTorusHabs` for
    Ring Habs, `Project_SlavicCommonwealth` for The Intermarium) or keep the game's spelling
    (`Project_Pan-AsianCooperative`, `Project_Helium-3Mine`).
    - *Observed* (2026-10-20, the eight private saves): of 219 listed names, 184 occur in a
      `finishedTechsNames`, `finishedProjectNames` or `finishedOneTimeOnlyProjectNames` list and 18 more
      occur elsewhere in the saves as project names. `Project_AlienMasterProject` and
      `Project_AlienAdvancedMasterProject` are finished names that the wiki's project list lacks;
      `Project_GreaterPanAsia` occurs too and is not listed.
    - *Hypothesis:* the 17 names never seen (the faction endgames other than the Servants' and
      Protectorate's, the late alien-weakness chain, some unifications, `Project_BoranePlasmajetTorch`,
      `Project_AntimatterFarm`) are spelled as the saves would carry them; none has a close match in the
      saves.

## Structures looked at and set aside

- `TIHistoricalData` (one entry, `Data`: pair map faction → object of resource-use series): graph data,
  `derived_history`.
- `FactionGoal_*` collections and `TIFactionState.factionGoals`: AI planning, per the inventory's
  interpretation boundary.
- `TIMissionState` (337 per older save, 27–30 per newer; normalized as the mission domain, not an event
  source). Not a mission history: the states referenced by a councilor's `activeMission` or `completedMission`
  sit beside states nothing in the save references (Protectorate 2030-10: 36 active, 2 completed, 54
  unreferenced of 92; Resist 2046-02 and 2046-10: 47 active, 292 and 294 unreferenced; 2026-11-05).
  *Hypothesis:* the game deletes a state when its mission resolves and the unreferenced ones are leftovers it
  never cleaned up. They accumulate without pattern: a Protectorate `GainInfluence` state from the first
  save (2026-02) survives to the last, while a councilor who chose Advise on nearly every turn keeps two.
  In Protectorate only player councilors keep leftovers; an AI councilor has its active mission at most. States persist across
  intervals (292 of 339 carried over between two consecutive Resist saves, 2026-11-03). `startTime`,
  `resolveTime` null, `missionOutcome` `None` or `Aborted`. Mission outcomes are in the notification log
  instead (`TINotificationQueueState`, above).
- `TIMissionPhaseState`, `TIPromptQueueState`, `TITimeEvent`, `TIEffectsState`: engine phase, pending
  prompts, scheduled ticks, effect tables.
- `TIOfficerState` (353–380 per older save, none in the newer): ship officers with `rank`, `maxRank`,
  `ship`/`hab` references and JSON.NET-linked dates; promotions appear in the notification queue instead.
- `TISpaceBodyState` (normalized as `space body`: name and parent; `habSites`, `nations`, `orbits` lists,
  `playerTag` string and `maxHabTier` are acknowledged only) and
  `TIHabSiteState` (`parentBody`, `hab`, `pendingHab`, `landedFleets`, daily yields, coordinates):
  reference targets and colonization corroboration only.
