# Domain field map for `terra_invicta_json_v1`

This is a field-level handoff for normalizers and analyzers described in [`docs/architecture.md`](../architecture.md). It records *serialized field names only*—not player values—from the inspected complete save. The state collections use the pair-map decoding in [Containers, identity, and references](containers-and-references.md).

## Observed facts

| Normalized domain | State type | Observed fields relevant to the architecture |
| --- | --- | --- |
| Campaign time | `TITimeState` | `daysInCampaign`, `currentQuarterSinceStart`, `currentDateTime` (`year`, `month`, `day`, `hour`, `minute`, `second`, `millisecond`), `masterMetaTemplateName`, `scenarioMetaTemplateName` |
| Campaign metadata | `TIMetadataState` | `gameTimeString`, `playerFactionName`, `difficulty`, `playedWithMods`, scenario/difficulty multipliers |
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

The inspected `TIFactionState.resources` object had these named resource members: `Money`, `Influence`, `Operations`, `Research`, `Projects`, `Boost`, `MissionControl`, `Water`, `Volatiles`, `Metals`, `NobleMetals`, `Fissiles`, `Antimatter`, and `Exotics`. The inspected `TICouncilorState.attributes` object had `Persuasion`, `Investigation`, `Espionage`, `Command`, `Administration`, `Science`, `Security`, `Loyalty`, and `ApparentLoyalty`.

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

`src/tinarrative/parsing/fields.py` implements this for `TIFactionState`, `TINationState`, `TIRegionState`, `TIControlPoint`, `TICouncilorState`, `TIArmyState`, `TIMegafaunaArmyState`, `TISpaceFleetState`, `TISpaceShipState`, and `TIHabState`: it copies exactly the fields in the table above (plus the common entity metadata), resolves a reference field only when its observed target type has an entity domain and the ID exists in the same save, keeps other reference-shaped values raw, and records every object's state type, map ID, and `/gamestates/<type>/<index>/Value` path. A field observed to point at more than one domain (councilor `location`) resolves against the set of observed domains; the owning state type decides the resulting domain.

Deliberately not copied: `damagePoints` (vectors), ship module graphs and `ammo`/`batteryCharge` (`$id`/`$ref`), fleet `Logs`, `AI_FailedAttackEnemyStrength`, `unreachableLocations`, hab `conflictFleets` (51 of 55 IDs were stale), and every `TIHabModuleState`/`TIOrgState` field.

Research has no state objects. `normalization._research` keeps the five singleton fields on `ResearchState` (with the singleton's path) and derives one name-keyed `technology` state per string in `finishedTechsNames` and per `techProgress` element with a string `techTemplateName`, each with `finished` (membership in the finished list), `progress` (the raw element or unknown), and a path into the list it came from. Elements of another shape create no identity and stay visible raw on `ResearchState`.

A fleet's `parentFleet` frequently names an ID that no longer exists (merged fleets vanish, see [entity identity](entity-identity.md)). The normalizer keeps that as `Unknown(unresolved_reference, raw=<id>)`; downstream code must treat a fleet ID as valid only for its own lifetime and use ship `fleet` references for continuity.

For sequence ordering, use the componentized time state and raw-byte hash rules in [chronology and duplicate snapshots](chronology-and-deduplication.md), not a filename sort.

The more specific diff candidates are directly represented: control-point `faction`/`crackdown`/`defended`; nation relation and statistic fields; army `currentRegion`/`strength`/`destroyed`; councilor `faction`/`status`/`location`; fleet `trajectory`/`orbitState`/`inCombat`; ship `fleet`/`propellant_tons`/damage; and completed research collections.

See [snapshot-diff observations](diff-observations.md) for aggregate evidence that these fields change across a real save interval and for conservative event-evidence rules.

## Hypotheses and limits

- `currentDateTime` is the best candidate for normalized chronology because it is componentized, but the project has not yet compared it against `gameTimeString` across a sequence.
- A missing entity from a later map may mean destruction, archival, a filter, or a serialization change. Diff code must preserve that ambiguity.
- Field names suggest domain semantics, but a field's units, lifecycle, and causal meaning require before/after validation before an analyzer labels an event.
