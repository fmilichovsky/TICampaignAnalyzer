# Benchmarks: package size

What `events --narrative --format json` and `narrate` hand to an LLM is measured on real campaigns, so a change's effect
on the package can be read off every pull request instead of being measured by hand.

```text
benchmarks/
  samples/<campaign>/*.json.xz   # real saves, one directory per campaign, xz-compressed
  samples/samples.json           # the manifest: size and SHA-256 of every file, a description per campaign
  matrix.toml                    # the events and narrate runs made against every campaign
  config.toml                    # the settings file every run is given: empty, so the code's defaults apply
```

The tool is `tinarrative benchmark metrics`. Its CLI code runs from the current checkout; it runs `events` and
`narrate` with the interpreter it is given (`--python`) and reads their output, so the same checkout can measure any
revision. Progress is shown as one aggregate terminal line while campaigns continue to print their completed run trees.

## What is measured

`measure` decompresses each campaign into a temporary directory and runs every matrix entry against it:

- each `[[events]]` run writes one package, `packages/<campaign>/<id>.json`;
- each `[[narrate]]` run plans the package of the `events` run it names, with `narrate --package`, and writes
  `narrate/<campaign>/<id>/` (the plan and the requests). It never passes `--send`, so nothing is contacted.

The campaigns are measured at once. Within a campaign every `events` run starts at once, and each `narrate` run as
soon as the package it plans is written. `--jobs` bounds the commands running together (default: the CPU count). Each
`events` run holds a whole campaign in memory, so lower it on a machine with little RAM. The log shows one tree per
campaign, `events` and `narrate` runs with their times, written in one piece when the campaign is done.

Every command is given `--config config.toml`, and `TINARRATIVE_CONFIG` is removed from its environment. A failing
run is recorded with its exit code and the end of its stderr. For an over-budget `narrate` run, the record also holds
the tokens the largest interval needs. `metrics.json` holds, per campaign and run:

| Run | Metrics |
| --- | --- |
| `events` | `bytes` as written; `chars` of the compact JSON a request embeds; `est_tokens` (`chars` ÷ `--chars-per-token`, 3 by default, as `narrator.chars_per_token`); `counts` of narrative events (also by significance), atomic and inferred events, glossary entries and saves; `members` |
| `narrate` | `chapters`, `estimate_total` and `estimate_max` from `plan.json`, `reductions`, the request `chars` split into `system`, `block` (request block and framing) and `package`, `members` summed over the chapter packages, `per_chapter`, `prompt_version` |

`members` maps each member path to its compact characters, key included, summed over list elements:
`saves[].situation.nations[].allies` is the allies of every nation of every save. Paths go at most four keys deep. A
mapping keyed by ID (more than 30 keys) is not broken down.

Characters and estimated tokens are exact for what is sent. Real tokens depend on the model's tokenizer, so compare
the estimates with each other, not with a provider's bill.

## On pull requests

[`.github/workflows/package-metrics.yml`](../.github/workflows/package-metrics.yml) installs the pull request's base and
head into two virtual environments and measures both with the head checkout's CLI, samples, matrix and settings. It posts
`compare`'s report as one comment, which every later push edits, and writes the report to the job summary. It
uploads both sides' outputs as the `package-metrics` artifact, kept 14 days, so any package or request can be diffed
locally. The check never fails because a size changed.

The report:

- **Highlights**: the runs whose estimate changed by at least 1%, or that have a member whose change is at least 1% of
  the package, largest first. Each row names the members that changed most. A member's change is shown on the most
  specific member that explains it, so dropping one field reads as that field and not as every mapping above it.
- **`events` packages** and **`narrate` plans**: every run, base → head where the two differ.
- **Member changes**: per changed run, the members holding at least 1% of the package and every changed member. When
  nothing changed, the section shows the members of each campaign's first `events` package instead.
- **Notes**: runs that fail on one side only, a changed narrator prompt, or matrices or samples that differ between
  the sides.

## Running it locally

```sh
make package-metrics PYTHON=.venv/bin/python        # this tree → build/package-metrics/
```

To compare with another revision, install that revision into its own environment and measure it with this script:

```sh
git worktree add ../tinarrative-main main
python3 -m venv ../tinarrative-main/.venv && ../tinarrative-main/.venv/bin/python -m pip install -q ../tinarrative-main
    .venv/bin/python -m tinarrative.cli benchmark metrics measure --python ../tinarrative-main/.venv/bin/python \
    --out build/package-metrics-main --label main
.venv/bin/python -m tinarrative.cli benchmark metrics compare build/package-metrics-main/metrics.json \
    build/package-metrics/metrics.json --out build/package-metrics/report.md
```

## Adding a run

Add an entry to `matrix.toml`. An `[[events]]` entry needs an `id` and its `args`. A `[[narrate]]` entry also names the
`package` (an `events` id) it plans. Every combination is run against every campaign, so a run that cannot succeed for
one campaign records its failure. That failure is still a measurement: the budget a campaign needs falls as the
package shrinks.

## Samples

These are the only real saves the repository holds, and an exception to the fixture rules in
[docs/testing.md](../docs/testing.md#synthetic-and-real-save-policy): they are never fixtures and no test reads their
content. Only the manifest test does, by hashing them. They are compressed, whole saves, left unedited. Each campaign
directory holds consecutive saves of one campaign, so that grouping finds a single campaign there.

To add or refresh a campaign, run `tinarrative benchmark sample NAME PATH`. Pass a directory to select one of its
detected campaigns with `--campaign SELECTOR` (or the interactive picker), or pass one or more save files directly.
An import replaces the current files for `NAME`; invalid explicitly listed saves reject the import before replacement.
In a terminal, progress on stderr names the current phase and file count.

For example:

```sh
tinarrative benchmark sample protectorate ~/saves --campaign protectorate
```

The utility compresses the selected saves, moves them into the sample directory and refreshes `samples.json`. To
add or refresh a campaign manually:

1. Pick saves that differ in what they exercise: game phase, number of developments, chapter count. Avoid adding a
   campaign that only repeats an existing one. Every campaign multiplies the run time.
2. Check that none of them carries a machine path or an account identifier. This must print nothing:

   ```sh
   grep -l -i -E '/Users/|/home/|C:\\\\|AppData|steamid|steam_id|"steam' real_saves/<files>
   ```

3. Run `tinarrative benchmark sample <campaign> <save-directory>` (or list the selected save files). Supply
   `--description` to write the campaign description; otherwise add one to `samples.json` if it is missing.
4. Review the campaign's runs in `matrix.toml` and add entries where needed. Run
   `tinarrative benchmark metrics samples` until it reports nothing.

A pull request that changes the samples or the matrix measures both sides with the new ones, so its report compares
code only. The next pull requests measure against the new samples from then on.
