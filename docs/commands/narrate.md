# `tinarrative narrate`

```
tinarrative narrate <path> [<path>...] [--campaign <selector>] [--min-significance <level>] [--constituents all|evidence|none] [options]
tinarrative narrate --package <file>|- [options]
tinarrative narrate --assemble <dir>

options: [--period year|half|quarter] [--audience public|insider] [--citations footnotes|none]
         [--style chronicle|headlines] [--length <words>] [--focus <name>] [--output <dir>] [--config <file>]
         [--send] [--force] [--profile <name>] [--provider anthropic|openai|openrouter|ollama] [--model <id>] [--base-url <url>]
         [--max-input-tokens <tokens>] [--max-output-tokens <tokens>] [--temperature <t>]
```

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

| Option | Default | Meaning |
| --- | --- | --- |
| `PATH...` | | Save files or directories, in any order. |
| `--package FILE` | | A finished narrator package to narrate as it is; `-` for stdin. |
| `--campaign SELECTOR` | | The campaign to narrate when the saves hold several (as `events --campaign`). |
| `--min-significance LEVEL` | `major` | Lowest significance of a narrative event told (saves only). |
| `--constituents all\|evidence\|none` | `evidence` | Which events behind the narrative events the model also gets (saves only). |
| `--period year\|half\|quarter` | from the campaign span | The sections the history is told in; see [Chapter plan](#chapter-plan). |
| `--audience public\|insider` | `public` | Who the history is for. `insider` centres on the player faction. |
| `--citations footnotes\|none` | `footnotes` | Footnotes citing event IDs, or none. |
| `--style chronicle\|headlines` | `chronicle` | Running prose or headlines. |
| `--length WORDS` | | Target length of the whole history, shared out across chapters by their narrative events. |
| `--focus NAME` | player faction for `insider` | A faction or nation to centre the account on. |
| `--output DIR` | | Write the plan and the requests here; without it only the plan summary is printed. |
| `--config FILE` | `$TINARRATIVE_CONFIG`, else built-in | Settings file: narrative rules and the `[llm]` budget, provider and profiles ([configuration](../configuration.md)). |
| `--jobs N` | `processing.jobs`, else bounded by CPUs and memory | Saves only: worker processes for surveying the saves and analyzing the intervals; `1` runs everything in one process. Small inputs run in one process. The output is the same for every value ([configuration](../configuration.md)). |
| `--send` | off | Send the requests to the provider ([Sending](#sending)). Needs `--output`. |
| `--force` | off | With `--send`, send every chapter again, even one with a matching stored response. |
| `--assemble DIR` | | Assemble `history.md` and `manifest.json` from a directory written earlier. Takes no other option. |
| `--profile NAME` | | Apply the settings profile `[llm.profiles.NAME]`. |
| `--provider`, `--model`, `--base-url`, `--max-input-tokens`, `--max-output-tokens`, `--temperature` | | Override the `narrator` setting of the same name ([Provider and budget](#provider-and-budget)). |

The audience, citation and style defaults are the prompt's; see [llm](../narrator.md).

## Chapter plan

Each chapter is a run of whole periods that fits within `llm.max_input_tokens`, and carries
the narrative events that start in it, the situation at its opening and closing saves, and a
reminder of what earlier chapters told. A period too large for one request is told without the
supporting events, then split; narrative events are never dropped. If a single interval does not fit,
the command stops before writing anything (exit 2).

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

`max_input_tokens` shapes the chapter plan; the other keys only affect sending.

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

| Code | When |
| --- | --- |
| 0 | The plan was printed and, with `--output`, written; with `--send`, the history was assembled, whatever the audit found. |
| 2 | Usage error: no save paths and no `--package`; `--force` without `--send`; `--assemble` with another option; `--package` with save paths, `--campaign`, `--min-significance`, `--constituents` or `--jobs`; a package with no interval; a single interval over the token budget; the save input errors of `events`; an unknown `--profile` or an invalid override; `--send` without `--output`, provider, model or API key, or over the context window. |
| 4 | A save or the `--package` file cannot be read; `--assemble`: DIR or its `plan.json` cannot be read. |
| 5 | A save is not a supported save, or the package is not a narrator package. `--assemble` (and the assembly after `--send`): the plan, a request or a response is missing, invalid or does not match. |
| 8 | The settings file cannot be read or is not valid settings. Nothing is printed on stdout. |
| 9 | `--output`, or the history and manifest, cannot be written. |
| 10 | `--send`: a chapter request failed (authentication, network, HTTP error, invalid response), or its completion hit the output limit, was refused or had no text. Completed chapters are kept. |

## Examples

```sh
tinarrative narrate ~/saves --campaign latest --output run/
tinarrative narrate --package package.json --audience insider --length 4000 --output run/ --send --profile local
tinarrative narrate --assemble run/
```
