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
  - [ ] Prominence shares (#197).
  - [ ] Atomic events scaled by stake (#198).
  - [ ] Developments scaled by stake (#199).
  - [ ] Space and faction stakes (#200).
  - [ ] Narrator length and recall by score (#201).
- [x] Councilor profiles (#222):
  - [x] Missions and councilor dates (#228).
  - [x] Dossier and dry run (#229).
  - [x] LLM articles (#230).

## CLI user experience

- [x] Split `diff` and `events` by layer (#90).
- [x] `tinarrative save` command group (#91).
- [x] Directories as `events` input (#92).
- [x] Group saves by campaign (#89).
- [x] `tinarrative campaigns` and `events --campaign` (#93).
- [x] Interactive campaign picker.

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
- [ ] Parallel survey and interval processing (#257).
