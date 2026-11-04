# AGENTS.md

Orientation for coding agents. Keep this file short; link to docs instead of repeating them.

## What this is

`tinarrative` is a Python CLI that reconstructs a readable campaign history from Terra Invicta save files. Saves
are snapshots; each pipeline stage adds interpretation without discarding the evidence below it. Objective changes,
inferred events and narrative presentation stay separate layers. Read [docs/architecture.md](docs/architecture.md)
before touching the model or pipeline.

## Layout

- `src/tinarrative/` — one subpackage per pipeline stage, `io` → `parsing` → `model` → `diff` → `analyzers` →
  `reconstruction` → `narrative` → `rendering` ([README](README.md#package-layout)).
- `src/tinarrative/cli.py` — argparse entry point; stable exit codes at the top.
- `src/tinarrative/config.py` — TOML runtime settings ([docs/configuration.md](docs/configuration.md)).
- `src/tinarrative/inspection/` — `save inspect`; raw structure only, must not import `parsing`.
- `src/tinarrative/maintenance/` — `unknowns`; maintains the registry in `docs/game-data-notes/unknowns/`
  (machine-written, never edited by hand).
- `src/tinarrative/narrator/` — LLM request, chapters, providers, assembly, councilor articles; the system
  prompts are `prompt.md` and `councilor_prompt.md` (the only copies). It reads the narrator package dict only and must not import `parsing`, `sequence` or `model`
  (a test enforces it). No test touches the network.
- `tests/` — mirrors the package; fixtures in `tests/fixtures/`.
- `docs/commands/` — one user-facing page per CLI command.
- `docs/game-data-notes/` — the evidence log of the observed save format ([README](docs/game-data-notes/README.md)).
- `benchmarks/` — real sample campaigns and the package-size matrix ([README](benchmarks/README.md)).
- `scripts/` — standalone utilities, not fit to be part of the main product.
  ([observe_saves.md](scripts/observe_saves.md)). Only `narrator_prompt.py` imports `tinarrative`.

## Commands

```sh
make check        # format check + lint + strict mypy + pytest; same as CI
python -m ruff format .
python scripts/verify_fixture_manifest.py tests/fixtures/io/terra_invicta_json_v1/fixture_manifest.json
make package-metrics PYTHON=.venv/bin/python
```

`make check` must pass before a change is done.

## Code conventions

- **Strict typing.** mypy `strict = true` over `src/`; `from __future__ import annotations`.
- **Evidence vs. inference.** Never merge objective changes and inferred events into one type; every event keeps
  provenance back to save data.
- **Version-specific parsing stays in `parsing`.** Downstream stages use model types only.
- **Diagnostics through `tinarrative.log`.** `get_logger(__name__)`, `fields(...)`, aggregate counts, nothing above
  INFO on the success path. Never log a directory path or a string read from a save; use `safe_path` and `shape`
  ([docs/debugging.md](docs/debugging.md)).
- **No undocumented structure ignored silently.** Everything outside `parsing/fields.py` and `parsing/inventory.py`
  goes through `UnknownCollector`. After adding a field there, re-run the unknowns scan on private saves; the
  committed-registry test fails otherwise.

## Documentation rules

Each fact has exactly one home. Point to it; do not restate it.

- **Contracts live in code.** Signatures, types and docstrings define behavior. `docs/architecture.md` holds
  principles and the designs of work not built yet; once a design is implemented, its section shrinks to the
  principle plus a pointer to the defining module.
- **Plans live in issues.** A `docs/roadmap.md` entry is one headline line plus its issue number. Issue and PR
  numbers appear nowhere else except explicit `TODO`s.
- **Observations live in `docs/game-data-notes/`.** A format fact is documented only after it was checked against
  real data, labeled observed vs. hypothesis. Nowhere else cites save samples, counts or dates.
- **Command pages are for users.** Usage, options, outputs, exit codes and examples; no internals. Update the page
  when a command's behavior changes.
- **`docs/testing.md` states conventions,** never individual fixtures; a fixture's purpose is in its sidecar or
  manifest entry.
- **Comments explain why, not what.** No comment on self-explanatory code; module docstrings of at most three
  lines; no docstring repeats the architecture or cites a save sample.

## Tests and fixtures

Read [docs/testing.md](docs/testing.md) first. The non-negotiables:

- Fixtures are hand-authored synthetic derivatives, located with `tests.fixtures.fixture_path(...)`, each with a
  provenance sidecar; re-run the manifest verifier after editing the `terra_invicta_json_v1` set.
- Real saves are committed only in `benchmarks/samples/`, for size measurement. Tests that need a real save are
  marked `real_save` and excluded from the default run. No automated sanitizers.
- No player names, machine paths or account identifiers in fixtures or their metadata.

## Working style

- Small, focused PRs matching one roadmap item.
- A new pipeline stage comes with `tests/<stage>/` coverage and its roadmap checkbox.
- A change to a supported format identifier or fixture assumption updates `docs/game-data-notes/` and the manifest
  together.
