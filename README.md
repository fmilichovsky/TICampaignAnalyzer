# Terra Invicta Narrative Save Analyzer

`tinarrative` reconstructs a readable campaign history from Terra Invicta save
snapshots. It keeps observed state changes separate from inferred events and
narrative presentation.

## Development

Requires Python 3.11 or newer. Work inside a project-local virtual environment
so the pinned development tools don't mix with other Python installs:

```sh
python3 -m venv .venv            # once per clone
source .venv/bin/activate        # once per shell session
make install                     # once, and again after changing dependencies
tinarrative --help
```

Activation puts `.venv/bin` first on `PATH`, so `python`, `tinarrative`, and the
`make` targets below all use the environment's interpreter. Run `deactivate` to
leave it. On Windows, activate with `.venv\Scripts\activate` instead. The
`.venv/` directory is ignored by git; delete and recreate it to start fresh.

## Commands

- [`tinarrative campaigns <path>...`](docs/commands/campaigns.md): list the campaigns
  that saves belong to, with the selector for `events --campaign`.
- [`tinarrative councilors <path>...`](docs/commands/councilors.md): select a campaign's
  notable councilors, write the dossier and one article request per councilor, and with
  `--send` have a model write the neutral, public-perception articles.
- [`tinarrative events <path> <path>...`](docs/commands/events.md): group saves
  (files, or directories read one level deep) by campaign, order one campaign's saves
  by game time and report the analyzer results (and, with
  `--inferred`, the inferred events; with `--changes`, the literal state changes)
  of every pair of consecutive saves; with `--narrative`, the narrative events that span
  intervals (takeovers, wars, federations, expansions, ...), tuned by an optional
  [settings file](docs/configuration.md). This is the only command that reports analysis;
  `narrate` runs the same analysis to build its package.
- [`tinarrative narrate <path>...`](docs/commands/narrate.md): cut a campaign's narrator
  package into chapters under a token budget and write one LLM request per chapter; with
  `--send`, send them to an Anthropic, OpenAI-compatible or Ollama model and assemble the
  responses into one footnoted history with a citation audit and a run manifest.
- `tinarrative save COMMAND`: per-save evidence and debugging commands.
  - [`tinarrative save inspect <save>`](docs/commands/inspect.md): report one save's
    raw serialized structure without interpreting it.
  - [`tinarrative save parse <save>`](docs/commands/parse.md): load and validate one
    save as a supported raw save and print an envelope summary, ending with the
    number of unknown structures met.
  - [`tinarrative save diff <before> <after>`](docs/commands/diff.md): compare two saves and
    list every literal state change between them, with before/after values and
    evidence, without analyzing or inferring anything.
- [`tinarrative benchmark sample <name> <path>...`](docs/commands/benchmark.md): import or refresh a campaign's
  saves in the package-size benchmark samples.
- [`tinarrative unknowns <path>...`](docs/commands/unknowns.md): scan saves for
  structures the parser does not describe and record them in the
  [unknowns registry](docs/game-data-notes/unknowns/README.md) for triage.

Each page documents the command's options, output, and exit codes. See the
[command index](docs/commands/README.md) for the shared exit-code conventions.

To see what the parser decided, run any command with `--log-level debug` before
the command name, or set `TINARRATIVE_LOG_LEVEL=debug`; the log goes to stderr and
names no paths or save content. See the [debugging guide](docs/debugging.md).

## Testing

```sh
make check
```

`make check` is the baseline quality gate and runs formatting, linting, strict type checking, and tests.

Individual targets are `make format`, `make lint`, `make typecheck`, and
`make test`. To apply formatting, run `python -m ruff format .`.

Standards for code, docs, fixtures and tests are in [CONTRIBUTING.md](CONTRIBUTING.md); running and maintaining
the suite is in [the testing guide](docs/testing.md).

`make package-metrics` measures what `events` and `narrate` would send to an LLM for the real sample campaigns in
`benchmarks/`, and `make runtime-metrics` measures how long `events` takes on them. Every pull request gets both
measurements for its base and head as comments. See [benchmarks/README.md](benchmarks/README.md).
