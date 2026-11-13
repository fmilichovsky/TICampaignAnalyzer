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

Campaign history:

- [`campaigns`](docs/commands/campaigns.md): list the campaigns your saves belong to.
- [`narrate`](docs/commands/narrate.md): have an LLM write the campaign's history.
- [`councilors`](docs/commands/councilors.md): have an LLM write articles about the notable councilors.

Analysis and debugging:

- [`events`](docs/commands/events.md): report what happened between consecutive saves; builds the narrator package.
- [`save diff`](docs/commands/diff.md): list every literal change between two saves.
- [`save parse`](docs/commands/parse.md): check that a save loads.
- [`save inspect`](docs/commands/inspect.md): show a save's raw structure.

Maintainer tooling:

- [`unknowns`](docs/commands/unknowns.md): find save structures the parser does not describe yet.
- [`benchmark`](docs/commands/benchmark.md): maintain the sample campaigns and measure package size and runtime.

Options, saves, campaigns and exit codes shared by the commands are in the [command reference](docs/commands/README.md).
Add `--log-level debug` before the command to see what the parser decided; see the [debugging guide](docs/debugging.md).

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
