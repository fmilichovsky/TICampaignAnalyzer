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

Turns a campaign into a written history told by an LLM. It splits the campaign into chapters that each fit one model
request and builds those requests. Without `--send` it contacts nothing: review the requests, or run them by hand
against any model. With `--send` it sends them and assembles the answers into one footnoted `history.md`. Read
[sending to a model](README.md#sending-to-a-model) before the first `--send`.

## Examples

```sh
# Plan the history of the campaign being played and write the requests, without sending anything.
tinarrative narrate ~/saves --campaign latest --output run/

# Send them with the provider and model of the "local" settings profile.
tinarrative narrate ~/saves --campaign latest --output run/ --send --profile local

# An insider history of about 4000 words from a package built earlier.
tinarrative narrate --package package.json --audience insider --length 4000 --output run/ --send

# Rebuild history.md from a run directory, sending nothing.
tinarrative narrate --assemble run/
```

Saves are chosen as described in [saves and campaigns](README.md#saves-and-campaigns). `--package` narrates a package
from [`events --narrative --format json`](events.md#narrator-package) instead; save paths, `--campaign`,
`--min-significance`, `--constituents` and `--jobs` do not apply to it.

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

`llm.max_input_tokens` and `llm.max_output_tokens` decide how the campaign is split into chapters. When a single
interval between two saves does not fit, the command stops before writing anything (exit 2): raise
`llm.max_input_tokens` or `--max-input-tokens`. A `--period` finer than the saves allow is kept, with a warning.

## Output

stdout gets the plan: per chapter its dates, periods, narrative event counts and estimated tokens. With `--send` it
adds one line per chapter, `sent` or `kept`. With `--output DIR`, the command writes:

```text
DIR/
  plan.json          # the plan
  requests/01.json   # one request per chapter
  responses/01.json  # with --send: one per completed chapter
  history.md         # with --send, once every chapter has a response
  manifest.json      # the run record and citation audit, written with history.md
```

The run stops at the first failed chapter (exit 10) and keeps the chapters before it; a rerun resumes there.

`history.md` names the provider, model and campaign, then tells the chapters in order with footnotes citing event IDs.
The **citation audit** reports footnotes that cite nothing the chapter was given, major narrative events no footnote
cites, and footnotes without a definition. It never changes the prose: when it finds anything, stderr gets one summary
line, the details go to `manifest.json`, and the run still exits 0.

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
