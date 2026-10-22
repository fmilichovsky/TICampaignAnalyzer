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
- `src/tinarrative/config.py` — runtime settings (TOML via `--config` /
  `TINARRATIVE_CONFIG`) for the narrative rules' thresholds and windows; keys
  and defaults in [docs/configuration.md](docs/configuration.md).
- `src/tinarrative/inspection/` — `tinarrative save inspect`: raw structural
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
- `benchmarks/` — real sample campaigns (`samples/`, xz-compressed) and the `events`/`narrate` run matrix that
  `scripts/package_metrics.py` measures package sizes with; CI posts base-vs-head on every PR
  ([.github/workflows/package-metrics.yml](.github/workflows/package-metrics.yml),
  [README](benchmarks/README.md)). The script never imports `tinarrative`.
- `src/tinarrative/narrator/` — LLM request builder (`request.py`): the system prompt as package data
  (`prompt.md`, the only copy; `docs/narrator.md` holds the rationale) and the request block; the chapter
  planner of `tinarrative narrate` (`chapters.py`: estimate, plan, chapter packages, continuity); the providers of
  `narrate --send` (`providers.py`: neutral request and completion, the `anthropic`/`openai`/`ollama` adapters,
  retries) over a stdlib HTTP transport (`transport.py`) that tests replace with a fake; the assembly of the
  responses (`assembly.py`: `history.md`, footnote renumbering, citation audit, `manifest.json`). It reads the narrator
  package dict only and must not import `parsing`, `sequence` or `model`; a test enforces it. No test touches the
  network.
- `scripts/narrator_prompt.py` — thin CLI over that builder (adds `--sample` trimming) for an
  `events --narrative --format json` package; never calls an API.

## Commands

```sh
make check        # install + format check + lint + strict mypy + pytest; same as CI
make format lint typecheck test   # individual gates
python -m ruff format .           # apply formatting
python scripts/verify_fixture_manifest.py tests/fixtures/io/terra_invicta_json_v1/fixture_manifest.json
make package-metrics PYTHON=.venv/bin/python   # package sizes of the benchmark samples
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
- **Comments state rules, not evidence.** Code comments and docstrings must not cite
  specific save samples (sample sizes, campaign counts, investigation dates, interval
  lengths, "observed in every inspected save"). That belongs in `docs/game-data-notes/`;
  state the rule and point at the note if needed.
- **Each doc has its altitude.** Specific observations live in `docs/game-data-notes/`
  only. `docs/architecture.md` stays high-level: no save samples, counts or dates; link
  to the notes instead. Issue and PR numbers appear only in `docs/roadmap.md` (and
  explicit `TODO`s); never in code comments, architecture or the notes.
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
- **Real saves live only in `benchmarks/samples/`.** They are whole, xz-compressed saves listed in
  `samples.json`, checked for machine paths and account identifiers before they are added, and used only to
  measure package size. Fixtures are hand-authored synthetic derivatives. No automated sanitizers. Tests needing
  a real save's content are marked `real_save` and excluded from the default run.
- No player names, machine paths, or account identifiers anywhere in fixtures
  or their metadata.

## Working style

- Small, focused PRs matching one roadmap item are the norm (see git log).
- When adding a pipeline stage, add the corresponding `tests/<stage>/` coverage
  in the same change and update the roadmap checkbox.
- If a change alters a supported format identifier or fixture assumption,
  update `docs/game-data-notes/` and the manifest together.
