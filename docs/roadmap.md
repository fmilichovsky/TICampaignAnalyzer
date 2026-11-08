# Roadmap

## Foundation

- [x] Installable package and CLI entry point.
- [x] Separate pipeline stages, from loading to rendering.
- [x] Opt-in debug logging.
- [x] Detect and register unknown save structures (`tinarrative unknowns`).

## MVP

- [x] Document representative save-file structures.
- [x] Inspect a single save's raw structure (`save inspect`).
- [x] Load, validate and normalize a save (`save parse`).
- [x] Normalize councilors, armies, space entities and research.
- [x] Deterministic single-save diff (`save diff`).
- [x] Decode save-carried records with provenance.
- [x] Render objective changes as Markdown.

## Campaign history

- [x] Politics analyzers: control points, nations, councilors.
- [x] Army, space-object and technology analyzers.
- [x] Rule-based reconstruction of higher-level events
  ([sources](game-data-notes/higher-level-event-sources.md)):
  - [x] Significance and churn rules (#70).
  - [x] Nation metric shifts with cause attribution (#71).
  - [x] Territorial reconstruction (#72).
  - [x] Space reconstruction (#73).
  - [x] Wars and federations (#64).
  - [x] Region alien substates and Earth anomalies (#65).
  - [x] Organizations (#66).
  - [x] Global values singleton (#67).
  - [x] Notification log as a record (#68).
  - [x] Combat logs as a record (#69).
- [x] Aggregate events across an ordered save sequence (`events`).

## Narrative layer

Target: the narrator package of [architecture 13.1](architecture.md#131-narrator-input).

- [x] Entity names in every output (#94).
- [x] Space bodies as reference targets (#95).
- [x] Atomic gaps the narrative needs (#96).
- [x] Nation control reconstruction (#97).
- [x] Ledger mission records as corroboration (#98).
- [x] Situation reports (#99).
- [x] Narrative aggregation framework (#100).
- [x] Geopolitical narrative rules (#101).
- [x] Space narrative rules (#102).
- [x] Narrator package in `events --narrative` (#103).
- [x] LLM narrator contract (#104).
- [x] `tinarrative narrate`: request builder (#139), chapter plan (#140, #157), providers (#141), assembly (#142).
- [x] Narrator package gaps from the trials (#124, #125, #126, #127, #128, #129, #130, #131).
- [x] Narrator prompt rewrite (#132).
- [ ] Battle-outcome loss fields read as the actor's losses; combat records lack date and body (no issue yet).
- [x] Package-size measurement on benchmark samples.
- [x] Minimize the narrator package size (#144: #159, #160, #161, #165).
- [x] Takeover waves with digest-listed members (#163).
- [ ] Nation metrics redesign ([nation statistics](game-data-notes/nation-metrics.md)):
  - [x] Evidence pass (#189).
  - [x] Significance defaults (#190).
  - [x] Game bands and band-shift rules (#191).
  - [x] Nuclear arcs (#195, related #186).
  - [x] Population and economic trajectory (#192).
  - [x] Military and space-support assets and rankings (#193).
  - [ ] Campaign baseline from cumulative trackers (#194).
- [ ] Entity-scaled significance ([design](architecture.md#entity-scaled-score-design)):
  - [x] Design.
  - [x] Numeric score with unchanged levels (#196).
  - [x] Prominence shares (#197).
  - [x] Atomic events scaled by stake (#198).
  - [ ] Nuclear warheads in the situation report (#354).
  - [ ] Geopolitical narrative events scaled by stake (#199).
  - [ ] Nation narrative events scaled by power share (#359).
  - [ ] Nuclear arsenal share (#360).
  - [ ] Space program share (#361).
  - [ ] Space and faction stakes (#200).
  - [ ] Remove the top-N promotion (#362).
  - [ ] Narrator length and recall by score (#201).
- [x] Councilor profiles (#222):
  - [x] Missions and councilor dates (#228).
  - [x] Dossier and dry run (#229).
  - [x] LLM articles (#230).
  - [x] Enrich package data (#243).
  - [x] Fix councilor mission detection (#281).
  - [x] Public visibility in councilor articles (#284).
- [x] Diplomatic realignments as developments (#173).
- [ ] Slim down narrative package (#267):
  - [x] Exclude relations and default values (#268).
  - [ ] Reduce carried statistics (#269).
  - [ ] Drop duplicate fields (#270).
  - [ ] Drop unresolvable constituent IDs (#271).
  - [ ] Slim down atomic event attributes (#272).
  - [ ] Apply slimming to continuing events (#273)

## CLI user experience

- [x] Split `diff` and `events` by layer (#90).
- [x] `tinarrative save` command group (#91).
- [x] Directories as `events` input (#92).
- [x] Group saves by campaign (#89).
- [x] `tinarrative campaigns` and `events --campaign` (#93).
- [x] Interactive campaign picker.
- [x] Settings cleanup: a small, intent-grouped configuration surface (#364).

## Continuous capture

Target: record every save the game writes and narrate on demand in installments
([design](architecture.md#continuous-capture-design); tracking #207).

- [x] Design.
- [x] Evidence pass on the save directory (#208).
- [ ] Content-addressed save store (#209).
- [ ] Per-object index and `campaigns --store` (#210).
- [ ] `events --store` and `narrate --store` (#211).
- [ ] `tinarrative watch` (#212).
- [ ] Lines across reloads (#216).
- [ ] Interval cache (#213).
- [ ] Narration installments (#214).

## Processing runtime

Tracking #249.

- [x] Runtime benchmark and per-stage timing lines.
- [x] Record-log diff keys computed once (#253).
- [x] Shared snapshot and interval indexes (#254).
- [x] Indexed event stream for narrative rules (#255).
- [x] Normalization and model hot-path costs (#256).
- [x] Parallel survey and interval processing (#257).
- [x] Read only required sections during save survey (#274).
- [x] Ignore low-value and unused fields from normalization (#275).
- [x] Stop decoding unnecessary ledger labels (#276).
- [ ] Run analyzers selectively (#277).
- [ ] Package metrics on per-campaign workers instead of concurrent runs (#331).

## Code structure

- [ ] Event kinds: declare each event type once (#316):
  - [ ] Foundation and the aliens family (#317).
  - [ ] Campaign and faction families (#318).
  - [ ] Military family (#319).
  - [ ] Technology family (#320).
  - [ ] Space family (#321).
  - [ ] Nations family (#322).
  - [ ] Control family (#323).
  - [ ] Wars and federations family (#324).
  - [ ] Narrative-event kinds (#325).
  - [ ] Cleanup (#326).
- [ ] Campaign analysis: one module from save inputs to an analysed campaign (#328):
  - [ ] Narrative settings enter interval analysis as one slice (#329).
  - [ ] Drop the two-save rule (#330).
  - [ ] The survey step (#332).
  - [ ] Benchmark sample reuses the survey step (#333).
  - [ ] The choice and the analysis step (#334).
  - [ ] Thin the command-line tests (#335).
- [ ] Narrator send run: the narrator owns its run directory (#337):
  - [ ] Host: one bundle for clock, sleep and HTTP (#338).
  - [ ] Run directory: layout and response record (#339).
  - [ ] Send run into the narrator (#340).
  - [ ] Step functions per product (#341).
- [ ] Exclusive constituents: rule order keeps narrative events from re-telling each other's events (#344):
  - [ ] Explained events: rules declare their explainers (#345).
  - [ ] The merger cites everything it causes (#346).
  - [ ] Exclusive constituents: kinds declare them, rule order enforces them (#347).
- [ ] Narrative-event significance in one place (#349):
  - [ ] Rename "development" to "narrative event" (#350).
  - [ ] Situation report answers its own questions (#351).
  - [ ] One top-N promotion helper (#352).
  - [ ] One ranking of nations (#353).
  - [ ] Scored from kinds: geopolitics rules (#355).
  - [ ] Scored from kinds: nation-metric and diplomacy rules (#356).
  - [ ] Scored from kinds: asset and space rules (#357).
  - [ ] Rules no longer choose a level (#358).
