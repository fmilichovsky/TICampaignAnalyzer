# AGENTS.md

Orientation for coding agents working in this repository. Keep this file short;
link to existing docs instead of duplicating them.

## What this is

`tinarrative` is a Python CLI that reconstructs a readable campaign history
from Terra Invicta save files. The core idea: saves are snapshots, and each
pipeline stage adds interpretation without discarding lower-level evidence.
Objective changes, inferred events, and narrative presentation are kept as
separate layers. Read [docs/architecture.md](docs/architecture.md) before
touching the model or pipeline.

## Layout

- `src/tinarrative/` — package, one subpackage per pipeline stage
  (`io` → `parsing` → `model` → `diff` → `analyzers` → `reconstruction` →
  `narrative` → `rendering`). Stage responsibilities are listed in
  [README.md](README.md#package-layout).
- `src/tinarrative/cli.py` — argparse entry point; stable exit codes are
  defined at the top of the file.
- `src/tinarrative/inspection/` — `tinarrative inspect`: raw structural
  report of one save, plus the ID census from `src/tinarrative/identity.py`.
  It does not normalize anything and must not import from `parsing`.
- `tests/` — loosely mirrors the package layout. Fixtures live in `tests/fixtures/`.
- `docs/commands/` — one page per implemented CLI subcommand (options, output, exit codes).
  Update the matching page when a command's behavior changes.
- `docs/game-data-notes/` — evidence log of the observed save format. Start at
  its [README](docs/game-data-notes/README.md).
- `docs/game-data-notes/unknowns/` — machine-written registry of save structures the
  parser met and does not describe, plus the triage workflow
  ([README](docs/game-data-notes/unknowns/README.md)). Refreshed by
  `tinarrative unknowns`; never edited by hand.
- `src/tinarrative/maintenance/` — `tinarrative unknowns`: scans saves and maintains
  that registry. A tool package like `inspection`, not a pipeline stage.
- `scripts/verify_fixture_manifest.py` — validates the versioned fixture set.

## Commands

```sh
make check        # install + format check + lint + strict mypy + pytest; same as CI
make format lint typecheck test   # individual gates
python -m ruff format .           # apply formatting
python scripts/verify_fixture_manifest.py tests/fixtures/io/terra_invicta_json_v1/fixture_manifest.json
```

Tool versions are pinned in [pyproject.toml](pyproject.toml). `make check`
must pass before a change is considered done; CI runs exactly that
([.github/workflows/tests.yml](.github/workflows/tests.yml)).

## Conventions that matter

- **Strict typing.** mypy runs with `strict = true` over `src/`. Use
  `from __future__ import annotations` and full annotations on public functions.
- **Evidence vs. inference.** Never collapse objective state changes and
  inferred events into one type. Provenance back to save data is a design
  requirement, not a nicety (architecture doc, sections 3–5).
- **Version-specific parsing stays in `parsing`.** Downstream stages depend on
  normalized model types only.
- **Diagnostics go through `tinarrative.log`.** `logger = get_logger(__name__)`,
  `fields(...)` for `key=value` context, aggregate counts instead of per-entity lines,
  nothing above DEBUG/INFO on the success path. Never log a directory path or a string
  value read from a save; use `safe_path` and `shape`. See [docs/debugging.md](docs/debugging.md).
- **Save format claims must be observed, not assumed.** Only document a format
  fact in `docs/game-data-notes/` if it was checked against real data, and
  label it as observed vs. hypothesis per that directory's README.
- **Never ignore an undocumented structure silently.** The normalizer reports
  everything outside `parsing/fields.py` and `parsing/inventory.py` through
  `UnknownCollector`. After adding a field to `ENTITY_FIELDS`, `RECORD_FIELDS` or
  `ACKNOWLEDGED_FIELDS` (with an `UnsupportedReason`), re-run the unknowns scan on
  private saves so the registry shrinks; the committed-registry test fails otherwise.
  The registry holds names, shapes, counts and dates only, never values.

## Tests and fixtures

Read [docs/testing.md](docs/testing.md) before adding tests or fixtures. Key
points:

- Locate fixtures via `tests.fixtures.fixture_path(...)`, never CWD-relative.
- Every non-text fixture has a `<name>.json` sidecar with provenance metadata.
- The `terra_invicta_json_v1` fixture set is governed by its
  `fixture_manifest.json` (SHA-256, size limits, format/version assumptions).
  Re-run the verifier script after any edit there.
- **Never commit real saves or campaign data.** Fixtures are hand-authored
  synthetic derivatives. No automated sanitizers. Tests needing real saves are
  marked `real_save` and excluded from the default run.
- No player names, machine paths, or account identifiers anywhere in fixtures
  or their metadata.

## Working style

- Small, focused PRs matching one roadmap item are the norm (see git log).
- When adding a pipeline stage, add the corresponding `tests/<stage>/` coverage
  in the same change and update the roadmap checkbox.
- If a change alters a supported format identifier or fixture assumption,
  update `docs/game-data-notes/` and the manifest together.
