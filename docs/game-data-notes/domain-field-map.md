# Domain field map for `terra_invicta_json_v1`

This is a field-level handoff for normalizers and analyzers described in [`docs/architecture.md`](../architecture.md). It records *serialized field names only*—not player values—from the inspected complete save. The state collections use the pair-map decoding in [Containers, identity, and references](containers-and-references.md).

## Observed facts

| Normalized domain | State type | Observed fields relevant to the architecture |
| --- | --- | --- |
| Campaign time | `TITimeState` | `daysInCampaign`, `currentQuarterSinceStart`, `currentDateTime` (`year`, `month`, `day`, `hour`, `minute`, `second`, `millisecond`) |
| Campaign metadata | `TIMetadataState` | `gameTimeString`, `playerFactionName`, `difficulty`, `playedWithMods`, scenario/difficulty multipliers |
| Factions | `TIFactionState` | `player`, `councilors`, `knownSpies`, `fleets`, `habSectors`, `controlPoints`, `armies`, `resources`, `finishedProjectNames`, `currentProjectProgress`, `researchWeights`, `intel`, `factionGoals` |
| Nations | `TINationState` | `capital`, `regions`, `allies`, `rivals`, `claims`, `wars`, `armies`, `publicOpinion`, `GDP`, `inequality`, `education`, `democracy`, `cohesion`, `unrest`, `militaryTechLevel`, `controlPoints`, `federation`, `breakawayParent`, `breakaways` |
| Control points | `TIControlPoint` | `nation`, `faction`, `benefitsDisabled`, `defended`, `crackdownExpiration`, `defendExpiration`, `controlPointType`, `positionInNation` |
| Regions | `TIRegionState` | `nation`, `leadOccupier`, `occupations`, `populationInMillions`, `alienFacility`, `alienActivity`, `xenoforming`, `isBeingAnnexed`, `annexingArmy`, `adjacencies`, `armies`, `abductions` |
| Armies | `TIArmyState` | `currentRegion`, `faction`, `homeRegion`, `priorRegion`, `strength`, `operationTarget`, `destroyed`, `armyType`, `destinationQueue` |
| Councilors | `TICouncilorState` | `faction`, `agentForFaction`, `location`, `recruitDate`, `detainedReleaseDate`, `attributes`, `activeMission`, `completedMission`, `orgs`, `status`, `XP` |
| Organizations | `TIOrgState` | `assignedCouncilor`, `factionOrbit`, `homeRegion`, `tier`, costs, monthly incomes, research/mission-control income, and attribute/priority bonuses |
| Fleets | `TISpaceFleetState` | `ships`, `trajectory`, acceleration/deceleration flags, `homeport`, `barycenter`, `combatState`, `parentFleet`, `faction`, `orbitState`, `inCombat`, `globalPosition` |
| Ships | `TISpaceShipState` | acceleration, delta-v, mass, `fleet`, `launchDate`, `lastRefitDate`, `propellant_tons`, `kills`, `officers`, damage and repair fields, `storedFaction` |
| Habs and modules | `TIHabState`, `TIHabModuleState`, `TIHabSiteState` | hab `faction`, `orbitState`, `sectors`, `districts`, `habSite`, `dockedFleets`; module construction, decommissioning, power, slot/sector, destruction, and completion fields |
| Research | `TIGlobalResearchState` | `finishedTechsNames`, `finishedOneTimeOnlyProjectNames`, `techProgress`, `campaignStartYear`, `endGameTechsCompletedByCategory` |
| Federation and war | `TIFederationState`, `TIWarState` | federation `members`, name/adjective fields; `TIWarState` was present but empty in this sample |

The inspected `TIFactionState.resources` object had these named resource members: `Money`, `Influence`, `Operations`, `Research`, `Projects`, `Boost`, `MissionControl`, `Water`, `Volatiles`, `Metals`, `NobleMetals`, `Fissiles`, `Antimatter`, and `Exotics`. The inspected `TICouncilorState.attributes` object had `Persuasion`, `Investigation`, `Espionage`, `Command`, `Administration`, `Science`, `Security`, `Loyalty`, and `ApparentLoyalty`.

## Implementation guidance

The table gives a direct first-pass mapping to `SaveSnapshot`:

```text
TITimeState           -> date, timestamp, turn-like campaign-day metadata
TIFactionState        -> factions
TINationState         -> nations
TIRegionState         -> regions
TIArmyState           -> armies
TICouncilorState      -> councilors
TIOrgState            -> organizations
TISpaceFleetState +
TISpaceShipState +
TIHabState            -> space
TIGlobalResearchState -> research / technologies
```

Use the state type and numeric map ID as the factual provenance key, for example `TINationState:123`. Save the original state type, map ID, and source path with every normalized object. Field-level domain code should resolve reference IDs through the target state map and report an unresolved reference as unknown rather than guessing a target.

For sequence ordering, use the componentized time state and raw-byte hash rules in [chronology and duplicate snapshots](chronology-and-deduplication.md), not a filename sort.

The more specific diff candidates are directly represented: control-point `faction`/`crackdown`/`defended`; nation relation and statistic fields; army `currentRegion`/`strength`/`destroyed`; councilor `faction`/`status`/`location`; fleet `trajectory`/`orbitState`/`inCombat`; ship `fleet`/`propellant_tons`/damage; and completed research collections.

See [snapshot-diff observations](diff-observations.md) for aggregate evidence that these fields change across a real save interval and for conservative event-evidence rules.

## Hypotheses and limits

- `currentDateTime` is the best candidate for normalized chronology because it is componentized, but the project has not yet compared it against `gameTimeString` across a sequence.
- A missing entity from a later map may mean destruction, archival, a filter, or a serialization change. Diff code must preserve that ambiguity.
- Field names suggest domain semantics, but a field's units, lifecycle, and causal meaning require before/after validation before an analyzer labels an event.
