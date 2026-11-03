# Configuration

The narrative rules' thresholds and windows, and the budget and provider of `narrate`, are
runtime settings with built-in defaults (`src/tinarrative/config.py`). The `narrative` tables change
what `events --narrative` (and `narrate` from saves) builds and nothing else; the `narrator` table
changes how `narrate` cuts, requests and sends a package, and never what `events` builds.

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

[narrator.profiles.local]
provider = "ollama"
model = "..."
```

[`configuration.example.toml`](configuration.example.toml) lists every key at its default, with
its meaning; copy it and keep only the keys you change. A test keeps it equal to the defaults.

Validation is strict, and every error message names the key. Each of these is an error:

- an unknown table or key;
- a value of the wrong type. An integer key takes only an integer (`true` and `3.0` are errors). A
  number key takes an integer or a float, never `true`. A string key takes a non-empty string;
- a string outside its choices;
- a value below its minimum.

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
| `narrative.geopolitics.metric_shifts_max` | 12 | 0 | A geopolitical development keeps at most this many `metric_shifts` entries: those of its role nations first, then `numNuclearWeapons`, then the largest `relative_change` (entries without one last). The rest are counted as `metric_shifts_omitted` ([events](commands/events.md#narrative-events)). |
| `narrative.space.campaign_gap_days` | 365 | 0 | Battle outcomes of one killer and victim pair chain into one `faction.space_campaign` while each follows the previous one this soon. |
| `narrative.space.colonisation_window_days` | 180 | 0 | First habs on new bodies of one faction this soon after the first form one `faction.colonisation_wave`. |
| `narrative.space.buildup_min_ships` | 5 | 2 | A `faction.fleet_buildup` needs at least this many ships of one hull appearing for one faction in one interval. |
| `narrative.nation_metrics.band_hold_days` | 180 | 0 | A band shift (`nation.unrest_shift`, `nation.government_shift`, ...) needs its band crossing to still hold in the next situation report when that report is dated this soon after it; a later report cannot refute it, and a crossing in the last interval is kept and `open` ([events](commands/events.md#narrative-events)). |
| `narrative.nation_metrics.buildup_min_armies` | 2 | 1 | A `nation.military_buildup` or `nation.demobilization` needs the nation's standard armies in the situation reports to move by at least this many within a year ([events](commands/events.md#narrative-events)). |
| `narrative.nation_metrics.space_assets_window_days` | 365 | 0 | Growth of one nation's boost or mission control (`nation.space_assets_changed`) chains into one `nation.space_program_growth` while each follows the previous one this soon. |
| `narrative.nation_metrics.nuclear_window_days` | 365 | 0 | Changes of one nation's nuclear arsenal chain into one `nation.nuclear_armament`, `nation.nuclear_buildup` or `nation.nuclear_disarmament` while each follows the previous one this soon ([events](commands/events.md#narrative-events)). |
| `narrative.nation_metrics.nuclear_buildup_min` | 5 | 1 | A `nation.nuclear_buildup` gains at least this many weapons, or half the arsenal it started from. |
| `narrative.nation_metrics.ranking_top_n` | 10 | 1 | `world.ranking_changed` reports nations entering or leaving the top this many by GDP, strength, boost or mission control; `nation.space_program_growth` is `major` when its nation enters that top by boost or mission control, and each situation report lists this many `spaceports`. Values above 20, the places `nation.rank_changed` reports, count as 20. |

The `councilors` keys ([councilors](commands/councilors.md)):

| Key | Default | Minimum | Meaning |
| --- | --- | --- | --- |
| `councilors.rivals_per_faction` | 2 | 0 | The most prominent councilors of each other human faction that join the player's councilors in the dossier. |
| `councilors.min_tenure_days` | 365 | 0 | A councilor is selected only after being employed this many game days. |
| `councilors.missions_per_councilor` | 3 | 0 | A player councilor's dossier keeps this many mission and target groups, the most frequent first. |
| `councilors.article_words` | 220 | 1 | The article length each request asks for; also carried in the dossier header. |

The `narrator` keys ([narrate](commands/narrate.md), [architecture 20.3](architecture.md#203-token-budget-and-chapters)):

| Key | Default | Minimum | Meaning |
| --- | --- | --- | --- |
| `narrator.max_input_tokens` | 200000 | 1000 | One request's estimated input, system prompt, request block and chapter package together, stays within this many tokens. |
| `narrator.chars_per_token` | 3 | 1 | The estimate divides the request's characters by this; a lower value is more conservative. |
| `narrator.quarter_span_days` | 730 | 0 | A campaign spanning this many game days or fewer is told by quarter (unless `--period` is given). A derived period is made coarser chapter by chapter where the saves are further apart than it runs ([narrate](commands/narrate.md#chapter-plan)). |
| `narrator.half_span_days` | 1825 | 0 | A longer campaign spanning this many game days or fewer is told by half year; a longer one by year. |
| `narrator.recalled_developments` | 40 | 0 | Each chapter is reminded of at most this many developments of earlier chapters (`major` and above; the most significant, then the most recent, are kept and the rest counted), so the model can refer back to them without retelling them. 0 turns the reminder off; a larger value costs input tokens in every later chapter. |
| `narrator.top_economies` | 10 | 0 | A chapter's situation reports keep the nations the chapter references and this many more, the largest by `GDP` among the nations that hold a region in that save. |

### Narrator provider and profiles

These keys matter only to `narrate --send` and `councilors --send` ([sending](commands/narrate.md#sending),
[architecture 20.5](architecture.md#205-providers)). An optional key without a default is unset
until a file, a profile or a flag sets it.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `narrator.provider` | string: `anthropic`, `openai`, `openrouter`, `ollama` | unset | The API the requests are sent to: Anthropic Messages, OpenAI Chat Completions (or any server implementing it), OpenRouter Chat Completions, Ollama's native chat. |
| `narrator.model` | string | unset | The model every request names. There is no built-in model, so a stale ID is never sent by default. |
| `narrator.base_url` | string, `http://` or `https://` | unset: the provider's public API, for OpenRouter `https://openrouter.ai/api/v1`, for Ollama `http://localhost:11434` | The API root, for a gateway, a compatible server or a remote Ollama. |
| `narrator.api_key_env` | string | unset | The **name** of the environment variable holding the API key. Required for `anthropic`, `openrouter`, and for `openai` without a `base_url`. |
| `narrator.max_output_tokens` | integer, minimum 1 | 16000 | One completion stops at this many tokens; one that reaches it fails its chapter. Models that think count their thinking here. |
| `narrator.context_window` | integer, minimum 1 | unset | The model's context window, when stated. `max_input_tokens + max_output_tokens` above it is rejected before sending. |
| `narrator.temperature` | number, minimum 0 | unset | Sent with each request when set. Current Claude models reject it. |
| `narrator.timeout_seconds` | integer, minimum 1 | 600 | One HTTP request is abandoned after this many seconds. Raise it for a slow local model. |

**Profiles.** A table `[narrator.profiles.NAME]` names a set of values. A profile may set any of
`provider`, `model`, `base_url`, `api_key_env`, `max_input_tokens`, `max_output_tokens`,
`chars_per_token`, `context_window`, `temperature` and `timeout_seconds`. These are validated as the
keys of the same name; any other key is an error. `narrate --profile NAME` applies the profile over
the `[narrator]` keys, and the override flags apply over both
([narrate](commands/narrate.md#provider-and-budget)). Without `--profile`, the `[narrator]` keys
apply as they are.

```toml
[narrator.profiles.claude]
provider = "anthropic"
model = "claude-sonnet-5-5"
api_key_env = "ANTHROPIC_API_KEY"

[narrator.profiles.local]
provider = "ollama"
model = "..."
max_input_tokens = 24000
max_output_tokens = 4000
context_window = 32768
timeout_seconds = 1800

[narrator.profiles.openrouter]
provider = "openrouter"
model = "..."
api_key_env = "OPENROUTER_API_KEY"
```

**Keys.** An API key is never a setting: a settings file names only the environment variable, and
the key is read from it at send time. The key never appears in the output or in a log.

The evidence behind the narrative rules' defaults is in
[sources for higher-level events](game-data-notes/higher-level-event-sources.md)
(*Narrative rules (geopolitics)* and *Narrative rules (space)*).

## Reproducibility

`events --format json --narrative` records the effective `narrative` settings, every key included,
as `settings`. The Markdown narrative section names every `narrative` key that differs from its
default. `narrate --output` records in `plan.json` the `narrator` settings the plan depends on;
each `responses/NN.json` records the provider, model, output limit and temperature it was sent
with.

## Errors

A settings file that cannot be read, is not valid TOML or does not match the schema stops the
command with exit code 8, before any save is read; nothing is printed on stdout. Debug logging
names the settings source (`flag`, `env` or `default`) and the file's base name only.
