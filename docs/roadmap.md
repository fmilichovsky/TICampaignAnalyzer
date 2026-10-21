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
- [ ] `tinarrative narrate`, designed in architecture section 20: send the
  package to a model in chapters under a fixed token budget, behind an
  explicit flag and API key, and write the prose with the model and prompt
  version in its header:
  - request builder in `tinarrative.narrator`: the prompt shipped in the
    package, `style` in the request block, the prompt hash as its version;
    `scripts/narrator_prompt.py` and the narrator-contract skill move to it
    (#139);
  - chapter plan: token estimate, period derived from the campaign span,
    chapter packages, the `continuity` member and the prompt rules for
    chapter parts; `narrate` writes the plan and the requests without
    sending; builds on the constituent-only atomic stream (#130, done) (#140);
  - providers `anthropic`, `openai` and `ollama` over the standard
    library's HTTP client behind `--send`, the `[narrator]` settings table
    with profiles, a provider-failure exit code (#141);
  - assembly: `history.md` with its header, footnotes renumbered across
    chapters, citation audit, run manifest and resume (#142).
- [ ] Narrator package gaps found by the trials:
  - [x] executive-seat semantics: the seat is the nation's `Executive`-typed
    control point, wherever it sits, with the point at `positionInNation` 0
    standing in for a nation that has none; the report and the control rule
    name which (#124);
  - [x] executive changes in a nation whose control points move to another
    nation in the same interval: only the moved points are left out of the
    control rule, which reports the rest at lower confidence (#125);
  - [x] `faction.space_campaign` lists as `bodies` only the bodies of its
    directly joined `hab.destroyed` events, not those of the losses its
    battle outcomes count (#126);
  - `war.arc` `duration_days` runs to an interval-based end without saying it
    is an upper bound, and its `start` is its first fighting record even when
    the war's own `started_on` is earlier (#127);
  - a corroborating ledger charge can set a takeover's `end` and its `record`
    basis (#128);
  - `metric_shifts` carry no per-shift dates, and `federation.lifecycle`
    attaches the shifts of a nation from before it joined (#129);
  - [x] with `--narrative`, `--min-significance` filters the narrative events
    and the atomic stream holds only the listed events' constituents,
    transitively, behind `--include-constituents` (#130);
  - [x] the glossary keeps the latest name of an entity whose display name
    changes between saves and lists the earlier ones; battle outcomes and
    hab destructions name every faction and body reference (#131).
- [x] Narrator prompt rewritten around a short fact floor and free
  interpretation: per-entry footnotes, a `style: headlines` option, no
  meta-statements about the record, a backstory ban, actor-side count
  semantics, `narrative_event` labels left out (#132).
- [ ] Narrator package gaps found by the rewrite trials: `habs_lost`,
  `fleets_lost` and `kill_count` on battle outcomes and space campaigns read
  as the actor's losses by every trial; name them for the victim
  (`victim_habs_lost`) or carry an explicit `victim` on the campaign; combat
  records carry no date or body, so battle narration cannot place them.

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

