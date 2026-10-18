# `tinarrative events`

```
tinarrative events <save> <save> [<save>...] [--format markdown|json] [--min-significance <level>] [--inferred] [--changes]
```

Reads two or more saves of one campaign, orders them by game time, and reports the analyzer
results of every pair of consecutive saves (architecture section 15, Mode B). Each pair is
diffed as [`diff`](diff.md) does, and the diff is run through every objective analyzer, the
significance rules and, with `--inferred`, the reconstruction rules. `events` is the only command
that runs analyzers, significance or reconstruction; given two saves it is the analyzed view of
the pair, and with `--changes` it also lists the literal changes that `diff` reports. The command
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
  - with `--inferred`, `#### Inferred events` (see below);
  - `#### Objective analyzer results`, grouped by category, each result with its affected entities;
  - with `--changes`, `#### State changes`: every literal change of the interval, grouped by
    domain, one line each in the form of `diff`'s text report (a `records` change shows entry
    counts only). When the interval has none, the section says `No state changes were recorded.`

With fewer than two distinct saves, the report says that no interval was compared and the
command exits 0.

### Significance

Every analyzer result carries a significance (`trivial`, `minor`, `major` or
`campaign_defining`), assigned by the rules in `narrative/significance.py` (architecture
section 12). `--min-significance <level>` lists only the results at that level or above; the
default `trivial` lists every result. When results are dropped, one line after the interval's
objective results states how many were omitted and below which level, so the report never hides
the omission. State changes listed with `--changes` are never filtered.

### Inferred events

`--inferred` also runs the reconstruction stage (`reconstruction.infer_events`, architecture
sections 5.2 and 10) on each interval's analyzer results and lists what it infers in a separate
`#### Inferred events` section before the objective results, so inferences never mix with the
results they rest on. Today the rules cover territory (`territory_gained` / `territory_lost`,
`independence` with its release reading, `unification` and `annexation`) and space
(`faction.first_hab_on_body`, `hab.destroyed`, `faction.battle_outcome`). Each line gives the event's reading and its `confidence`; an event whose evidence
fits several readings is prefixed `[ambiguous]` and followed by an `alternatives:` line naming the
competing event IDs. Below it, one `from` line per constituent names the objective result's ID and
its description as listed under `#### Objective analyzer results` (the ID alone if that result is
not among the analyzer results):

```
- nation:20 annexed 1 region of nation:21 (confidence: `medium`)
  - from `nation.relation_changed/wars/nation:20/nation:21/added@2032-04-01T00:00:00`: nation:20 and nation:21: wars entry added (listed by both)
  - from `region.nation_changed/region:42@2032-04-01T00:00:00`: region:42 nation: nation:21 -> nation:20
```

Inferred events get a significance by the same rules and `--min-significance` filters them the
same way; the section states its own omitted count (`N inferred events below <level>
significance omitted.`), separate from the objective one. When nothing was inferred the section
says `No events were inferred.`

## JSON output

`--format json` prints one object:

- `inputs`, `duplicates`;
- `saves`: one object per distinct save, with `key`, `source`, `aliases`, `sha256` and `date`;
- `intervals`: one object per interval, with `index`, `key`, `before` and `after` (source paths),
  `not_before` and `date` (their game times), `changes` (state change count), `events` (the
  objective events, serialized as `Event.to_dict`), `inferred` (the same for inferred events, or
  `null` without `--inferred`) and `state_changes` (the literal changes, each serialized exactly as
  a change in `diff --format json`, with values, detail and source locations, or `null` without
  `--changes`).

The JSON report holds every event. It ignores `--min-significance`.

`--changes` keeps every interval's changes, with their before and after values, in memory until
the report is written, so a long sequence uses more memory with it than without it.

Failures print one message to stderr naming the save that failed and no traceback. With
`--log-level info`, the run logs the ordering summary (paths given, distinct saves, duplicates,
tied game times, intervals) and per-interval event counts.

## Exit codes

| Code | When |
| --- | --- |
| 0 | Every save was loaded and every interval was analyzed (including when only one distinct save remained). |
| 2 | Usage error: fewer than two saves, or an unknown `--format` or `--min-significance`. |
| 4 | A save path cannot be read (missing, unreadable, or a directory). |
| 5 | A save is not a supported save (malformed, wrong shape, or unsupported format or game version) or has no parseable game time. |
