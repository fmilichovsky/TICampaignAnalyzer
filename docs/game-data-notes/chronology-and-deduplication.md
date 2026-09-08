# Chronology and duplicate snapshots

This note supplies the ordering and deduplication rules for the architecture's
“ordered save sequence” and “campaign directory” modes. It is based on
non-sensitive structural comparisons of the private save directory on
2026-09-08.

## Observed facts

- `TITimeState` has one pair-map entry in the inspected complete save. Its
  `Value.currentDateTime` is an object with `year`, `month`, `day`, `hour`,
  `minute`, `second`, and `millisecond` fields; it has no observed timezone or
  offset field.
- The serialized dates matched the date portions embedded in five inspected
  filenames, including manual, auto, and exit saves.
- Manual-save sequence numbers are not a safe chronological ordering key. In
  the inspected directory, numbered save 71 had serialized time
  `2041-10-07 12:49:32`, while numbered save 72 had the earlier serialized
  time `2041-10-03 03:00:17`.
- `Resistsave00083_2046-10-8.json` and `Exitsave.json` had identical SHA-256
  hashes and byte lengths. They are byte-identical duplicate snapshots.
- `Autosave.json` had the same serialized `currentDateTime` as those two
  files but a different SHA-256 hash. Equal game time alone does not prove
  identical serialized state.

## Recommended campaign-input contract

1. Discover candidate files without assigning chronology from their names.
2. Load and parse the documented envelope, then extract the componentized
   `TITimeState.currentDateTime` when available.
3. Hash raw bytes with SHA-256. Coalesce byte-identical files into one
   analysis snapshot while retaining every original path as provenance.
4. Sort distinct snapshots by serialized date/time. For equal date/times but
   different hashes, retain both snapshots and use a deterministic secondary
   order (for example, normalized path); do not discard one as a duplicate.
5. Mark a save with missing, malformed, or unsupported time state as having
   unknown chronology. Do not place it into a diff interval based solely on
   filename or filesystem modification time.

`currentID.value` is not documented as a chronology key. Do not use it to
order saves without evidence that it is monotonic and comparable across the
relevant sequence.

## Hypotheses and limits

- Matching calendar date in filenames may be a convenience of these save
  modes, not a durable filename contract.
- Equal serialized times with different bytes could reflect sub-second state,
  save-mode metadata, or a meaningful simultaneous snapshot. Their semantic
  difference has not been classified.
- Time components may be game-calendar values rather than real-world UTC.
  The normalizer should represent them as a game timestamp until a timezone
  contract is established.
