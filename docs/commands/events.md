# `tinarrative events`

<!-- generated: synopsis events -->
```
tinarrative events [--campaign SELECTOR] [--format {markdown,json}]
                   [--min-significance {trivial,minor,major,campaign_defining}]
                   [--constituents {all,evidence,none}] [--period {year,half,quarter}] [--inferred]
                   [--changes] [--narrative] [--config FILE] [--jobs N]
                   PATH [PATH ...]
```
<!-- end generated -->

Reports what happened in one campaign between every pair of consecutive saves: the events found in each interval and
how significant each one is. On request it adds the events inferred from them, the narrative events that span the
whole campaign, and the literal state changes. Use it to read a campaign's analysis yourself, to check what
[`narrate`](narrate.md) will tell, or to build a narrator package for your own model. Saves and campaigns are chosen as
described in [saves and campaigns](README.md#saves-and-campaigns); at least two usable saves are needed.

## Examples

```sh
# Everything that happened in the campaign being played.
tinarrative events ~/saves --campaign latest > report.md

# A digest: the major narrative events, each with the evidence behind it.
tinarrative events ~/saves --narrative --min-significance major --constituents evidence

# The narrator package, for narrate --package or your own model.
tinarrative events ~/saves --narrative --format json > package.json

# Audit a package: every ID in it resolves here, with its sources.
tinarrative events ~/saves --inferred --format json > audit.json
```

## Options

<!-- generated: options events -->
| Option | Meaning |
| --- | --- |
| `PATH...` | Save files or directories, in any order; a directory is read one level deep. |
| `--campaign SELECTOR` | The campaign to use when the saves hold several: a key, a unique key prefix, a listing number or 'latest'. |
| `--format markdown\|json` | Report format (default markdown). |
| `--min-significance trivial\|minor\|major\|campaign_defining` | Lowest significance listed; with --narrative, of the narrative events (default trivial). |
| `--constituents all\|evidence\|none` | With --narrative, which events behind the listed narrative events to list (default none). |
| `--period year\|half\|quarter` | How the Markdown narrative section is grouped (default year). |
| `--inferred` | Also list the events inferred in each interval, with the results they rest on. |
| `--changes` | Also list every literal state change under its interval; not with --narrative --format json. |
| `--narrative` | Also join the whole campaign's events into narrative events; implies --inferred. |
| `--config FILE` | TOML settings file (default: $TINARRATIVE_CONFIG, else the built-in settings). |
| `--jobs N` | Worker processes; 1 runs everything in one process; the output is the same (default: processing.jobs). |
<!-- end generated -->

The thresholds of the narrative rules are [settings](../configuration.md); a report built with non-default settings
says so.

## Output

The Markdown report has four parts:

- `## Campaign`: the chosen campaign.
- `## Saves`: the saves in game-time order, with merged copies and skipped files.
- `## Narrative` (with `--narrative`): the narrative events by period.
- `## Intervals`: one section per pair of saves, with its inferred events (with `--inferred`), its analyzer results by
  category, and its state changes (with `--changes`).

Entities are named as `Name (domain:key)`, such as `Germany (nation:3857)`. Every event has an ID, such as
`region.nation_changed/region:42@2032-07-01T00:00:00`, and an inferred or narrative event lists the IDs it rests on:

```
- `2032-01-01T00:00:00` to `2032-07-01T00:00:00` (open): <description> (inferred, confidence `medium`, significance `major`)
  - roles: actor: Fixture Faction (faction:7); target: Fixture Nation (nation:20)
  - from `faction.nation_control_changed/executive/nation:20@2032-04-01T00:00:00`
```

`(open)` marks a narrative event still under way in the last save. With `--narrative`, the interval sections list
only the events that `--constituents` keeps.

`--format json` prints the same report as one document, with a situation report per save and a glossary of the
entities it references. Every event carries a `significance` level and a `score` from 0 to 100.

### Narrator package

`events --narrative --format json` is the narrator package: the input of [`narrate --package`](narrate.md) and of any
LLM narrator ([narrator](../narrator.md)). It holds the narrative events, a situation report per save, the glossary
and, with `--constituents all` or `evidence`, the events behind them, but no file paths or locations in the saves.

## Exit codes

<!-- generated: exit-codes events -->
| Code | When |
| --- | --- |
| 0 | The report was printed. |
| 2 | Usage error, fewer than two usable saves, or no campaign chosen. |
| 4 | A named path cannot be read, or a named directory holds no usable save. |
| 5 | A named file is not a supported save or has no game time. |
| 8 | The settings file cannot be read or is not valid settings. |
<!-- end generated -->
