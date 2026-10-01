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
- Factions, nations, regions and space bodies carry a `Value.templateName` that
  looks like a content key (e.g. a nation or region template); councilors
  carry one such as a `pregenC<n>` style name for at least some entries.
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
| councilor | `TICouncilorState` | numeric ID | `in-save-id` | `templateName` (pregenerated only) |
| army | `TIArmyState`, `TIMegafaunaArmyState` | numeric ID | `in-save-id` | none |
| fleet | `TISpaceFleetState` | numeric ID | `in-save-id` | none |
| ship | `TISpaceShipState` | numeric ID | `in-save-id` | none |
| space object | space body, Lagrange point, orbit, ad hoc orbit, hab site, hab | numeric ID | `in-save-id` | `templateName` (bodies) |
| organization | `TIOrgState` | numeric ID | `in-save-id` | `templateName` |
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

## Unresolved (hypotheses; documented here only, not printed by `inspect`)

- Cross-snapshot stability of every numeric ID: requires comparing two saves of
  one campaign.
- Whether councilors, armies, fleets and ships keep their IDs across death,
  recruitment, merge, split or refit.
- Whether ad hoc orbits are transient (five observed with high IDs).
- Whether IDs are ever reused after an object is destroyed. No inspected
  entry in the domain types had `exists` false, so destruction is unobserved.
- Per-faction research ownership beyond `factionContributions`.
