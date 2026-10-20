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

- [x] Names in every output: render `EntityRef.name` in `describe_event`, the
  Markdown and the JSON for every domain that carries a `displayName` (#94).
- [x] Normalize `TISpaceBodyState` as a `space body` reference target
  (`displayName`, parent body; the save serializes no body kind) so habs, fleets, destruction entries
  and milestones name their body (#95).
- [x] Close the atomic gaps the narrative needs: `nation.claims_changed` and
  `hostileClaims`; `nation.renamed` / `federation.renamed` from `displayName`
  and `federationName`; `faction.project_completed` from
  `finishedProjectNames`; hull class on `ship.appeared`; the army's home nation
  on `army.*` events; `nation.unrest_attempts_changed` from
  `factionUnrestAttempts`; `nation.new_government_recorded` from
  `dateOfNewGovernment`; alien-or-human kind and population as attributes (#96).
- [x] Reconstruct nation control per interval:
  `faction.nation_control_changed` (executive, plurality, sole controller) from
  control-point events, `controlPointType`, `positionInNation` and the
  executive record's cause, dated by the executive record when it agrees;
  significance major (#97).
- [x] Ledger mission records: `faction.transaction_recorded` for an
  allow-listed set of `Transactions` labels, record-dated by the assignment,
  minor, corroboration only, under the bounds of architecture 11.3; the
  zero-to-four-week assignment-to-outcome window is verified on private saves
  first (#98).
- [x] Situation reports: `narrative/situation.py` builds the per-save digest
  of architecture 11.4 from one snapshot; `run_sequence` keeps the reports,
  not the snapshots (#99).
- [x] Narrative aggregation framework: the narrative fields on `Event`,
  `narrative.aggregate(stream, situations)` with a named-rule protocol,
  windows over consecutive intervals in game days, the confidence and
  significance policy, and synthetic event-stream fixtures in
  `tests/narrative/` (#100).
- [x] Geopolitical narrative rules: `faction.takeover` with precursors and
  consolidation, `war.arc`, `federation.lifecycle`, `nation.expansion`,
  `nation.cession`, `nation.release` / `nation.breakaway`,
  `nation.claims_declared`, `nation.transformation`, each carrying the nation
  statistic shifts of its span as `metric_shifts`, with the thresholds and windows as runtime
  settings (`--config`, [configuration](configuration.md)) (#101).
- [x] Space narrative rules: `faction.space_campaign`,
  `faction.colonisation_wave`, `campaign.first_milestone` dating,
  `faction.fleet_buildup`, `technology.milestone` with its curated,
  documented list (#102).
- [x] Complete the narrator package in `events --narrative` rather than a
  separate `history` command: a `glossary` in the JSON (every referenced ID
  with its name and kind, a nation's regions), `--min-significance` applied to
  the JSON with omitted counts, `--period year|half|quarter` for the narrative
  section, key attributes on narrative lines, and collapsed empty intervals so
  the Markdown reads as a digest; the package schema in
  `docs/commands/events.md` (#103).
- [x] LLM narrator contract, verified by trial runs: the prompt in
  `docs/narrator.md`, a narrator package without provenance or paths
  (`events --narrative --format json`, audited through the same run with
  `--inferred`), and `scripts/narrator_prompt.py` to assemble a request
  without calling an API (#104).
- [ ] `tinarrative narrate`: send the request behind an explicit flag and API
  key, and write the prose beside the package with the model and prompt
  version in its header.
- [ ] Narrator package gaps found by the trials:
  - executive-seat semantics: where a nation has a control point typed
    `Executive` that is not at `positionInNation` 0,
    `lastExecutiveChange.newExecutive` follows that point, so the situation
    report's `executive` (position 0) and the control events disagree; settle
    the seat in `docs/game-data-notes/` and in the situation report and
    control rule (#124);
  - executive changes in a nation whose control points move to another nation
    in the same interval are skipped as territory and reported nowhere (#125);
  - `faction.space_campaign` lists as `bodies` only the bodies of its
    directly joined `hab.destroyed` events, not those of the losses its
    battle outcomes count (#126);
  - `war.arc` `duration_days` runs to an interval-based end without saying it
    is an upper bound, and its `start` is its first fighting record even when
    the war's own `started_on` is earlier (#127);
  - a corroborating ledger charge can set a takeover's `end` and its `record`
    basis (#128);
  - `metric_shifts` carry no per-shift dates, and `federation.lifecycle`
    attaches the shifts of a nation from before it joined (#129);
  - one `--min-significance` filters both the narrative and the atomic stream,
    so `minor` developments bring the whole `minor` stream with them (#130);
  - the glossary keeps one name for control points whose display name
    changes between saves, and a few alien faction refs carry no name (#131).
- [ ] Narrator prompt: faction briefs stated as fact, public-audience front
  leaks on smaller models, uncited statements about the record (#132).

## CLI user experience

- [x] Split `diff` and `events` by layer: `diff` reports literal state changes
  only, `events` is the single analyzed view (#90).
- [x] Group per-save evidence commands under `tinarrative save`
  (`save inspect`, `save parse`, `save diff`) (#91).
- [x] Accept directories as `events` input, with the `unknowns` skip and
  exit-code policy (#92).
- [x] Group saves by campaign from continuity evidence inside `events`, with
  the grouping signals reported as inference (#89).
- [x] Select among several campaigns: `tinarrative campaigns` listing and
  `events --campaign` (#93).
- [x] Pick the campaign interactively, with fuzzy search, when `events` runs in
  a terminal without a matching `--campaign`.

