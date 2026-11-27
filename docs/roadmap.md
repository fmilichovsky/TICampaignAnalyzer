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

Target: the [narrator package](commands/events.md#narrator-package).

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
- [ ] Entity-scaled significance ([ADR-0011](adr/0011-significance-is-judged-once-and-scaled-by-share.md)):
  - [x] Design.
  - [x] Numeric score with unchanged levels (#196).
  - [x] Prominence shares (#197).
  - [x] Atomic events scaled by stake (#198).
  - [x] Nuclear warheads in the situation report (#354).
  - [x] Geopolitical narrative events scaled by stake (#199).
  - [x] Nation narrative events scaled by power share (#359).
  - [x] Nuclear arsenal share (#360).
  - [ ] Space program share (#361).
  - [x] Space and faction stakes (#200).
  - [x] Remove the top-N promotion (#362).
  - [ ] Narrator length and recall by score (#201).
- [ ] Stake calibration dashboard (#446):
  - [x] Stake measure registry, no nuclear bonus (#458).
  - [x] Public rule layers and the takeover wave member gate (#459).
  - [x] Calibration table extraction (#460).
  - [x] Calibration replay in Python, with pipeline parity (#461).
  - [x] Calibration replay in the browser, with parity against Python (#462).
  - [x] `benchmark calibrate report` and the calibration cache (#463).
  - [x] Calibration page and `benchmark calibrate open` (#464).
  - [x] One replay in Python; `calibrate open` serves the page and the browser replay is removed (#591).
  - [x] One scoring path for atomic and narrative events (#588).
  - [x] Draft stakes: declaration, scoring seam and shadow rows (#465).
  - [x] Draft stakes in the readout and on the page (#466).
- [x] Councilor profiles (#222):
  - [x] Missions and councilor dates (#228).
  - [x] Dossier and dry run (#229).
  - [x] LLM articles (#230).
  - [x] Enrich package data (#243).
  - [x] Fix councilor mission detection (#281).
  - [x] Public visibility in councilor articles (#284).
- [x] Sharpen councilor articles (#395):
  - [x] One home per subject across sections (#396).
  - [x] Councilor brief without audit fields (#397).
  - [x] Move dossier wording and banding into the brief (#398).
  - [x] Stances in place of faction names (#399).
  - [x] Public phrasing for missions (#400).
  - [x] Public aliases for faction-reward organizations (#302).
  - [x] Plain phrases for jargon trait labels (#401).
  - [x] Numbers as words (#402).
- [x] Diplomatic realignments as narrative events (#173).
- [ ] Slim down narrative package (#267):
  - [x] Exclude relations and default values (#268).
  - [ ] Reduce carried statistics (#269).
  - [ ] Drop duplicate fields (#270).
  - [ ] Drop unresolvable constituent IDs (#271).
  - [ ] Slim down atomic event attributes (#272).
  - [ ] Apply slimming to continuing events (#273)
- [x] Chapter length by narrative weight within an output budget (#418).

## Agent calibration framework

Target: agents that judge event kinds, base levels and scalings against the sample campaigns (#531).

- [ ] Repo skills in `.agents/skills`, symlinked from `.claude/skills` (#641).
- [x] Editorial direction (#642).
- [x] Scaling engine: a scaling per kind in place of the reference and the clamp (#643).
- [x] Calibration table: roles, explained events, interval dates and name history (#644).
- [x] Themes file (#645).
- [x] Sample profile in `samples.json` (#646).
- [x] Calibration registry script (#647).
- [x] Coverage labels (#648).
- [ ] Calibration principles (#649).
- [ ] Calibration page: a row per scaling (#650).
- [ ] Kind reasons (#651).
- [ ] Report views: `--view`, period and tiers (#652).
- [ ] Events view (#653).
- [ ] Distribution view (#654).
- [ ] Must-tell lists and the must-tell view (#655).
- [ ] Theme view and `--theme` (#656).
- [ ] Crowding view (#657).
- [ ] Smells view and thresholds (#658).
- [ ] Must-tell drafting tools (#659).
- [ ] Sample admission: coverage delta and as-found report (#660).
- [ ] Markdown evidence block (#661).
- [ ] Calibration evidence CI job (#662).
- [ ] Calibration reviews parent and the first registry members (#663).
- [ ] `kind-calibration` skill (#664).
- [ ] `calibration-review` skill (#665).
- [ ] `recollection-dissection` skill (#666).
- [ ] Must-tell list for `protectorate` (#667).
- [ ] Must-tell list for `resist-long` (#668).

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
(ADR [0016](adr/0016-captured-saves-are-evidence-everything-else-is-rebuilt.md),
[0017](adr/0017-reloads-split-a-campaign-into-lines.md), [0018](adr/0018-a-growing-campaign-is-narrated-in-sealed-installments.md); tracking #207).

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

- [x] Test suite hygiene: contributor standards, a leaner suite, sample tests in CI (#368).
- [x] Event kinds: declare each event type once (#316):
  - [x] Foundation and the aliens family (#317).
  - [x] Campaign and faction families (#318).
  - [x] Military family (#319).
  - [x] Technology family (#320).
  - [x] Space family (#321).
  - [x] Nations family (#322).
  - [x] Control family (#323).
  - [x] Wars and federations family (#324).
  - [x] Narrative-event kinds (#325).
  - [x] Cleanup (#326).
- [ ] Campaign analysis: one module from save inputs to an analysed campaign (#328):
  - [ ] Narrative settings enter interval analysis as one slice (#329).
  - [ ] Drop the two-save rule (#330).
  - [x] The survey step (#332).
  - [x] Benchmark sample reuses the survey step (#333).
  - [ ] The choice and the analysis step (#334).
  - [x] Thin the command-line tests (#335).
- [x] Narrator send run: the narrator owns its run directory (#337):
  - [x] Host: one bundle for clock, sleep and HTTP (#338).
  - [x] Run directory: layout and response record (#339).
  - [x] Send run into the narrator (#340).
  - [x] Step functions per product (#341).
- [x] Exclusive constituents: rule order keeps narrative events from re-telling each other's events (#344):
  - [x] Explained events: rules declare their explainers (#345).
  - [x] The merger cites everything it causes (#346).
  - [x] Derived rule order: narrative rules declare what they read (#382).
  - [x] Exclusive constituents: kinds declare them, rule order enforces them (#347).
- [ ] Narrative-event significance in one place (#349):
  - [x] Rename "development" to "narrative event" (#350).
  - [x] Situation report answers its own questions (#351).
  - [x] One top-N promotion helper (#352).
  - [x] One ranking of nations (#353).
  - [x] Scored from kinds: geopolitics rules (#355).
  - [x] Scored from kinds: nation-metric and diplomacy rules (#356).
  - [x] Scored from kinds: asset and space rules (#357).
  - [ ] Rules no longer choose a level (#358).
