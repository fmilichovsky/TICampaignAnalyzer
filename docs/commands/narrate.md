# `tinarrative narrate`

<!-- generated: synopsis narrate -->
```
tinarrative narrate [--package FILE] [--campaign SELECTOR]
                    [--min-significance {trivial,minor,major,campaign_defining}]
                    [--constituents {all,evidence,none}] [--period {year,half,quarter}]
                    [--audience {public,insider}] [--citations {footnotes,none}]
                    [--style {chronicle,headlines}] [--length WORDS] [--focus NAME] [--output DIR]
                    [--send] [--force] [--assemble DIR] [--profile NAME]
                    [--provider {anthropic,openai,openrouter,ollama}] [--model MODEL]
                    [--base-url URL] [--max-input-tokens TOKENS] [--max-output-tokens TOKENS]
                    [--temperature TEMPERATURE] [--config FILE] [--jobs N]
                    [PATH ...]
```
<!-- end generated -->

Turns a campaign into a written history told by an LLM. It cuts the campaign's
[narrator package](events.md#narrator-package) into chapters small enough for one model request
each and builds those requests. Without `--send` it contacts nothing: the requests can be
reviewed, or run by hand against any model. With `--send` it sends them to the configured
provider and assembles the answers into one footnoted `history.md`, with a citation audit.
`--assemble DIR` re-assembles a directory written earlier without sending anything.

## Input

- **Saves.** The same inputs as [`events`](events.md): files, directories, `--campaign` and the
  [campaign picker](events.md#campaign-picker). The package is built as
  `events --narrative --format json` builds it.
- **`--package FILE`** narrates a package written earlier by `events --narrative --format json`;
  `-` reads it from stdin. Save paths, `--campaign`, `--min-significance`, `--constituents` and
  `--jobs` are usage errors with it.

## Options

<!-- generated: options narrate -->
| Option | Meaning |
| --- | --- |
| `PATH...` | Save files or directories, in any order; a directory is read one level deep. |
| `--package FILE` | A narrator package from 'events --narrative --format json' to narrate instead; '-' reads stdin. |
| `--campaign SELECTOR` | The campaign to use when the saves hold several: a key, a unique key prefix, a listing number or 'latest'. |
| `--min-significance trivial\|minor\|major\|campaign_defining` | Lowest significance of a narrative event told, from saves (default major). |
| `--constituents all\|evidence\|none` | Which events behind the narrative events the model also gets (default evidence). |
| `--period year\|half\|quarter` | The sections the history is told in (default: from the campaign's span). |
| `--audience public\|insider` | Who the history is for; insider centres on the player faction (default public). |
| `--citations footnotes\|none` | Footnotes citing event IDs, or none (default footnotes). |
| `--style chronicle\|headlines` | Running prose or headlines (default chronicle). |
| `--length WORDS` | Target length of the whole history (default: from how much happened). |
| `--focus NAME` | A faction or nation to centre the account on (default: the player faction with --audience insider). |
| `--output DIR` | Write the plan and one request per chapter here. |
| `--send` | Send the requests to the provider and assemble history.md; needs --output. Hands the campaign to a third party unless the provider runs locally. |
| `--force` | With --send, send every chapter again, even one with a matching stored response. |
| `--assemble DIR` | Assemble history.md from a directory written earlier, sending nothing; takes no other option. |
| `--profile NAME` | Apply the settings profile llm.profiles.NAME. |
| `--provider anthropic\|openai\|openrouter\|ollama` | Override llm.provider. |
| `--model MODEL` | Override llm.model; there is no default model. |
| `--base-url URL` | Override llm.base_url. |
| `--max-input-tokens TOKENS` | Override llm.max_input_tokens. |
| `--max-output-tokens TOKENS` | Override llm.max_output_tokens. |
| `--temperature TEMPERATURE` | Override llm.temperature. |
| `--config FILE` | TOML settings file (default: $TINARRATIVE_CONFIG, else the built-in settings). |
| `--jobs N` | Worker processes; 1 runs everything in one process; the output is the same (default: processing.jobs). |
<!-- end generated -->

The audience, citation and style defaults are the prompt's; see [llm](../narrator.md).

## Chapter plan

Each chapter is a run of whole periods that fits within `llm.max_input_tokens`, and carries
the narrative events that start in it, the situation at its opening and closing saves, and a
reminder of what earlier chapters told. A period too large for one request is told without the
supporting events, then split; narrative events are never dropped.

Every chapter is asked for a length by its narrative weight: its top-level narrative events counted by
significance (campaign-defining 4, major 2, minor 1, trivial 0). Without `--length`, the whole history is
6 words per point. A chapter's length may take half of `llm.max_output_tokens`, at 1.5 tokens a word; periods
that ask for more go to separate chapters, and a single period is split at saves, keeping its supporting events.
If a single interval does not fit either budget, the command stops before writing anything (exit 2).

Without `--period`, the period is `quarter`, `half` or `year` by the campaign's span
(`narrator.quarter_span_days`, `narrator.half_span_days`), made coarser chapter by chapter where
the saves are further apart than the period runs. A given `--period` is kept, with a warning on
stderr where the saves are too sparse for it. The planner is in
[`narrator/chapters.py`](../../src/tinarrative/narrator/chapters.py) and the request it builds in
[`narrator/request.py`](../../src/tinarrative/narrator/request.py).

## Provider and budget

The provider, model and token budget come from the `narrator` settings
([configuration](../configuration.md#narrator-provider-and-profiles)), in this order, each over
the previous one:

1. the `[llm]` keys of the settings file, else their defaults;
2. the profile given with `--profile NAME` (an unknown profile is a usage error);
3. the override flags `--provider`, `--model`, `--base-url`, `--max-input-tokens`,
   `--max-output-tokens` and `--temperature`.

`max_input_tokens` and `max_output_tokens` shape the chapter plan; the other keys only affect sending.

## Sending

**`--send` hands the campaign to the provider, a third party unless it runs on your machine**
(Ollama, or an OpenAI-compatible server at a local `base_url`). The requests carry no file paths,
but they do carry faction, nation and leader names and the whole history.

`--send` needs `--output DIR`, a provider and a model (there is no default model), and, for
`anthropic`, `openrouter`, and for `openai` without a `base_url`, an `api_key_env` setting naming the environment
variable that holds the API key. The key is read only from that variable. Anything missing is a
usage error and nothing is contacted.

Chapters are sent in order. A chapter whose stored response was made from the same request,
provider and model is kept, not sent again, so an interrupted run resumes where it stopped;
`--force` sends every chapter again. The run stops at the first failed chapter (exit 10), keeping
the chapters completed before it. A completion cut off at the output limit, refused, or with no
text (some reasoning models stop after their reasoning without writing) counts as failed, and a
rerun sends that chapter again. Reasoning a provider returns beside the text is never used as the
chapter. The providers are in [`narrator/providers.py`](../../src/tinarrative/narrator/providers.py).

## Output

stdout always gets the plan: per chapter its part, dates, periods, narrative event counts and token
estimate. With `--send` it adds one line per chapter (`sent` or `kept`, with token counts) and
names the history. With `--output DIR`, the command writes:

```text
DIR/
  plan.json          # the plan
  requests/01.json   # one request per chapter
  responses/01.json  # with --send: one per completed chapter
  history.md         # with --send, once every chapter has a response
  manifest.json      # the run record and citation audit, written with history.md
```

The same package and settings always give the same plan and request files.

`history.md` opens with a header naming the provider, model, prompt version, campaign and period,
followed by the chapters in order, their footnotes numbered through the whole history. The
**citation audit** checks every cited ID against what its chapter was given and reports
citations that match nothing, major narrative events that no footnote cites, and footnotes without a
definition. It never changes the prose. When it finds anything, stderr gets one summary line and
the run still exits 0; the details are in `manifest.json`. Assembly and the audit are in
[`narrator/assembly.py`](../../src/tinarrative/narrator/assembly.py).

## Exit codes

<!-- generated: exit-codes narrate -->
| Code | When |
| --- | --- |
| 0 | The plan was printed; with --send, the history was assembled. |
| 2 | Usage error, no campaign chosen, a single interval over llm.max_input_tokens, or --send without --output, a provider, a model or an API key. |
| 4 | A save, the --package file or the --assemble directory cannot be read. |
| 5 | A save is not a supported save, the package is not a narrator package, or a run directory does not match its plan. |
| 8 | The settings file cannot be read or is not valid settings. |
| 9 | --output cannot be written. |
| 10 | A chapter request failed, or its completion was cut off, refused or empty; earlier chapters are kept. |
<!-- end generated -->

## Examples

```sh
tinarrative narrate ~/saves --campaign latest --output run/
tinarrative narrate --package package.json --audience insider --length 4000 --output run/ --send --profile local
tinarrative narrate --assemble run/
```
