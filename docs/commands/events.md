# `tinarrative events`

```
tinarrative events <path> <path> [<path>...] [--campaign <selector>] [--format markdown|json] [--min-significance <level>] [--inferred] [--changes]
```

Reads two or more saves, given as files, directories or both, groups them by campaign, orders one campaign's saves by game time, and reports the analyzer
results of every pair of consecutive saves (architecture section 15, Mode B). Each pair is
diffed as [`save diff`](diff.md) does, and the diff is run through every objective analyzer, the
significance rules and, with `--inferred`, the reconstruction rules. `events` is the only command
that runs analyzers, significance or reconstruction; given two saves it is the analyzed view of
the pair, and with `--changes` it also lists the literal changes that `save diff` reports.

## Directory input

A directory contributes its files one level deep, in sorted order, as [`unknowns`](unknowns.md)
does; subdirectories are not entered. Files and directories can be mixed in any order. Only paths
named on the command line can fail the run:

- A named file that cannot be read or is not a usable save stops the run (exit 4 or 5).
- A file found inside a named directory that cannot be read, is not a supported save or has no
  parseable game time is skipped. It is listed in the report and never changes the exit code.
- A named directory that holds no files, or whose every file is skipped, is an input error
  (exit 4).

The "at least two saves" check applies after expansion: fewer than two candidate files, or fewer
than two usable saves once the skipped files are set aside, is a usage error (exit 2). A file
found in a directory and a file named on the command line with the same bytes are merged by the
rule below.

## Campaigns

Before ordering, the saves are grouped by campaign exactly as [`campaigns`](campaigns.md) lists them.
Saves belong to one campaign when the human player's faction, the faction name, the scenario and the
real-world campaign start all match. Grouping applies to files named on the command line as well as
to files found in directories.

- With one group, `events` reports it and `--campaign` is not needed.
- With several groups and no `--campaign`, `events` never picks a group silently or mixes groups.
  In a terminal it opens the [campaign picker](#campaign-picker). Otherwise the run stops with a
  usage error (exit 2) and prints
  `the input holds N campaigns; choose one with --campaign` and the `campaigns` listing to stderr.
- `--campaign <selector>` reports one group. The selector is a key or unique key prefix from the
  listing, the listing number, or `latest` (the group holding the most recently modified file;
  [selector keys](campaigns.md#selector-keys)). A selector that matches no group, or matches several,
  prints the reason, then opens the picker with the selector as its first search in a terminal, or
  prints the listing and exits 2 otherwise.

The "at least two saves" check also applies to the chosen campaign. A campaign with a single
distinct save, such as an unclassified save, is a usage error.

### Campaign picker

The picker opens only when both stdin and stderr are terminals. It writes the listing and its prompt
to stderr, so `events saves > report.md` still asks in the terminal and the file holds only the
report. Scripts and pipes keep the exit-2 behavior above. The prompt
`Campaign (number, key or search text; empty to cancel):` takes:

- anything `--campaign` accepts: a listing number, a key or unique key prefix, or `latest`;
- otherwise, fuzzy search text, matched against each group's key, faction name, scenario and
  real-world start (never against paths). Each whitespace-separated term must appear in order,
  not necessarily contiguously (`prot` matches `protectorate`), and case is ignored. A single match
  is chosen. With several, the listing narrows to them, best match first, keeping their listing
  numbers, and the prompt asks again. With none, the full listing is shown again.

An empty answer, end of input or Ctrl-C cancels the picker. The run prints
`no campaign chosen` and exits 2. Once a campaign is chosen, the run continues exactly as with
`--campaign`.

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

## Naming entities

The Markdown lines and the "affected entities" list name an entity as `Name (domain:key)`, for
example `Germany (nation:3857)`: the display name the save gives it, with the ID kept for audit.
An entity the save gives no name, or one that is not normalized (an orbit or a hab site), keeps the bare `domain:key`. A name-keyed entity whose name is its key, such as
a technology, is not repeated. This holds for the subject, the context in parentheses and any
reference an event carries as an attribute. The `#### State changes` section stays literal and
prints IDs only, as `save diff` does. Names are save content, so they appear in this report and
never in the diagnostic log.

## Markdown output

The default report lists:

- `## Campaign`: the chosen campaign's key, player faction, scenario and real-world start, and the
  signals it was grouped on. Grouping is inference, so the section names them. It also says how many
  given saves belong to other campaigns.
- `## Saves`: the distinct saves in chronological order, each with its key and source path, its
  identical aliases, and a note when it has the same game time as the previous save. A summary
  line follows with the number of usable saves given, the number of byte-identical copies merged
  and the number of skipped files. When files were skipped, a `Skipped` list follows, one line per
  file with its path, error class and the loader's message; the file's content is never shown.
- `## Intervals`: one `### <earlier date> to <later date>` section per interval, giving:
  - the number of state changes;
  - with `--inferred`, `#### Inferred events` (see below);
  - `#### Objective analyzer results`, grouped by category, each result with its affected entities;
  - with `--changes`, `#### State changes`: every literal change of the interval, grouped by
    domain, one line each in the form of `save diff`'s text report (a `records` change shows entry
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
`independence` with its release reading, `unification` and `annexation`), nation control
(`faction.nation_control_changed` per `executive`, `plurality` and `sole` scope) and space
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

- `campaign`: the chosen campaign, in the form `campaigns --format json` lists it;
- `inputs` (the chosen campaign's saves given, after directory expansion), `duplicates`;
- `skipped`: one object per file skipped inside a named directory, with `source`, `error_class` and
  `error` (empty when none);
- `saves`: one object per distinct save, with `key`, `source`, `aliases`, `sha256` and `date`;
- `intervals`: one object per interval, with `index`, `key`, `before` and `after` (source paths),
  `not_before` and `date` (their game times), `changes` (state change count), `events` (the
  objective events, serialized as `Event.to_dict`), `inferred` (the same for inferred events, or
  `null` without `--inferred`) and `state_changes` (the literal changes, each serialized exactly as
  a change in `diff --format json`, with values, detail and source locations, or `null` without
  `--changes`).

Every reference in `entities`, in `attributes` and in a source's `member` is an object with `ref`
(`domain:key`), `state_type`, `confidence` and, when the save gives the entity a display name,
`name`.

The JSON report holds every event. It ignores `--min-significance`.

`--changes` keeps every interval's changes, with their before and after values, in memory until
the report is written, so a long sequence uses more memory with it than without it.

Failures print one message to stderr naming the path that failed and no traceback. With
`--log-level info`, the run logs the paths given and candidate files, the number of campaigns and
the selected campaign's number (with `interactive=True` when it was picked), the ordering summary
(usable saves, distinct saves, duplicates, skipped files, tied game times, intervals) and
per-interval event counts. `--log-level debug` adds one line per skipped file with its file name
and error class; directory paths are never logged.

## Exit codes

| Code | When |
| --- | --- |
| 0 | Every named path was used and every interval was analyzed (including when only one distinct save remained). Files skipped inside a named directory do not change it. |
| 2 | Usage error: fewer than two usable saves after directory expansion or in the chosen campaign; several campaigns without `--campaign`, or a `--campaign` that matches no campaign or several, when stdin or stderr is not a terminal; a cancelled campaign picker; or an unknown `--format` or `--min-significance`. |
| 4 | A named path cannot be read (missing or unreadable), or a named directory holds no files or no usable save. |
| 5 | A named file is not a supported save (malformed, wrong shape, or unsupported format or game version) or has no parseable game time. |
