# AGENTS.md

Orientation for coding agents. Keep this file short; link to docs instead of repeating them.

**Follow [CONTRIBUTING.md](CONTRIBUTING.md).** It holds the repo's code, documentation, fixture and test standards;
nothing here restates them.

## What this is

`tinarrative` is a Python CLI that reconstructs a readable campaign history from Terra Invicta save files. Saves
are snapshots; each pipeline stage adds interpretation without discarding the evidence below it. Objective changes,
inferred events and narrative presentation stay separate layers. Read the decisions in [docs/adr/](docs/adr/)
before touching the model or pipeline.

## Layout

- `src/tinarrative/` — one subpackage per pipeline stage, `io` → `parsing` → `model` → `diff` → `kinds` →
  `analyzers` → `reconstruction` → `narrative` → `rendering` ([README](README.md#package-layout)).
- `src/tinarrative/kinds/` — one event kind per event type, one module per family (ADR-0001).
- `src/tinarrative/cli.py` — argparse entry point; stable exit codes at the top.
- `src/tinarrative/config.py` — TOML runtime settings ([docs/configuration.md](docs/configuration.md)).
- `src/tinarrative/inspection/` — `save inspect`; raw structure only.
- `src/tinarrative/maintenance/` — `unknowns`; maintains the registry in `docs/game-data-notes/unknowns/`.
- `src/tinarrative/narrator/` — LLM request, chapters, providers, assembly, councilor articles; the system
  prompts are `prompt.md` and `councilor_prompt.md`.
- `tests/` — mirrors the package; fixtures in `tests/fixtures/` ([docs/testing.md](docs/testing.md)).
- `docs/commands/` — one user-facing page per CLI command.
- `docs/game-data-notes/` — the evidence log of the observed save format ([README](docs/game-data-notes/README.md)).
- `benchmarks/` — real sample campaigns, the package-size matrix and the runtime measurement
  ([README](benchmarks/README.md)).
- `scripts/` — standalone utilities, not fit to be part of the main product
  ([observe_saves.md](scripts/observe_saves.md)).

## Commands

```sh
make install      # install the pinned editable development environment
make check        # format check + lint + strict mypy + pytest; run after install
make samples      # the tests that read the committed benchmark campaigns
python -m ruff format .
python scripts/verify_fixture_manifest.py tests/fixtures/io/terra_invicta_json_v1/fixture_manifest.json
make package-metrics PYTHON=.venv/bin/python
```

## Agent-only rules

- Do not add agent attribution lines to commits or PR descriptions.

## Agent skills

### Issue tracker

GitHub Issues on fmilichovsky/TICampaignAnalyzer via `gh`.
See [docs/agents/issue-tracker.md](docs/agents/issue-tracker.md).

### Triage labels

Default vocabulary: needs-triage, needs-info, ready-for-agent,
ready-for-human, wontfix. See [docs/agents/triage-labels.md](docs/agents/triage-labels.md).

### Domain docs

Single-context: root CONTEXT.md and docs/adr/.
See [docs/agents/domain.md](docs/agents/domain.md).
