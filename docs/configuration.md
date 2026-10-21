# Configuration

The narrative rules' thresholds and windows, and the budget of `narrate`'s chapter planner, are
runtime settings with built-in defaults (`src/tinarrative/config.py`). The `narrative` tables change
what `events --narrative` (and `narrate` from saves) builds and nothing else; the `narrator` table
changes how `narrate` cuts and requests a package, and never what `events` builds.

## Where settings come from

1. `--config <file>` on the command (`events`, `narrate`);
2. else the file named by the `TINARRATIVE_CONFIG` environment variable (an empty value counts as
   unset);
3. else the defaults.

The file is read and validated on every run of the command, whether or not `--narrative` is given.

## File format

A UTF-8 TOML file whose tables mirror the settings. A file names only the keys it changes; every
other key keeps its default.

```toml
[narrative.geopolitics]
top_gdp_nations = 5
expansion_gap_days = 730

[narrator]
max_input_tokens = 32000
```

[`configuration.example.toml`](configuration.example.toml) lists every key at its default, with
its meaning; copy it and keep only the keys you change. A test keeps it equal to the defaults.

Validation is strict: an unknown table or key, a value that is not an integer (`true` and `3.0`
included) or a value below its minimum is an error, and the message names the key.

## Keys

All windows are in game days. A window is measured from the earliest date an event can have
had (its record date, else the start of its interval), so consecutive saves always fall within one
another's window ([architecture 11.3](architecture.md#113-first-catalogue)).

| Key | Default | Minimum | Meaning |
| --- | --- | --- | --- |
| `narrative.geopolitics.top_gdp_nations` | 10 | 1 | A `faction.takeover` is `campaign_defining` when its nation ranks this high or higher by `GDP` in the report after the takeover's first interval. |
| `narrative.geopolitics.takeover_consolidation_days` | 180 | 0 | Control changes of one nation to the same faction this soon after the first join one takeover; its control-point gains are attached over the same window. |
| `narrative.geopolitics.takeover_precursor_days` | 90 | 0 | The faction's unrest attempts and the nation's unrest and opinion shifts this long before a takeover are attached as precursors. |
| `narrative.geopolitics.ledger_window_days` | 28 | 0 | A `Coup`, `Purge` or `Crackdown` charge is attached to a takeover when dated this long before it at most (the assignment-to-outcome bound of architecture 11.3). |
| `narrative.geopolitics.expansion_gap_days` | 365 | 0 | Gains of one nation chain into one `nation.expansion` while each follows the previous one this soon. |
| `narrative.geopolitics.release_window_days` | 180 | 0 | A released or breakaway nation's own events this soon after its independence are attached. |
| `narrative.geopolitics.transformation_window_days` | 120 | 0 | Statistic shifts of one nation this soon after the first form one `nation.transformation`. |
| `narrative.space.campaign_gap_days` | 365 | 0 | Battle outcomes of one killer and victim pair chain into one `faction.space_campaign` while each follows the previous one this soon. |
| `narrative.space.colonisation_window_days` | 180 | 0 | First habs on new bodies of one faction this soon after the first form one `faction.colonisation_wave`. |
| `narrative.space.buildup_min_ships` | 5 | 2 | A `faction.fleet_buildup` needs at least this many ships of one hull appearing for one faction in one interval. |

The `narrator` keys ([narrate](commands/narrate.md), [architecture 20.3](architecture.md#203-token-budget-and-chapters)):

| Key | Default | Minimum | Meaning |
| --- | --- | --- | --- |
| `narrator.max_input_tokens` | 200000 | 1000 | One request's estimated input, system prompt, request block and chapter package together, stays within this many tokens. |
| `narrator.chars_per_token` | 3 | 1 | The estimate divides the request's characters by this; a lower value is more conservative. |
| `narrator.quarter_span_days` | 730 | 0 | A campaign spanning this many game days or fewer is told by quarter (unless `--period` is given). |
| `narrator.half_span_days` | 1825 | 0 | A longer campaign spanning this many game days or fewer is told by half year; a longer one by year. |
| `narrator.recalled_developments` | 40 | 0 | Each chapter is reminded of at most this many developments of earlier chapters (`major` and above; the most significant, then the most recent, are kept and the rest counted), so the model can refer back to them without retelling them. 0 turns the reminder off; a larger value costs input tokens in every later chapter. |
| `narrator.top_economies` | 10 | 0 | A chapter's situation reports keep the nations the chapter references and this many more, the largest by `GDP`. |

The evidence behind the narrative rules' defaults is in
[sources for higher-level events](game-data-notes/higher-level-event-sources.md)
(*Narrative rules (geopolitics)* and *Narrative rules (space)*).

## Reproducibility

`events --format json --narrative` records the effective `narrative` settings, every key included,
as `settings`. The Markdown narrative section names every `narrative` key that differs from its
default. `narrate --output` records the `narrator` settings in `plan.json`.

## Errors

A settings file that cannot be read, is not valid TOML or does not match the schema stops the
command with exit code 8, before any save is read; nothing is printed on stdout. Debug logging
names the settings source (`flag`, `env` or `default`) and the file's base name only.
