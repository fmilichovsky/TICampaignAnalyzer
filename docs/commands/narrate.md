# `tinarrative narrate`

```
tinarrative narrate <path> [<path>...] [--campaign <selector>] [--min-significance <level>] [options]
tinarrative narrate --package <file>|- [options]

options: [--period year|half|quarter] [--audience public|insider] [--citations footnotes|none]
         [--style chronicle|headlines] [--length <words>] [--focus <name>] [--output <dir>] [--config <file>]
```

Cuts a campaign's [narrator package](events.md#narrator-package) into chapters, each small enough
for one model request, and builds the request of every chapter
([architecture 20.1–20.4](../architecture.md#201-command-and-data-flow)). It contacts nothing:
sending the requests to a model is a later step. The requests can be reviewed, diffed or run by
hand against any model.

## Input

- **Saves.** `narrate` takes the same save inputs as [`events`](events.md) (files, directories,
  `--campaign`, the campaign picker) and builds the package in-process, as
  `events --narrative --include-constituents --format json --min-significance <level>` does.
  `--min-significance` defaults to `major`. The atomic stream keeps only the constituents of the
  listed developments.
- **`--package FILE`** reads a finished package instead; `-` reads it from stdin. The package is
  narrated as it was built, so save paths, `--campaign` and `--min-significance` are usage errors
  with it.

Given the same package, both inputs produce the same plan and the same request bytes.

## Request parameters

Each request opens with a request block that the [prompt](../narrator.md) reads. The block lists
only the keys that are set, in a fixed order:

| Key | Set by | Value |
| --- | --- | --- |
| `chapter` | program | `2 of 5` |
| `part` | program | `whole` (one chapter), `first`, `middle` or `last` |
| `covers` | program | the chapter's opening and closing save dates, `2032-01-01 to 2032-07-01` |
| `period` | `--period`, else derived | span of the first to last save: up to `narrator.quarter_span_days` → `quarter`, up to `narrator.half_span_days` → `half`, else `year` |
| `audience`, `citations`, `style` | the options of the same name | left to the prompt's defaults when not given |
| `length` | `--length WORDS` | the chapter's share of the whole history, `about 450 words` |
| `focus` | `--focus`, else derived | the player faction (`player_faction_name` of the last save) for `--audience insider` |

**Length.** `--length` is a target for the whole history. Each chapter gets a share in
proportion to the weight of the developments it holds: `campaign_defining` 4, `major` 2, `minor`
and `trivial` 1. If no chapter holds a development, the shares follow the number of intervals.
The shares are whole words and add up to the target exactly (largest remainder). A chapter with a
zero share gets no `length` key.

## Chapter plan

A chapter is a contiguous run of the package's intervals made of whole periods. It opens on the
save before its first interval and closes on the save of its last, so consecutive chapters share
a save. An interval belongs to the period of its opening save. A development belongs to the
chapter holding the interval its start lies in. A development with an unknown start belongs to
the chapter holding the first interval it lists.

**Estimate.** A request's input is estimated as the characters of its system prompt and user
message, divided by `narrator.chars_per_token` and rounded up. No provider is asked, so the plan
depends only on the package and the settings. The planner estimates each request with the values
not yet known at their largest (chapter count, part name, length share), so a written request is
never larger than its planned estimate.

**Greedy.** The planner walks the periods in order and adds the next period to the current
chapter while the estimate stays within `narrator.max_input_tokens`. A period that does not fit
on its own is reduced in a fixed order, and the step is recorded for that chapter:

1. `atomic_dropped`: the period becomes one chapter without its atomic stream. The chapter keeps
   its developments, situations and glossary.
2. `split`: the period is split at save boundaries into consecutive chapters, each without atomic
   stream. `covers` tells the model where a period continues across chapters.
3. If a single interval still does not fit, the command stops before writing anything (exit 2)
   and names the interval and the tokens it needs.

Developments are never dropped and the significance level is never raised to make a chapter fit.

## Chapter package

A chapter package has the schema of the narrator package, restricted to the chapter. It selects
entries and never rewrites one, so an ID means the same event in the chapter package and in the
full package:

- `narrative`: the developments that belong to the chapter, in package order;
- `saves`: the opening and the closing save. Their situation's `nations` are reduced to the
  nations the chapter references, plus the `narrator.top_economies` largest by `GDP` in that save.
  Every other member of the situation is unchanged;
- `intervals`: the chapter's intervals. Their `events` and `inferred` keep only the events the
  chapter's developments and its `continuing` developments are built from, followed transitively,
  and are empty when the atomic stream was left out. Their `omitted` counts are the package's;
- `glossary`: the entries still referenced, and the regions of the nations among them;
- every other member (`campaign`, `settings`, the filter fields and counts) as in the package;
- `chapter`: `index`, `count`, `part` and `covers` (`from` and `to`, the two save dates);
- `continuity`, built from the package and never from earlier prose:
  - `continuing`: the full records of earlier chapters' developments that are `open`, or that
    list one of this chapter's intervals;
  - `earlier`: `id`, `event_type`, `significance`, `start`, `end` and `roles` of other earlier
    developments at `major` and above. At most `narrator.recalled_developments` are kept: the most
    significant first, then the latest. They are listed in package order;
  - `earlier_omitted`: how many were left out of `earlier` by that limit.

## Output

stdout always gets a short plan: per chapter its index and part, covers, periods, the number of
developments, continuing and recalled developments, the estimate and any reduction. With
`--output DIR`, the command writes:

```text
DIR/
  plan.json         # the plan
  requests/01.json  # one request per chapter: {"system": ..., "messages": [...]}
```

`plan.json` holds the prompt version (SHA-256 of the prompt), the SHA-256 of the package (compact
JSON), the narrator settings, the request parameters, and per chapter its `index`, `part`,
`covers`, `periods`, the numbers of `intervals`, `developments`, `continuing` and `recalled`, the
`estimate`, the `reduction` (`null`, `atomic_dropped` or `split`) and the SHA-256 of its request
file. The files hold no time and no path, so the same package and settings give byte-identical
files. Request files are numbered with two digits (more when there are more chapters). A numbered
request file left over from a longer plan is removed; other files in `DIR` are left alone.

With `--log-level info`, the run logs the save pipeline's lines (as `events`) or the package's
size, then the number of chapters and developments, the largest estimate and the number of
reduced chapters. It never logs a request or a string from the package.

## Exit codes

| Code | When |
| --- | --- |
| 0 | The plan was printed and, with `--output`, written. |
| 2 | Usage error: no save paths and no `--package`; `--package` with save paths, `--campaign` or `--min-significance`; a package with no interval; a single interval over `narrator.max_input_tokens` (nothing written); the save input errors of `events`. |
| 4 | A save or the `--package` file cannot be read. |
| 5 | A save is not a supported save, or the package is not UTF-8 JSON or not a narrator package. |
| 8 | The settings file cannot be read or is not valid settings. Nothing is printed on stdout. |
| 9 | `--output` cannot be written. The plan is not printed. |
