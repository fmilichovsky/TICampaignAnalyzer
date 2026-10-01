# Entity identity strategy

Initial strategy for identifying the same game entity across snapshots. The
machine-readable form is `ENTITY_DOMAINS` in `src/tinarrative/identity.py`; the
census is printed by [`tinarrative inspect`](../commands/inspect.md) in its
`identity:` section.

## Observed facts

Observed on 2026-10-01 in one private mid-campaign save (aggregate figures only):

- Every gamestate entry has `Key.value == Value.ID.value`; 0 mismatches, 0
  missing, 0 duplicates in all 16,066 entries.
- IDs are drawn from **one global counter**: no ID appears in more than one state
  type, and `currentID` equals the largest ID in the save (it is the next-ID
  counter's high-water mark, observed; its exact semantics are a hypothesis).
- IDs are not dense per type. Objects created at campaign start occupy low blocks
  (space bodies 2..374, Lagrange points 375..465, regions 467..3725, nations
  3734..4557, factions 4815..4822); objects created during play (councilors,
  ships, fleets, habs, orgs, armies, ad hoc orbits) are interleaved up to
  `currentID`.
- Factions, nations, regions and space bodies carry a unique `Value.templateName`
  (content key). Councilor and organization `templateName` values are **not**
  unique (generated pools such as `randomizedCouncilor1`, `Random*`), so they are
  not a secondary key.
- Technologies have no state objects. Finished techs are strings in
  `TIGlobalResearchState.finishedTechsNames`; progress is
  `techProgress[].techTemplateName` with per-faction contributions keyed by
  faction ID.

## Strategy

| Domain | State types | Primary identity | Confidence | Secondary |
| --- | --- | --- | --- | --- |
| faction | `TIFactionState` | numeric ID | `in-save-id` | `templateName` |
| nation | `TINationState` | numeric ID | `in-save-id` | `templateName` |
| region | `TIRegionState` | numeric ID | `in-save-id` | `templateName` |
| councilor | `TICouncilorState` | numeric ID | `in-save-id` none |
| army | `TIArmyState`, `TIMegafaunaArmyState` | numeric ID | `in-save-id` | none |
| fleet | `TISpaceFleetState` | numeric ID | `in-save-id` | none |
| ship | `TISpaceShipState` | numeric ID | `in-save-id` | none |
| space object | space body, Lagrange point, orbit, ad hoc orbit, hab site, hab | numeric ID | `in-save-id` | `templateName` (space bodies) |
| organization | `TIOrgState` | numeric ID | `in-save-id` | none |
| technology | `TIGlobalResearchState` | template name string | `name-key` | none |

Because the counter is global, `(numeric ID)` alone is unique within a save; a
cross-snapshot key should still be stored with its domain.

Confidence levels:

- `in-save-id`: the save serializes an integer ID. It is unique within a save
  (observed). Stability across saves is **not** established.
- `name-key`: no ID; identity is a content/template name. Stable only while the
  name set is unchanged.
- A `heuristic` level is reserved for matching rules (e.g. by attributes) and is
  not used yet.

## Cross-save observations

Five saves of one campaign, in-game 2045-08-01, 2045-11-01, 2045-11-22,
2046-02-22 and 2046-10-08 (observed 2026-10-01, aggregates only):

- **Stable (observed):** 15,147 IDs are present in both the first and last save.
  None changed state type. Factions (8), nations (295), regions (363) and space
  bodies (373) kept the same IDs and `templateName`s. The 19 armies persisted.
  Finished techs stayed 148 and each save's set contained the previous one.
- **No ID reuse (observed):** every ID added between consecutive saves is above
  the previous save's `currentID`; no ID reappeared after disappearing; `currentID`
  rose monotonically (296902 -> 321998).
- **Objects vanish, not flagged:** removed objects are absent from the next save;
  none was kept with `exists` false.
- **Fleets:** 21 fleets disappeared between first and last save; 49 of their
  ships live on in other fleets with their ship IDs unchanged (fleet merge/rename
  keeps ship identity; the fleet ID is not carried over), 42 ships also vanished.
  84 persisted ships changed fleet.
- **Councilors/orgs:** disappearing councilors (61) and orgs (87) were almost
  entirely unaffiliated generated pool entries (58 of 61 councilors had no
  faction; all 87 orgs were `Random*`); named orgs and faction councilors
  persisted, and no persisted councilor changed faction.
- **Hab modules** were the only persisted objects whose `templateName` changed
  (empty -> assigned, i.e. construction).

## Unresolved

- Whether the 3 removed faction councilors died, were lost, or were otherwise
  removed: not determinable from the ID alone.
- Ship refit: no persisted ship changed `lastRefitDate`, so refit behaviour is
  unobserved.
- Army merge/split: not observed (no army removed except a megafauna army, whose
  replacement has a new ID).
- Ad hoc orbits: 1 of 5 disappeared and 1 appeared; likely transient, not proven.
- Whether fleet IDs identify a "fleet" across merges: they do not (merged
  fleets vanish), so fleet identity is the ID's lifetime only.
- Per-faction research ownership beyond `factionContributions`.
