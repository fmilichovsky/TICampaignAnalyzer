# Terra Invicta Narrative Save Analyzer

`tinarrative` reconstructs a readable campaign history from Terra Invicta save
snapshots. It keeps observed state changes separate from inferred events and
narrative presentation.

## Development

```sh
python -m pip install -e ".[dev]"
tinarrative --help
```

## Commands

- [`tinarrative inspect <save>`](docs/commands/inspect.md): report one save's
  raw serialized structure without interpreting it.
- [`tinarrative parse <save>`](docs/commands/parse.md): load and validate one
  save as a supported raw save and print an envelope summary.
- `tinarrative diff <before> <after>` is registered but not implemented yet.

Each page documents the command's options, output, and exit codes. See the
[command index](docs/commands/README.md) for the shared exit-code conventions.

## Testing

```sh
make check
```

`make check` is the baseline quality gate and runs formatting, linting, strict
type checking, and tests; CI runs the same target. Development-tool versions
are pinned in `pyproject.toml` so a clean checkout resolves the same tools.

Individual targets are `make format`, `make lint`, `make typecheck`, and
`make test`. To apply formatting, run `python -m ruff format .`.

See [the testing guide](docs/testing.md) for test and fixture conventions.

## Package layout

- `io`: discover and load save files.
- `inspection`: describe one save's raw serialized structure without
  normalizing it.
- `identity`: per-domain entity-identity strategy table and the ID census that
  `inspection` reports.
- `parsing`: decode version-specific save data and normalize it.
- `model`: stable snapshots, changes, events, and provenance types.
- `diff`: derive literal state transitions.
- `analyzers`: emit domain-specific atomic events.
- `reconstruction`: combine evidence into conservative inferred events.
- `narrative`: group atomic events into narrative developments.
- `rendering`: turn structured narrative output into user-facing formats.
