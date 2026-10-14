# Roadmap

## Foundation

- [x] Establish the installable Python package and CLI entry point.
- [x] Separate loading, parsing, model, diff, analysis, reconstruction,
  narrative, and rendering responsibilities.

## MVP

- [x] Document representative save-file structures.
- [x] Inspect a single save's raw structure deterministically (`tinarrative inspect`).
- [ ] Normalize a minimal save snapshot.
- [ ] Produce a deterministic single-save diff.
- [x] Render objective changes as Markdown.

## Campaign history

- [ ] Add domain analyzers and rule-based reconstruction.
- [ ] Aggregate events across an ordered save sequence.
- [ ] Add fixture-driven parser and diff coverage.
