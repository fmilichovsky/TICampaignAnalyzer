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
- [ ] Produce a deterministic single-save diff.
- [ ] Render objective changes as Markdown.

## Campaign history

- [ ] Add domain analyzers and rule-based reconstruction of higher-level events.
- [ ] Aggregate events across an ordered save sequence.
- [ ] Allow automatically detecting and scanning the real game save directory.
- [ ] Add a heuristic for grouping different saves into distinct campaigns.

## Narrative generator

- [ ] Consume normalized campaign data and turn them into a readable narrative.
