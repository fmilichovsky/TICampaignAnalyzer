# Snapshot-diff observations

This page records non-sensitive, aggregate comparisons between the private
`Resistsave00070_2041-5-1.json` and `Resistsave00071_2041-10-7.json` samples
inspected on 2026-09-08. It informs the objective-diff and inference boundary
in [`docs/architecture.md`](../architecture.md); it does not label the cause
of any change.

## Observed identity continuity

The comparison used the pair-map `Key.value` identity documented in
[Containers, identity, and references](containers-and-references.md).

| State type | Earlier entities | Later entities | IDs retained |
| --- | ---: | ---: | ---: |
| `TIFactionState` | 8 | 8 | 8 |
| `TINationState` | 295 | 295 | 295 |
| `TIRegionState` | 363 | 363 | 363 |
| `TIControlPoint` | 429 | 423 | 422 |
| `TIArmyState` | 23 | 22 | 22 |
| `TICouncilorState` | 153 | 159 | 99 |
| `TISpaceFleetState` | 90 | 97 | 69 |
| `TISpaceShipState` | 452 | 444 | 391 |
| `TIHabState` | 260 | 260 | 255 |
| `TIGlobalResearchState` | 1 | 1 | 1 |

An ID in both maps identifies the same serialized entity for this interval.
The comparison does **not** establish why a non-retained ID is absent, or
whether a newly appearing ID is a new game-world entity. Those are inference
questions.

## Observed changed-field counts

For retained entities only, the following counts are exact JSON-value changes
over that interval. They are evidence that these fields change in ordinary
campaign progression, not proof of a specific game action.

| State type | Retained entities | Fields and changed-entity counts |
| --- | ---: | --- |
| `TIControlPoint` | 422 | `faction` 8; `benefitsDisabled` 2; `defended` 36; `crackdownExpiration` 2; `defendExpiration` 94 |
| `TINationState` | 295 | `allies` 22; `rivals` 14; `wars` 6; `GDP` 88; `inequality` 88; `education` 77; `democracy` 76; `cohesion` 84; `unrest` 77; `militaryTechLevel` 14; `controlPoints` 6; `federation` 8 |
| `TIArmyState` | 22 | `currentRegion` 4; `strength` 2; `faction` 0; `destroyed` 0; `operationTarget` 0 |
| `TICouncilorState` | 99 | `faction` 1; `location` 38; `status` 0; `orgs` 29; `XP` 47 |
| `TISpaceFleetState` | 69 | `ships` 28; `trajectory` 17; `orbitState` 15; `inCombat` 0; `faction` 0 |
| `TISpaceShipState` | 391 | `fleet` 33; `propellant_tons` 99; `damagePoints` 4; `storedFaction` 0 |

## Recommended event-evidence rules

These are conservative project rules, not observed game semantics:

- Emit a high-confidence **objective field transition** when a retained ID's
  field changes, preserving before/after serialized values and source saves.
- Emit an **appearance** or **disappearance** observation when an ID enters or
  leaves a state map. Do not name it “created,” “destroyed,” “purged,” or
  “annexed” without corroborating evidence.
- Keep timer/expiry fields (`defendExpiration`, `crackdownExpiration`) separate
  from strategic events; their frequent change makes them poor narrative
  signals by themselves.
- Treat high-churn fields such as councilor `XP`, ship propellant, and nation
  statistics as objective measurements. Narrative significance needs a
  threshold or an accompanying discrete transition.
- Candidate analyzers may interpret a control-point `faction` change, an army
  `destroyed` change, or a completed-research collection change, but must
  retain the literal diff as evidence.

## Limits

This is one interval in one campaign. It validates the mechanics of ID-keyed
comparison and identifies fields worth modeling; it does not establish
universal rates, thresholds, or event causality.
