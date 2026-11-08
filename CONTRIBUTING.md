# Contributing

The standards every change follows, whoever writes it. Setup and commands are in the [README](README.md#development);
test mechanics are in [docs/testing.md](docs/testing.md). A change is done when `make check` passes.

When a standard here can be checked mechanically, a test enforces it and the standard names that test.

## Code

- **Strict typing.** mypy `strict = true` over `src/`; `from __future__ import annotations`.
- **Evidence vs. inference.** Never merge objective changes and inferred events into one type; every event keeps
  provenance back to save data.
- **Version-specific parsing stays in `parsing`.** Downstream stages use model types only.
- **Stage boundaries.** `inspection` describes raw structure and does not import `parsing`. `narrator` reads the
  narrator package dict only and does not import `parsing`, `sequence` or `model`
  (`tests/narrator/test_request.py::test_the_narrator_package_does_not_import_the_deterministic_half`). Of
  `scripts/`, only `narrator_prompt.py` imports `tinarrative`.
- **Diagnostics through `tinarrative.log`.** `get_logger(__name__)`, `fields(...)`, aggregate counts, nothing above
  INFO on the success path. Never log a directory path or a string read from a save; use `safe_path` and `shape`
  ([docs/debugging.md](docs/debugging.md)).
- **No undocumented structure ignored silently.** Everything outside `parsing/fields.py` and `parsing/inventory.py`
  goes through `UnknownCollector`. The unknowns registry is machine-written, never edited by hand; after adding a
  field, re-run the unknowns scan on private saves
  (`tests/maintenance/test_committed_registry.py::test_committed_registry_is_valid_canonical_and_fully_unknown`).
- **Comments explain why, not what.** No comment on self-explanatory code; module docstrings of at most three
  lines; no docstring repeats the architecture or cites a save sample.

## Documentation

Each fact has exactly one home. Point to it; do not restate it.

- **Contracts live in code.** Signatures, types and docstrings define behavior. `docs/architecture.md` holds
  principles and the designs of work not built yet; once a design is implemented, its section shrinks to the
  principle plus a pointer to the defining module.
- **Plans live in issues.** A `docs/roadmap.md` entry is one headline line plus its issue number, ticked in the PR
  that completes it. Issue and PR numbers appear nowhere else except explicit `TODO`s.
- **Observations live in `docs/game-data-notes/`.** A format fact is documented only after it was checked against
  real data, labeled observed vs. hypothesis. Nowhere else cites save samples, counts or dates. Known state types
  match the inventory there
  (`tests/parsing/test_unknowns.py::test_known_state_types_match_the_documented_inventory`).
- **Command pages are for users.** Usage, options, outputs, exit codes and examples; no internals. Update the page
  when a command's behavior changes.
- **Settings have one example.** `docs/configuration.example.toml` is exactly the defaults
  (`tests/test_config.py::test_example_is_the_defaults`).
- **The narrator's system prompts exist once,** as `prompt.md` and `councilor_prompt.md` in the package; docs point
  at them
  (`tests/narrator/test_request.py::test_the_doc_points_at_the_packaged_prompt_instead_of_copying_it`,
  `tests/narrator/test_councilors.py::test_the_doc_points_at_the_packaged_councilor_prompt_instead_of_copying_it`).

## Fixtures and real data

- **Fixtures are hand-authored synthetic derivatives,** never real saves, sanitized or not, and never produced by
  an automated sanitizer. Each fixture has a manifest entry stating its purpose
  (`tests/test_fixture_manifest.py::test_terra_invicta_fixture_manifest_is_complete_and_consistent`).
- **No player names, machine paths or account identifiers** in fixtures or their metadata.
- **A change to a supported format identifier or fixture assumption** updates `docs/game-data-notes/` and the
  manifest together.
- **Real saves are committed only in `benchmarks/samples/`,** listed with their hashes in its manifest
  (`tests/test_package_metrics.py::test_the_committed_samples_match_their_manifest`).

## Tests

1. **Test durable contracts through the stage's public entry point.** Use a private seam only when the public one
   is infeasible, and say why in one line.
2. **Don't keep tests that pin a finished transition** — an old name absent, a removed option rejected. Check that
   once in the PR that makes the change.
3. **Name a regression test after the behavior it protects,** never after an issue.
4. **Each behavior has one home.** Stage tests own logic; command tests own argument wiring, exit codes and output
   format.
5. **Exact output is pinned only by goldens,** which regenerate with one command. Other tests assert properties,
   not counts, sizes, wording or incidental values; derive tunables from their source constants.
6. **No test touches the network.**

## Pull requests

- Small and focused, matching one roadmap item.
- A new pipeline stage comes with `tests/<stage>/` coverage and its roadmap checkbox.
