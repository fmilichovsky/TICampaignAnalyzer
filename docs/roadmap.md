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
- [x] Add rule-based reconstruction of higher-level events (evidence in
  [sources for higher-level events](game-data-notes/higher-level-event-sources.md)):
  - [x] Significance on events and the churn rules (recruit-pool councilors,
    routine fleet and councilor movement) (#70).
  - [x] Nation metric shifts with cause attribution from the
    `tracker_*ChangeReason_AllTime` maps (#71).
  - [x] Territorial reconstruction: unification, secession, annexation (#72).
  - [x] Space reconstruction: first presence on a body, hab losses joined to
    the destruction log, battle outcomes (#73).
  - [x] Wars and federations as entities with a war analyzer (#64).
  - [x] Region alien substates and Earth anomaly events (#65).
  - [x] Organizations and councilor organization events (#66).
  - [x] `TIGlobalValuesState` singleton: interstate wars, global milestones,
    nuclear and climate counters, serialized build version (#67).
  - [x] The game's notification log as a save-carried record (#68).
  - [x] `CombatLogs` reclassified from acknowledged to a record (#69).
- [x] Aggregate events across an ordered save sequence (`tinarrative events`):
  chronological ordering, byte-identical merging, per-interval analysis and
  reconstruction, interval-qualified event IDs. Joining evidence across
  intervals is the narrative layer's job (below).

## Narrative layer

Target: the narrator package of [architecture 13.1](architecture.md#131-narrator-input),
built from the developments catalogued in
[architecture 11.3](architecture.md#113-first-catalogue).

- [ ] Names in every output: render `EntityRef.name` in `describe_event`, the
  Markdown and the JSON for every domain that carries a `displayName` (#94).
- [ ] Normalize `TISpaceBodyState` as a `space body` reference target
  (`displayName`, parent body, body kind) so habs, fleets, destruction entries
  and milestones name their body (#95).
- [ ] Close the atomic gaps the narrative needs: `nation.claims_changed` and
  `hostileClaims`; `nation.renamed` / `federation.renamed` from `displayName`
  and `federationName`; `faction.project_completed` from
  `finishedProjectNames`; hull class on `ship.appeared`; the army's home nation
  on `army.*` events; `nation.unrest_attempts_changed` from
  `factionUnrestAttempts`; `nation.new_government_recorded` from
  `dateOfNewGovernment`; alien-or-human kind and population as attributes (#96).
- [ ] Reconstruct nation control per interval:
  `faction.nation_control_changed` (executive, plurality, sole controller) from
  control-point events, `controlPointType`, `positionInNation` and the
  executive record's cause, dated by the executive or new-government record
  when it falls in the interval; significance major (#97).
- [ ] Ledger mission records: `faction.transaction_recorded` for an
  allow-listed set of `Transactions` labels, record-dated by the assignment,
  minor, corroboration only, under the bounds of architecture 11.3; the
  zero-to-four-week assignment-to-outcome window is verified on private saves
  first (#98).
- [ ] Situation reports: `narrative/situation.py` builds the per-save digest
  of architecture 11.4 from one snapshot; `run_sequence` keeps the reports,
  not the snapshots (#99).
- [ ] Narrative aggregation framework: the narrative fields on `Event`,
  `narrative.aggregate(stream, situations)` with a named-rule protocol,
  windows over consecutive intervals in game days, the confidence and
  significance policy, and synthetic event-stream fixtures in
  `tests/narrative/` (#100).
- [ ] Geopolitical narrative rules: `faction.takeover` with precursors and
  consolidation, `war.arc`, `federation.lifecycle`, `nation.expansion`,
  `nation.cession`, `nation.release` / `nation.breakaway`,
  `nation.claims_declared`, `nation.transformation`, each carrying the nation
  statistic shifts of its span as `metric_shifts` (#101).
- [ ] Space narrative rules: `faction.space_campaign`,
  `faction.colonisation_wave`, `campaign.first_milestone` dating,
  `faction.fleet_buildup`, `technology.milestone` with its curated,
  documented list (#102).
- [ ] `tinarrative history <saves>`: the narrator package as JSON (narrative
  events, situation reports, glossary, atomic stream at `--min-significance`)
  and a Markdown digest grouped by period; `docs/commands/history.md` (#103).
- [ ] LLM narrator, outside this repository's deterministic scope for now: a
  prompt contract over the narrator package and prose that cites event IDs
  (#104).

## CLI user experience

- [x] Split `diff` and `events` by layer: `diff` reports literal state changes
  only, `events` is the single analyzed view (#90).
- [x] Group per-save evidence commands under `tinarrative save`
  (`save inspect`, `save parse`, `save diff`) (#91).
- [ ] Accept directories as `events` input, with the `unknowns` skip and
  exit-code policy (#92).
- [ ] Group saves by campaign from continuity evidence inside `events`, with
  link verdicts reported as inference (#89).
- [ ] Select among several campaigns: `tinarrative campaigns` listing and
  `events --campaign` (#93).

