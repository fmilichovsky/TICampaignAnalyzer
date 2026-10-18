# `tinarrative events`

```
tinarrative events <save> <save> [<save>...] [--format markdown|json] [--min-significance <level>] [--inferred]
```

Reads two or more saves of one campaign, orders them by game time, and reports the analyzer
results of every pair of consecutive saves (architecture section 15, Mode B). Each pair is
analyzed exactly as [`diff --format markdown`](diff.md) does: the literal diff, every objective
analyzer, the significance rules and, with `--inferred`, the reconstruction rules. The command
does not check that the saves belong to the same campaign. Mixing campaigns produces nonsense
intervals, not an error.

## Ordering and duplicates

The rules follow [chronology and duplicate snapshots](../game-data-notes/chronology-and-deduplication.md):

- Saves are ordered by their serialized game time (`TITimeState.currentDateTime`). File names,
  argument order and modification times are never used, so the saves can be given in any order.
- Byte-identical saves (same SHA-256), such as an `Exitsave.json` beside the manual save it copies,
  are one snapshot. The first path in sort order is its source and the others are listed as
  `identical:` aliases.
- Saves with the same game time but different bytes are all kept and ordered by path.
- A save without a parseable game time cannot be placed, and the run stops with exit code 5.

Each save is read twice: once to hash it and read its game time, and once to normalize it in
order. At most two normalized snapshots are held at a time.

## Intervals and event IDs

An interval is a pair of consecutive saves. Its key is the later save's game time; a second or
later save with the same game time adds `#2`, `#3`, and so on. A save's key does not change when
other saves are added before or after it.

An event ID names a type and a subject, so the same ID can recur in another interval: a region
that changes hands twice, a value that drifts every interval, a notification queue index that
holds a different entry in each save. Every event ID in this report is therefore qualified with
`@<interval key>`, for example `region.nation_changed/region:42@2032-07-01T00:00:00`. The same
suffix is applied to an inferred event's constituents and to its `alternatives`.

Consecutive intervals share their boundary save, so every state change, and every new entry of a
save-carried log, is reported in exactly one interval. Events are never merged across intervals.
Reconstruction rules see one interval at a time. Evidence that is split across a boundary, such
as a nation taking another nation's regions over two intervals, is reported as one
`territory_gained` per interval and never as one `unification`. Combining events across intervals
is left to narrative aggregation.

## Markdown output

The default report lists:

- `## Saves`: the distinct saves in chronological order, each with its key and source path, its
  identical aliases, and a note when it has the same game time as the previous save. A summary
  line follows with the number of paths given and the number of byte-identical copies merged.
- `## Intervals`: one `### <earlier date> to <later date>` section per interval, giving:
  - the number of state changes;
  - with `--inferred`, `#### Inferred events` in the same layout as `diff`'s inferred section;
  - `#### Objective analyzer results`, grouped by category. Literal state changes are not listed;
    run `diff` on the pair for those.

`--min-significance <level>` filters both lists as in `diff`, and each list states how many
events it omitted. With fewer than two distinct saves, the report says that no interval was
compared and the command exits 0.

## JSON output

`--format json` prints one object:

- `inputs`, `duplicates`;
- `saves`: one object per distinct save, with `key`, `source`, `aliases`, `sha256` and `date`;
- `intervals`: one object per interval, with `index`, `key`, `before` and `after` (source paths),
  `not_before` and `date` (their game times), `changes` (state change count), `events` (the
  objective events, serialized as `Event.to_dict`) and `inferred` (the same for inferred events, or
  `null` without `--inferred`).

The JSON report holds every event. It ignores `--min-significance`.

Failures print one message to stderr naming the save that failed and no traceback. With
`--log-level info`, the run logs the ordering summary (paths given, distinct saves, duplicates,
tied game times, intervals) and per-interval event counts.

## Exit codes

| Code | When |
| --- | --- |
| 0 | Every save was loaded and every interval was analyzed (including when only one distinct save remained). |
| 2 | Usage error: fewer than two saves, or an unknown `--format` or `--min-significance`. |
| 4 | A save path cannot be read (missing, unreadable, or a directory). |
| 5 | A save is not a supported save (as for `diff`) or has no parseable game time. |
