# `tinarrative events`

```
tinarrative events <path> <path> [<path>...] [--campaign <selector>] [--format markdown|json] [--min-significance <level>] [--period year|half|quarter] [--inferred] [--narrative] [--constituents all|evidence|none] [--changes] [--config <file>]
```

Reads the saves of one campaign, puts them in game-time order and reports what happened between
every pair of consecutive saves: the events found in each interval, how significant each one is
and, on request, the events inferred from them, the narrative events that span the whole campaign and
the literal state changes. It is the analyzed counterpart of [`save diff`](diff.md), and the
source of the package that [`narrate`](narrate.md) tells.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `PATH...` | required | Save files or directories, in any order. A directory is read one level deep. |
| `--campaign SELECTOR` | | The campaign to report when the saves hold several ([campaigns](#campaigns)). |
| `--format markdown\|json` | `markdown` | Markdown report or the JSON document. |
| `--min-significance LEVEL` | `trivial` | Lowest significance listed: `trivial`, `minor`, `major` or `campaign_defining`. Omitted events are counted, never hidden. With `--narrative` it filters the narrative events. |
| `--inferred` | off | Also list the events inferred from each interval's results, with what they rest on. |
| `--narrative` | off | Also join the events of the whole campaign into [narrative events](#narrative-events); implies `--inferred`. |
| `--constituents all\|evidence\|none` | `none` | With `--narrative`, which of the events behind the listed narrative events to list: all of them, the narrator evidence among them, or none. Ignored without `--narrative`. |
| `--period year\|half\|quarter` | `year` | How the Markdown narrative section is grouped. The JSON is not grouped. |
| `--changes` | off | Also list every literal state change under its interval. A usage error with `--narrative --format json`. |
| `--config FILE` | `$TINARRATIVE_CONFIG`, else built-in | Settings file for the narrative rules' thresholds and windows ([configuration](../configuration.md)). Read and validated on every run. |
| `--jobs N` | `processing.jobs`, else bounded by CPUs and memory | Worker processes for surveying the saves and analyzing the intervals; `1` runs everything in one process. Small inputs run in one process. The output is the same for every value ([configuration](../configuration.md)). |

## Input

- Files and directories can be mixed. A directory contributes its files one level deep;
  subdirectories are not entered.
- A named file that is not a usable save stops the run (exit 4 or 5). A file inside a named
  directory that is not a usable save is skipped and listed in the report.
- At least two usable saves are needed, after directory expansion and in the chosen campaign.
  Fewer is a usage error (exit 2).
- Saves are ordered by game time, never by file name or argument order. Byte-identical copies
  (such as an `Exitsave.json` beside the save it copies) are merged into one.

## Campaigns

The saves are grouped by campaign as [`campaigns`](campaigns.md) lists them.

- With one campaign, `--campaign` is not needed.
- With several and no `--campaign`, a terminal opens the [campaign picker](#campaign-picker);
  otherwise the run exits 2 and prints the listing to stderr. Campaigns are never mixed.
- `--campaign` takes a key or unique key prefix, the listing number, or `latest`
  ([selector keys](campaigns.md#selector-keys)). A selector that matches no campaign or several
  opens the picker in a terminal, or exits 2 otherwise.

### Campaign picker

The picker opens only when stdin and stderr are both terminals. It writes to stderr, so
`events saves > report.md` still asks in the terminal. At the prompt
`Campaign (number, key or search text; empty to cancel):` type:

- anything `--campaign` accepts (a number, a key or key prefix, `latest`); or
- search text, matched against the key, faction name, scenario and start date. Letters may be
  skipped (`prot` finds `protectorate`) and case is ignored. With several matches the listing
  narrows and the prompt asks again.

An empty answer, end of input or Ctrl-C cancels: the run prints `no campaign chosen` and exits 2.

## Markdown output

- `## Campaign`: the chosen campaign and the signals it was grouped on.
- `## Saves`: the saves in game-time order with their merged copies, and any skipped files.
- `## Narrative` (with `--narrative`): the narrative events by period.
- `## Intervals`: one section per pair of saves with its change count, `#### Inferred events`
  (with `--inferred`), `#### Objective analyzer results` grouped by category, and
  `#### State changes` (with `--changes`).

Entities are named as `Name (domain:key)`, such as `Germany (nation:3857)`. Every event has an ID
qualified by its interval, such as `region.nation_changed/region:42@2032-07-01T00:00:00`, so it can
be cited and looked up. An inferred event lists the events it rests on:

```
- nation:20 annexed 1 region of nation:21 (confidence: `medium`)
  - from `region.nation_changed/region:42@2032-04-01T00:00:00`: region:42 nation: nation:21 -> nation:20
```

## Narrative events

`--narrative` joins the events of the whole campaign into narrative events that span
intervals, such as a takeover and its consolidation, a war from start to peace, or a nation's
economic boom. Each is listed under its starting period with its span, `(open)` when it is still
under way in the last save, its description, confidence and significance, its roles, its key
attributes and the IDs of the events it is built from:

```
- `2032-01-01T00:00:00` to `2032-07-01T00:00:00` (open): <description> (inferred, confidence `medium`, significance `major`)
  - roles: actor: Fixture Faction (faction:7); target: Fixture Nation (nation:20)
  - attributes: metric_shifts: 2; region_count: `1`
  - from `faction.nation_control_changed/executive/nation:20@2032-04-01T00:00:00`
```

With `--narrative`, `--min-significance` filters the narrative events, and the interval sections
list only the events behind them that `--constituents` keeps; an interval with nothing to list
shrinks to one line. `events --narrative` thus reads as a digest, with `--constituents evidence`
or `all` filling in the drill-down. The takeovers a listed `faction.takeover_wave` groups are
listed by headline only, as members of the wave, and their own evidence is left out. The rules'
thresholds come from the settings file
([configuration](../configuration.md)); when they differ from the defaults, the section says so.
The rules themselves are in the [`narrative`](../../src/tinarrative/narrative/) package.

## JSON output

`--format json` prints one object, built by
[`rendering/json_report.py`](../../src/tinarrative/rendering/json_report.py):

- `campaign`: the chosen campaign, as `campaigns --format json` lists it;
- `inputs`, `duplicates`, `skipped`: what was read, merged and skipped;
- `saves`: the saves in order, each with its [situation report](#situation-report);
- `intervals`: per interval, its dates, change count, `events`, `inferred`, `state_changes` and
  `omitted` counts;
- `narrative`, `narrative_omitted`: the narrative events and how many were filtered out; a
  takeover a listed `faction.takeover_wave` groups keeps only its `id`, `event_type`,
  `significance`, span, `roles` and `intervals`, plus `member_of` naming the wave;
- `settings`, `min_significance`, `constituents`: how the report was built;
- `glossary`: names for the entities the document references by ID only.

Members that an option did not ask for are `null`. Events are serialized by
[`model/events.py`](../../src/tinarrative/model/events.py) and state changes as in
`save diff --format json`. Every event and narrative event carries its `significance` level and a
`score` from 0 to 100 that always lies in that level's band (`trivial` 0–24, `minor` 25–49, `major`
50–74, `campaign_defining` 75–100). An event whose type has no stake scores the midpoint of its level's
band. For the types the stake scales (nation, territory, control-point and organization events, wars), the score
moves with the share of the world the event touched, and the level follows the score; such an event also carries
a `significance_basis` with its `base` score, the `measure` (`power`, `population` or `organization`), the
`share`, the `scale` it added and the stake `entities` (plus a `bonus` for a war between nuclear-armed nations).
The [narrator package](#narrator-package) keeps the `score` and drops the basis. The reference shares and the
clamp are [settings](../configuration.md). Without `--narrative`, every event keeps its source locations in the
saves.

### Narrator package

`events --format json --narrative` is the narrator package, the input of [`narrate`](narrate.md)
and of an LLM narrator ([narrator](../narrator.md)). It holds the narrative events, a situation
report per save, the glossary and, with `--constituents all` or `evidence`, the events the listed
narrative events are built from. It carries IDs but no file paths and no source locations, and leaves
out detail a narrator does not need. `--changes` is a usage error with it.

To audit a package, run the same saves with `--inferred` instead of `--narrative` and without
`--min-significance`: every ID in the package resolves there, with its sources. The package form
is built by `_narrator_package` in
[`rendering/json_report.py`](../../src/tinarrative/rendering/json_report.py), and the glossary by
[`narrative/glossary.py`](../../src/tinarrative/narrative/glossary.py).

### Situation report

Each save's `situation` is a digest of that one save: per nation its controlling factions'
shares, federation, wars, regions, population, statistics, armies and space assets; the
federations and wars; per faction its habs, fleets and ships; and world totals such as
milestones, nuclear and climate figures and the largest spaceports. It states literal values and
counts, never an inference, and a value the save does not establish is `{"unknown": <reason>}`.
It is built by [`narrative/situation.py`](../../src/tinarrative/narrative/situation.py).

## Exit codes

| Code | When |
| --- | --- |
| 0 | The report was printed. Files skipped inside a named directory do not change it. |
| 2 | Usage error: fewer than two usable saves; several campaigns or an unmatched `--campaign` outside a terminal; a cancelled picker; an unknown option value; or `--changes` with `--narrative --format json`. |
| 4 | A named path cannot be read, or a named directory holds no files or no usable save. |
| 5 | A named file is not a supported save or has no parseable game time. |
| 8 | The settings file cannot be read or is not valid settings. Nothing is printed on stdout. |

## Examples

```sh
tinarrative events ~/saves --campaign latest > report.md
tinarrative events ~/saves --narrative --min-significance major --constituents evidence
tinarrative events ~/saves --narrative --format json > package.json
```
