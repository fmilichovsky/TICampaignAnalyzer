# Commands

What the `tinarrative` commands share. Each command has its own page, listed in the
[README](../../README.md#commands); `tinarrative COMMAND --help` prints the same options.

## Global options

Global options go before the command name.

<!-- generated: options tinarrative -->
| Option | Meaning |
| --- | --- |
| `--version` | Print the version. |
| `--log-level debug\|info\|warning\|error` | Diagnostic log level on stderr: debug, info, warning, error; must precede COMMAND (default: $TINARRATIVE_LOG_LEVEL, else warning). |
<!-- end generated -->

The [debugging guide](../debugging.md) explains `--log-level debug`.

## Saves and campaigns

`campaigns`, `events`, `narrate`, `councilors` and `benchmark sample` take saves the same way.

- Pass save files, directories or both, in any order. A directory is read one level deep.
- A named file that is not a usable save stops the run (exit 4 or 5). A file inside a named directory that is not a
  usable save is skipped and listed; it never changes the exit code.
- Saves are put in game-time order, whatever their file names. Byte-identical copies, such as an `Exitsave.json`
  beside the save it copies, count once.
- Campaigns are never mixed. When the saves hold several, choose one with `--campaign`:
  - a key from [`campaigns`](campaigns.md), such as `resistance-20260104-113751`, or any prefix that matches one
    campaign (`protectorate`);
  - its number in the `campaigns` listing (`2`);
  - `latest`: the campaign of the most recently modified save, usually the one being played.

### Campaign picker

In a terminal, a missing or unmatched `--campaign` opens a picker instead of failing. It writes to stderr, so
`tinarrative events ~/saves > report.md` still asks. Type anything `--campaign` accepts, or search text matched
against the key, faction, scenario and start date (`prot` finds `protectorate`). An empty answer or Ctrl-C cancels
with exit 2. Outside a terminal, the run exits 2 and prints the listing to stderr.

## Sending to a model

`narrate` and `councilors` build model requests and, without `--send`, contact nothing: the requests in `--output`
can be reviewed, or run by hand against any model.

**`--send` hands the campaign to the provider, a third party unless it runs on your machine** (Ollama, or an
OpenAI-compatible server at a local `llm.base_url`). The requests carry no file paths, but they do carry faction,
nation, leader and councilor names.

- `--send` needs `--output`, a provider and a model; there is no default model. `anthropic`, `openrouter` and
  `openai` without a `llm.base_url` also need `llm.api_key_env`, the name of the environment variable that holds the
  API key. Anything missing is a usage error, and nothing is contacted.
- Set these in the `[llm]` table of the [settings file](../configuration.md), choose a named set with
  `--profile NAME`, or override one value with a flag such as `--model`. Flags win over the profile, and the profile
  over `[llm]`.
- A rerun into the same `--output` keeps every response made from the same request, provider and model, so an
  interrupted run resumes where it stopped. `--force` sends everything again.

## Settings and workers

- `--config FILE`, else the `TINARRATIVE_CONFIG` environment variable, names the [settings file](../configuration.md);
  without either, the built-in settings apply.
- `--jobs N` sets the worker processes for reading and analyzing saves; `1` runs everything in one process. The output
  is the same for every value.

## Exit codes

Every command page lists the codes it uses. Their general meaning:

| Code | Meaning |
| --- | --- |
| 0 | Success. |
| 2 | Usage error. |
| 4 | An input path could not be read. |
| 5 | An input was read but is not a supported save or document. |
| 6 | `save inspect`: a `--path` did not resolve. |
| 7 | The unknowns registry could not be read or written. |
| 8 | The settings file could not be read or is not valid settings; nothing is printed on stdout. |
| 9 | An output file or directory could not be written. |
| 10 | `--send`: a model request failed, or its answer was cut off, refused or empty. |
