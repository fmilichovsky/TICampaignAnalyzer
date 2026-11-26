# Terra Invicta Narrative Save Analyzer

`tinarrative` reconstructs a readable campaign history from Terra Invicta save
snapshots. Most of the work happens in a repeatable, deterministic process that
constructs a filtered, ranked and partially interpreted package.
The package gets fed to an LLM to tie them together, wrap them in a readable story,
and justify how the general public would realistically perceive the events.
The tone and shape of the final content is stated in the [editorial direction](docs/editorial-direction.md).
How event significance is judged against it is stated in the [calibration principles](docs/calibration-principles.md).

- Most of the work happens locally without LLMs.
- Narrative layer (LLM interaction) supports multiple API providers (OpenAI, Anthropic, OpenRouter, Local Ollama).

## Quick start

1. Obtain an API key for an LLM provider.
1. Set up the local CLI with `make install` - see [Development](#development).
1. Try out the [`narrate`](docs/commands/narrate.md) or [`councilors`](docs/commands/councilors.md) command
against your Terra Invicta save directory.

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
- [`benchmark`](docs/commands/benchmark.md): maintain the sample campaigns, measure package size and runtime, and
  calibrate the share references.

Options, saves, campaigns and exit codes shared by the commands are in the [command reference](docs/commands/README.md).

## Development

Requires Python 3.11 or newer.

```sh
make install     # creates .venv if missing, then installs the pinned development tools; re-run after changing dependencies
make check
```

## Testing

```sh
make check
```

`make check` is the baseline quality gate and runs formatting, linting, strict type checking, and tests.

Individual targets are `make format`, `make lint`, `make typecheck`, and
`make test`. To apply formatting, run `make format-fix`.

Standards for code, docs, fixtures and tests are in [CONTRIBUTING.md](CONTRIBUTING.md); running and maintaining
the suite is in [the testing guide](docs/testing.md).

`make package-metrics` measures what `events` and `narrate` would send to an LLM for the real sample campaigns in
`benchmarks/`, and `make runtime-metrics` measures how long `events` takes on them. Every pull request gets both
measurements for its base and head as comments. See [benchmarks/README.md](benchmarks/README.md).

## Repository skills

Repo skills have one canonical copy in `.agents/skills/<name>/`.
Codex discovers skills there. Claude Code discovers them in `.claude/skills/<name>/`, so each supported repo skill
has a relative directory symlink from that location to its canonical copy. The allowlist in `.gitignore` ignores
locally installed skills and includes only skills deliberately committed to both discovery directories.

On Windows, enable Developer Mode to create symlinks without administrator rights, then set
`git config --global core.symlinks true` before cloning. In an existing clone, set `git config core.symlinks true`
before checking out symlink entries. Git may check out those entries as regular files when `core.symlinks` is
false. On Unix, symlinks generally work without extra setup; the filesystem must support them.

Run these commands from the repository root to create the symlink for the current repo skill:

```powershell
git config core.symlinks true
New-Item -ItemType Directory -Force .claude/skills | Out-Null
New-Item -ItemType SymbolicLink `
  -Path .claude/skills/narrator-contract-iteration `
  -Target ..\..\.agents\skills\narrator-contract-iteration
```

```sh
mkdir -p .claude/skills
ln -s ../../.agents/skills/narrator-contract-iteration \
  .claude/skills/narrator-contract-iteration
```

The shared ignore rules are:

```gitignore
*/skills/*
!*/skills/narrator-contract-iteration
```
