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
- [x] `tinarrative narrate`, designed in architecture section 20: send the
  package to a model in chapters under a fixed token budget, behind an
  explicit flag and API key, and write the prose with the model and prompt
  version in its header:
  - request builder in `tinarrative.narrator`: the prompt shipped in the
    package, `style` in the request block, the prompt hash as its version;
    `scripts/narrator_prompt.py` and the narrator-contract skill move to it
    (#139, done);
  - chapter plan: token estimate, period derived from the campaign span,
    chapter packages, the `continuity` member and the prompt rules for
    chapter parts; `narrate` writes the plan and the requests without
    sending; builds on the constituent-only atomic stream (#130, done) (#140,
    done); the period made coarser chapter by chapter where the saves are too
    sparse for it (#157, done);
  - providers `anthropic`, `openai` and `ollama` over the standard
    library's HTTP client behind `--send`, the `[narrator]` settings table
    with profiles, a provider-failure exit code (#141, done);
  - assembly: `history.md` with its header, footnotes renumbered across
    chapters, citation audit, run manifest, resume and `--assemble` (#142,
    done).
- [x] Narrator package gaps found by the trials:
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
  - [x] `war.arc` states an interval-bound duration as `duration_days_at_most`,
    and its `start` is the war's own record-dated `started_on` even when that
    predates the first save (#127);
  - a corroborating ledger charge can set a takeover's `end` and its `record`
    basis (#128);
  - [x] `metric_shifts` entries carry `not_before`, `date` and `date_basis`, and
    `federation.lifecycle` attaches a nation's shifts only from its
    membership intervals (#129); `war.arc` still attaches the shifts of a
    nation that joined mid-war from before it joined;
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
- [x] Package-size measurement: real sample campaigns in `benchmarks/samples/`, a matrix of `events` and
  `narrate` runs, `scripts/package_metrics.py` to measure and compare, and a workflow that posts base vs. head
  on every pull request.
- [x] Minimize the narrator package size (#144):
  - [x] slim the situation reports in the narrator form: allies as ref strings, bodies with one hab counted
    in `other_bodies`, `seat_basis` and a zero `unresolved_points` dropped, floats to 4 significant digits,
    chapter reports without nations that hold no region and that the chapter does not name (#159).
  - [x] list only narrator evidence in the atomic stream: one `--constituents all|evidence|none` flag, `narrate`
    building with `evidence`, and the takeover carrying its executive record's date and previous holder (#160).
  - [x] bound `metric_shifts`: no `numControlPoints`, at most `narrative.geopolitics.metric_shifts_max` entries per
    development with the rest counted, and no shift event IDs in the narrator form (#161).
  - [x] the glossary keeps only former names and the names of entities referenced by ID only: no `kind`, no
    nation `regions` and no region entries (#165).
- [ ] Nation metrics redesign: one rule per metric, shaped by how the metric behaves in the game, with
  `nation.statistic_shifted` kept as evidence (observations in
  [nation statistics](game-data-notes/nation-metrics.md)):
  - [x] evidence pass on the private saves: the quarterly per-capita GDP series and the cumulative cause trackers
    as campaign-long sources, population and GDP rates, band crossings with the margin and rest-value filters,
    nuclear, space-support and military assets (#189);
  - [x] significance: shifts `trivial` by default and `numNuclearWeapons` `major`; `numControlPoints` no longer a
    tracked statistic; `nation.transformation` and `transformation_window_days` removed (#190);
  - [x] bands as game vocabulary (`analyzers/politics/bands.py`, margins fixed there), `nation.band_crossed` with
    the margin and the tracker causes, one band-shift rule per statistic (`nation.unrest_shift`, `nation.government_shift`,
    `nation.education_shift`, `nation.cohesion_shift`, `nation.inequality_shift`, `nation.miltech_shift`) with the
    rest-value filter, confirmation by the next report and carrier suppression; `from_band` / `to_band` on
    `metric_shifts`; the architecture's band-label rule amended for game-defined bands (#191);
  - [ ] nuclear arcs: `nation.nuclear_program_changed` and `nation.policy_changed` atomic events,
    `nation.nuclear_armament`, `nation.nuclear_buildup`, `nation.nuclear_disarmament` (#195, related #186);
  - [ ] population and economic trajectory: territory-adjusted `nation.population_changed` and
    `nation.population_collapse`; `nation.pcgdp_trend` from `tracker_PCGDP_ByQuarter`, record-dated by quarter,
    chained into `nation.economic_trajectory`, with the quarters before the first save as `before_sequence`
    backstory (#192);
  - [ ] military and space-support assets and rankings: armies, navies, the strength estimate, boost, mission
    control and space defences in the situation report; `nation.military_buildup` / `nation.demobilization`,
    `nation.navy_established`, `nation.space_program_growth`, `nation.space_defences_established`,
    `world.ranking_changed` by GDP, strength, boost and mission control (#193);
  - [ ] campaign baseline from the cumulative cause trackers (`nation.since_start`), after the cohesion and unrest
    outliers are explained (#194).
- [ ] Entity-scaled significance: a 0–100 `score` beside the level, the type's base scaled by the share of the
  world the event moved, the four levels kept as bands over it (design in
  [architecture 12](architecture.md#entity-scaled-score-design), evidence in
  [space assets](game-data-notes/space-assets.md)):
  - [x] design: the score contract, the stake measures, the combination rule and the package contract in
    architecture 12; the *published* evidence label; the alien and human space holdings;
  - [ ] score with unchanged levels: `Event.score` with every base at its band midpoint, the `[narrative.significance]`
    bands and clamp, `score` in the JSON; the `narrative.<level>` package counts unchanged (#196);
  - [ ] prominence: `narrative/prominence.py` with the nation power share (GDP, population and the published
    strength estimate, weighted), region population and organization tier² shares, from snapshots and situation
    reports; the strength inputs in the situation report shared with #193; the power ranking recorded against the
    GDP ranking (#197);
  - [ ] atomic events scaled by stake: a `SCALED` table in `narrative/significance.py`, `significance_basis` in the
    `events` output and not in the narrator form, the nuclear bonus for wars across nuclear-armed nations, the
    tier-3 organization rule replaced by tier²; churn never scaled (#198);
  - [ ] developments scaled by stake: the builder's level becomes the rule's base plus the scale of its summed stake,
    floored by the cited scores; `faction.takeover` (replacing `top_gdp_nations`), `war.arc`, `nation.expansion`,
    `nation.cession`, `nation.release` / `nation.breakaway`, `federation.lifecycle` (#199);
  - [ ] space and factions: mass per hull class observed first; hab and fleet shares over the human totals with
    `hab_saturation` / `fleet_saturation`, the faction stake (Earth share blended with the ramped space share, the
    alien faction as backdrop), the battle stake by contested mass with `alien_mass_weight` and `contest_ratio`;
    the hab, fleet, battle and colonisation rules scaled (#200);
  - [ ] narrator by score: chapter length shares and continuity recall follow the score, the level tuple pinned
    to the model's, the prompt leads with the highest-scored developments (#201).

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


## Continuous capture

Target: a campaign recorded from every save the game writes, autosaves included, without manual saves, and narrated
on demand in installments ([architecture, Mode D](architecture.md#continuous-capture-design) and
[20.7](architecture.md#207-installments-design); tracking #207).

- [x] Design: the capture, index, campaign and interval-cache layers of Mode D, lines across reloads, the store layout
  of section 16, the installments of 20.7; the save modes as hypotheses in
  [the save directory](game-data-notes/save-directory.md).
- [ ] Evidence pass on the save directory: a read-only observation script, autosave rotation, combat and exit saves,
  write pattern and duration, folder location; the poll and settle defaults (#208).
- [ ] Content-addressed save store: xz objects named by the SHA-256 of the save, the append-only capture log, one
  writer lock, store location settings, `store import`, `store status` and `store verify` (#209).
- [ ] Per-object index (game time, campaign profile, build, status, parser fingerprint), stable campaign IDs and
  `campaigns --store` (#210).
- [ ] `events --store` and `narrate --store`: the sequence planned from index records and snapshots loaded from
  objects, with output identical to the same saves given as paths (#211).
- [ ] `tinarrative watch`: polling with a settle check, capture before indexing, catch-up on start, `--once` for
  schedulers (#212).
- [ ] Lines across reloads ([architecture](architecture.md#lines-design)): the continuity test over witness records,
  the save tree, the current line by capture order, `--line`, abandoned lines listed, installments refusing a seal on
  an abandoned line (#216).
- [ ] Interval cache: round-trip serialization of events and situation reports, entries keyed by both save hashes and
  the analysis-code fingerprint, qualification on read, `store gc` (#213).
- [ ] Narration installments: `narrate --append` with options fixed at the first installment, `middle…last` parts,
  `continuing` and `late` continuity, one history across installments, drift reported (#214).
