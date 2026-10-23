# `tinarrative narrate`

```
tinarrative narrate <path> [<path>...] [--campaign <selector>] [--min-significance <level>] [--constituents all|evidence|none] [options]
tinarrative narrate --package <file>|- [options]
tinarrative narrate --assemble <dir>

options: [--period year|half|quarter] [--audience public|insider] [--citations footnotes|none]
         [--style chronicle|headlines] [--length <words>] [--focus <name>] [--output <dir>] [--config <file>]
         [--send] [--force] [--profile <name>] [--provider anthropic|openai|ollama] [--model <id>] [--base-url <url>]
         [--max-input-tokens <tokens>] [--max-output-tokens <tokens>] [--temperature <t>]
```

Cuts a campaign's [narrator package](events.md#narrator-package) into chapters, each small enough
for one model request, and builds the request of every chapter
([architecture 20.1–20.5](../architecture.md#201-command-and-data-flow)). Without `--send` it
contacts nothing, and the requests can be reviewed, diffed or run by hand against any model.
With `--send` it sends them to the configured provider, writes the responses and assembles them
into one footnoted history with a citation audit and a run manifest. `--assemble DIR` assembles a
directory written earlier without sending anything.

## Input

- **Saves.** `narrate` takes the same save inputs as [`events`](events.md) (files, directories,
  `--campaign`, the campaign picker) and builds the package in-process, as
  `events --narrative --constituents <mode> --format json --min-significance <level>` does.
  `--min-significance` defaults to `major` and `--constituents` to `evidence`: the atomic stream
  keeps only the constituents of the listed developments that are narrator evidence.
- **`--package FILE`** reads a finished package instead; `-` reads it from stdin. The package is
  narrated as it was built, so save paths, `--campaign`, `--min-significance` and `--constituents`
  are usage errors with it.

Given the same package, both inputs produce the same plan and the same request bytes.

## Request parameters

Each request opens with a request block that the [prompt](../narrator.md) reads. The block lists
only the keys that are set, in a fixed order:

| Key | Set by | Value |
| --- | --- | --- |
| `chapter` | program | `2 of 5` |
| `part` | program | `whole` (one chapter), `first`, `middle` or `last` |
| `covers` | program | the chapter's opening and closing save dates, `2032-01-01 to 2032-07-01` |
| `period` | `--period`, else derived | span of the first to last save: up to `narrator.quarter_span_days` → `quarter`, up to `narrator.half_span_days` → `half`, else `year`; a derived period is made coarser chapter by chapter where the saves are too sparse for it (see [Chapter plan](#chapter-plan)) |
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
a save. An interval belongs to the period of its closing save. A development belongs to the chapter
holding the interval of its start when that is a recorded date, otherwise the interval of its end,
the one by which it was known. A development with no usable date belongs to the chapter holding
the first interval it lists.

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

**Sparse saves.** A period cannot be told from saves further apart than it runs: the model would
divide an interval it knows nothing inside of. A period whose intervals are longer, by median, than
the period's longest calendar run (`quarter` 92 days, `half` 184, `year` 366) is told at the next
coarser period, together with every other interval of that coarser period; this repeats until no
period but a year is too sparse. Calendar periods nest, so the periods never overlap. A chapter
holds one period, so a chapter ends where the period changes even when the next period would fit
the budget; each chapter's request carries its own `period`. An explicit `--period` is never made
coarser: the command keeps it and warns on stderr, naming the periods the saves are too sparse for.

## Chapter package

A chapter package has the schema of the narrator package, restricted to the chapter. It selects
entries and never rewrites one, so an ID means the same event in the chapter package and in the
full package:

- `narrative`: the developments that belong to the chapter, in package order;
- `saves`: the opening and the closing save. Their situation's `nations` are reduced to the
  nations the chapter references, plus the `narrator.top_economies` largest by `GDP` in that save.
  A nation that holds no region in that save never counts among the largest economies, and is kept
  only when the chapter's developments, its `continuing` developments or its atomic events
  reference it; a mention in an `earlier` digest does not keep it. Every other member of the
  situation is unchanged;
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

## Provider and budget

The `narrator` settings ([configuration](../configuration.md#narrator-provider-and-profiles))
choose the provider, the model and the budget. They are resolved in this order, each step over the
previous one:

1. the `[narrator]` keys of the settings file, else their defaults;
2. the profile `[narrator.profiles.NAME]` given with `--profile NAME`. An unknown profile is a
   usage error that lists the defined ones;
3. the flags `--provider`, `--model`, `--base-url`, `--max-input-tokens`, `--max-output-tokens` and
   `--temperature`. They are validated as the keys of the same name; an invalid value is a usage
   error that names the flag.

`max_input_tokens` and `chars_per_token` shape the plan, so a profile or a flag can change it. The
other provider keys never change the plan or the request bytes.

## Sending

`--send` sends each chapter's request to the provider, in chapter order. **It hands the campaign to
the provider, a third party unless the provider runs on your machine** (Ollama, or an
OpenAI-compatible server at a local `base_url`). The package carries no file paths, but it does
carry the campaign: faction, nation and leader names and the whole history.

Before anything is read or sent, `--send` requires all of the following:

- `--output DIR`;
- a provider and a model. There is no default model;
- for `anthropic`, and for `openai` without a `base_url`, an `api_key_env` naming the environment
  variable that holds the key;
- the variable that `api_key_env` names, when one is named, set and not empty;
- `max_input_tokens + max_output_tokens` no larger than `context_window`, when one is set.

A missing item is a usage error (exit 2) and nothing is contacted.

The key is read only from that environment variable. It never appears in a settings file, in
the output or in a log.

| Provider | Endpoint (`base_url` default) | Request |
| --- | --- | --- |
| `anthropic` | `POST {base_url}/v1/messages` (`https://api.anthropic.com`) | `x-api-key`, `anthropic-version: 2023-06-01`; `model`, `max_tokens`, `system`, one user message |
| `openai` | `POST {base_url}/chat/completions` (`https://api.openai.com/v1`) | `Authorization: Bearer` when a key is set; `model`, system and user messages, `max_completion_tokens` |
| `ollama` | `POST {base_url}/api/chat` (`http://localhost:11434`) | `Authorization: Bearer` when a key is set; `stream: false`, `options.num_ctx` = `max_input_tokens + max_output_tokens`, `options.num_predict` = `max_output_tokens` |

Every provider gets `temperature` only when it is set; current Claude models reject it. With a
`base_url`, `openai` reaches any server that implements Chat Completions (hosted gateways, LM
Studio, vLLM). Ollama is called through its native API because only that API sets the context
length per request. A context smaller than the request truncates the input silently.

**Finish.** Each completion's stop reason is mapped to a finish:

| Finish | Anthropic `stop_reason` | OpenAI `finish_reason` | Ollama `done_reason` |
| --- | --- | --- | --- |
| `complete` | `end_turn`, `stop_sequence` | `stop` | `stop` |
| `length` | `max_tokens`, `model_context_window_exceeded` | `length` | `length` |
| `refused` | `refusal` | `content_filter`, or a `refusal` message | |
| `other` | anything else | anything else | anything else |

A `length` or `refused` completion fails its chapter and is not written: a chapter is never kept
short. An `other` completion is written with its finish.

**Retries.** HTTP 408, 409, 429 and 5xx, and a failed connection, are retried up to three times.
Each retry waits as long as `Retry-After` asks (seconds or an HTTP date, at most 60 seconds), else
2, 4 and then 8 seconds. A timeout (`narrator.timeout_seconds`) and every other status fail at once.

**Resume.** Before a chapter is sent, its stored `responses/NN.json` is checked. The response is
kept, and the chapter is not sent again, when all of these hold:

- its `request_sha256` is the request's;
- its `provider`, `model`, `max_output_tokens` and `temperature` are those of this run;
- its `finish` is `complete` or `other`.

An interrupted or partly failed run therefore resumes where it stopped. A change to the plan or
to a request re-sends only the chapters it changes, while a different model or output limit
re-sends all of them. `--force` sends every chapter again, and needs `--send`.

**Failure.** The run stops at the first failed chapter (exit 10). The error message names the
chapter, the provider and the reason: the HTTP status with the provider's error message shortened,
no response, an invalid response, the output limit or a refusal. The chapters completed before it
keep their responses. No history or manifest is written, and those of an earlier run are left
alone.

## Output

stdout always gets a short plan: per chapter its index and part, covers, periods (with
`saves too far apart for a quarter` when the chapter's period was made coarser), the number of
developments, continuing and recalled developments, the estimate and any reduction. With
`--output DIR`, the command writes:

```text
DIR/
  plan.json          # the plan
  requests/01.json   # one request per chapter: {"system": ..., "messages": [...]}
  responses/01.json  # with --send: one per completed chapter
  history.md         # with --send, once every chapter has a response
  manifest.json      # the run record, written with history.md
```

`plan.json` holds the prompt version (SHA-256 of the prompt), the SHA-256 of the package (compact
JSON), the narrator settings, the request parameters (`period` is the requested or derived one,
before any chapter makes it coarser), and per chapter its `index`, `part`,
`covers`, `periods`, its `period` and `period_basis` (`requested` for `--period`, `campaign_span`
for the period derived from the span, `save_spacing` for one made coarser because the saves are too
sparse), the numbers of `intervals`, `developments`, `continuing` and `recalled`, the
`estimate`, the `reduction` (`null`, `atomic_dropped` or `split`) and the SHA-256 of its request
file. The files hold no time and no path, so the same package and settings give byte-identical
files. Request files are numbered with two digits (more when there are more chapters). A numbered
request file left over from a longer plan is removed; other files in `DIR` are left alone.
`plan.json` records only the settings the plan depends on (`max_input_tokens`, `chars_per_token`,
the span thresholds, `recalled_developments`, `top_economies`).

With `--send`, stdout adds one line per chapter (`sent` or `kept`, its finish, the input and
output tokens the provider reports and the plan's estimate), a line counting the responses written
and kept, and a line naming `history.md` and `manifest.json`. Each `responses/NN.json` holds:

| Member | Value |
| --- | --- |
| `index` | the chapter |
| `request_sha256` | the SHA-256 of `requests/NN.json`, as in `plan.json` |
| `provider`, `model`, `max_output_tokens`, `temperature` | what the request was sent with |
| `reported_model` | the model the provider reports, or `null` |
| `finish` | `complete` or `other` |
| `estimate` | the plan's input estimate |
| `input_tokens`, `output_tokens` | the counts the provider reports, or `null` |
| `text` | the completion |

Numbered responses beyond the plan's chapters are removed when sending starts. A stored response
that matches its request is kept (see **Resume**). Any other response is replaced when its
chapter is sent.

## History and audit

Once every chapter has a response, the run assembles `history.md`. It opens with a header:

```markdown
# Campaign history

- Provider: anthropic
- Model: claude-model-2026 (requested claude-model)
- Prompt version: 8903306c…
- Campaign: resistance-20260104-113751
- Period: 2041-05-01 to 2046-10-08
- Generated: 2026-10-22T09:30:15Z
```

The model is the one the provider reports, followed by the requested one when the two differ. The
prompt version is the one in `plan.json`. The campaign key comes from the package. The period runs
from the first chapter's opening save to the last chapter's closing save. The generation time is
the only line that changes between two assemblies of the same directory.

The chapters' texts follow in order, unchanged except for their footnotes. Each chapter numbers
its footnotes from 1, and the history renumbers them in sequence:

- references are numbered in order of first appearance, and a repeated label keeps its number;
- a definition that no reference points to gets the next number after the chapter's references;
- a reference with no definition keeps its number and takes its label as its definition, as in
  `[^situation 2046-10-08T00:00:00]`;
- definitions are taken out of the text wherever the model put them, together with a heading
  (`Footnotes`, `Notes`, `References`, `Sources`) that only introduces them. Rules and blank lines
  left at a chapter's end are dropped. All definitions follow the last chapter, in the new
  numbering, as the model wrote them.

**Citation audit.** A footnote cites the IDs in its backticks, or, with no backticks, the parts
between semicolons. Each cited ID is checked against the chapter package the chapter was written
from, read back from its request file. The package's citable IDs are:

- its developments and atomic events;
- its `continuity` entries, both `continuing` and `earlier`;
- `situation <save-key>` for its two saves.

The audit lists four kinds of finding:

| Finding | Meaning |
| --- | --- |
| `unmatched` | a cited ID that is none of the chapter package's IDs: an invented or truncated ID, or one from another chapter |
| `uncited` | a development of a chapter package at `major` and above that no footnote of the history cites; with `--citations none` it is not computed |
| `undefined` | a reference with no definition; its label is checked as a citation unless it is a number |
| `unreferenced` | a definition that no reference points to; its citations still count |

The audit reports and never changes or rejects prose. When it finds anything, stderr gets one
line, and the run still exits 0:

```text
tinarrative narrate: citation audit: 38 unmatched citations, 88 uncited developments at major and above, 1 footnote without definition; see DIR/manifest.json
```

A clean run leaves stderr empty.

**Manifest.** `manifest.json` records the run:

| Member | Value |
| --- | --- |
| `program` | `name` and `version` of tinarrative |
| `generated` | the generation time (UTC) |
| `prompt_version`, `package_sha256` | as in `plan.json` |
| `campaign`, `covers` | the campaign key and the period covered |
| `settings` | the planner settings of `plan.json`, plus `provider`, `model`, `max_output_tokens` and `temperature` from the responses (a list when the chapters differ) |
| `request` | the request parameters of `plan.json` |
| `chapters` | per chapter: `index`, `part`, `covers`, `periods`, `period`, `period_basis`, `estimate`, `reduction`, `request_sha256`, `request_characters`, the four send settings, `reported_model`, `finish`, `input_tokens`, `output_tokens` |
| `tokens` | the summed `estimate`, `request_characters`, `input_tokens` and `output_tokens`, and `characters_per_input_token` over the chapters that report input tokens, for calibrating `narrator.chars_per_token` |
| `audit` | `citations`, the number of `footnotes` and of `cited_ids`, and the lists `unmatched` (`chapter`, `footnote`, `id`), `uncited` (`chapter`, `id`, `significance`, or `null`), `undefined` and `unreferenced` (`chapter`, `footnote`, `label`) |

**`--assemble DIR`** reads `plan.json`, `requests/` and `responses/` of a directory that `narrate`
wrote, and writes `history.md` and `manifest.json` into it. It sends nothing, builds no package
and takes no other option. It does not need the current prompt, so a run made with an older
prompt can be assembled again. Every chapter of the plan needs its request file, unchanged (its
SHA-256 is the plan's), and a response made from that request.

## Log

With `--log-level info`, the run logs the save pipeline's lines (as `events`) or the package's
size, then the number of chapters and developments, the largest estimate and the number of
reduced chapters. With `--send` it adds, per request, the provider, the chapter, the attempt, the
HTTP status, the bytes sent and received, any retry wait, and per chapter whether it was sent or
kept, the finish, the token counts and the length of the text. Assembly logs the number of
chapters, footnotes and cited IDs, and the count of each finding. It never logs a request, a response, a key, a URL or a string
from the package.

## Exit codes

| Code | When |
| --- | --- |
| 0 | The plan was printed and, with `--output`, written; with `--send`, the history was assembled, whatever the audit found. |
| 2 | Usage error: no save paths and no `--package`; `--force` without `--send`; `--assemble` with any other option; `--package` with save paths, `--campaign`, `--min-significance` or `--constituents`; a package with no interval; a single interval over `narrator.max_input_tokens` (nothing written); the save input errors of `events`; an unknown `--profile` or an invalid override flag; `--send` without `--output`, provider, model or API key variable, or over `context_window` (nothing contacted). |
| 4 | A save or the `--package` file cannot be read; `--assemble`: DIR or its `plan.json` cannot be read. |
| 5 | A save is not a supported save, or the package is not UTF-8 JSON or not a narrator package. `--assemble` (and the assembly after `--send`): `plan.json` is not a plan, or a chapter's request or response is missing, invalid or does not match the plan; the message names the chapter. |
| 8 | The settings file cannot be read or is not valid settings. Nothing is printed on stdout. |
| 9 | `--output`, or the history and manifest, cannot be written. The plan is not printed (a response that cannot be written stops `--send` after the plan). |
| 10 | `--send`: a chapter request failed (authentication, network, HTTP error, invalid response), or its completion stopped at `max_output_tokens` or was refused. The completed chapters' responses are kept. |
