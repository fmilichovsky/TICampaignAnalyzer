# Roadmap

## Foundation

- [x] Establish the installable Python package and CLI entry point.
- [x] Separate loading, parsing, model, diff, analysis, reconstruction,
  narrative, and rendering responsibilities.
- [x] Opt-in debug logging for `inspect` and `parse` (`--log-level`,
  `TINARRATIVE_LOG_LEVEL`).
- [x] Detect and register unknown save structures (`tinarrative unknowns`,
  `parse --record-unknowns`, `docs/game-data-notes/unknowns/`).

## MVP

- [x] Document representative save-file structures.
- [x] Inspect a single save's raw structure deterministically (`tinarrative inspect`).
- [x] Load and validate a raw save (`tinarrative parse` validation).
- [x] Normalize a minimal save snapshot (`tinarrative parse` summary).
- [x] Normalize councilors, armies, space entities, and research state.
- [x] Produce a deterministic single-save diff (`tinarrative diff`).
- [x] Decode save-carried records (dated logs, cumulative counters) with provenance and diff support.
- [x] Render objective changes as Markdown.

## Campaign history

- [x] Add the politics analyzers (control-point control, nation ownership and
  relations, councilor membership) emitting objective, evidence-backed events.
- [x] Add the army, space-object and technology analyzers.
- [ ] Add rule-based reconstruction of higher-level events (evidence in
  [sources for higher-level events](game-data-notes/higher-level-event-sources.md)):
  - [x] Significance on events and the churn rules (recruit-pool councilors,
    routine fleet and councilor movement) (#70).
  - [ ] Nation metric shifts with cause attribution from the
    `tracker_*ChangeReason_AllTime` maps (#71).
  - [ ] Territorial reconstruction: unification, secession, annexation (#72).
  - [ ] Space reconstruction: first presence on a body, hab losses joined to
    the destruction log, battle outcomes (#73).
  - [x] Wars and federations as entities with a war analyzer (#64).
  - [x] Region alien substates and Earth anomaly events (#65).
  - [x] Organizations and councilor organization events (#66).
  - [x] `TIGlobalValuesState` singleton: interstate wars, global milestones,
    nuclear and climate counters, serialized build version (#67).
  - [x] The game's notification log as a save-carried record (#68).
  - [x] `CombatLogs` reclassified from acknowledged to a record (#69).
- [ ] Aggregate events across an ordered save sequence.
