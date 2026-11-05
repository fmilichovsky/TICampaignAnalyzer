# `tinarrative benchmark`

## `tinarrative benchmark sample`

```
tinarrative benchmark sample <name> <path> [<path>...] [--description TEXT] [--campaign SELECTOR]
```

Compresses saves into `benchmarks/samples/<name>/` and refreshes `samples.json`. If that campaign already exists,
its sample directory is replaced. Explicit save paths are all checked before replacement; an invalid save rejects the
import. The benchmark data directory is resolved from the current working directory. A directory is read one level
deep, and unusable files are skipped and reported.

## Inputs and options

| Argument | Meaning |
| --- | --- |
| `name` | One directory name for the sample campaign. |
| `path...` | Pass one directory, or one or more save files. A directory containing multiple campaigns uses the existing campaign selector and picker. |
| `--campaign SELECTOR` | Select a campaign in a directory, using the same keys, prefixes, listing indices, and `latest` selector as `events`. |
| `--description TEXT` | Set the campaign description in `samples.json`. Without it, an existing description is preserved. |

After a successful import, add a description in `samples.json` if one is missing, review `benchmarks/matrix.toml`,
and add runs for the campaign if needed. Run `tinarrative benchmark metrics samples` to verify the manifest.

## Examples

```sh
tinarrative benchmark sample protectorate ~/saves --campaign protectorate \
  --description "Protectorate campaign, early game"
tinarrative benchmark sample resist ~/campaign/save1.json ~/campaign/save2.json
```

## Exit codes

| Code | When |
| --- | --- |
| 0 | The sample files and manifest were updated. |
| 2 | Invalid command arguments or a campaign selector that cannot be resolved non-interactively. |
| 4 | A path cannot be read, or a directory contains no usable saves. |
| 5 | An explicitly listed save is unsupported or has no parseable game time. |
| 9 | Compression, manifest, or sample-directory update failed. |

## `tinarrative benchmark metrics`

### Verify samples

```sh
tinarrative benchmark metrics samples [--samples PATH] [--update]
```

Checks every compressed save against `samples.json`. `--update` rebuilds the manifest while retaining campaign
descriptions and the configured size limit. A mismatch exits with code 2.

### Measure

```sh
tinarrative benchmark metrics measure [--python PYTHON] [--samples PATH] [--matrix PATH] [--config PATH]
  --out PATH [--label TEXT] [--chars-per-token FLOAT] [--jobs N]
```

By default, reads `benchmarks/samples`, `benchmarks/matrix.toml`, and `benchmarks/config.toml` relative to the current
working directory. Runs every matrix entry against every sample campaign, writes packages and narrator plans under `PATH`, then writes
`metrics.json`. The selected `--python` runs `events` and `narrate`; the current CLI performs the measurement.
`--chars-per-token` accepts a decimal estimate (minimum 1). Progress appears on stderr in a terminal. Failed runs are
recorded in the metrics output.

### Compare

```sh
tinarrative benchmark metrics compare BASE HEAD [--out PATH] [--threshold PERCENT] [--run-url URL]
```

Writes a Markdown comparison to stdout or `PATH`. The report highlights package-size changes at or above the threshold
(1% by default). `--run-url` links the report to its CI artifact.

## `tinarrative benchmark runtime`

### Measure

```sh
tinarrative benchmark runtime measure --out FILE [--python PYTHON] [--label TEXT] [--base-python PYTHON]
  [--base-label TEXT] [--samples PATH] [--campaign SELECTOR] [--matrix PATH] [--run ID] [--config PATH] [--repeats N]
```

Times one `events` run per campaign and writes the runtime JSON to `FILE`. `--run` names the matrix's `events` run
to time (default `major`). `--samples` is either a benchmark samples directory (it holds `samples.json`, which is
verified first) or one directory of saves. For a directory of saves that holds several campaigns, `--campaign` is
passed on to `events`. With `--base-python`, the base and `--python` are measured in alternation. Each side keeps
the fastest of `--repeats` runs (default 1). Commands run one at a time. A failed run is recorded with its exit
code and the end of its stderr. See [benchmarks](../../benchmarks/README.md#runtime) for what is measured.

### Report

```sh
tinarrative benchmark runtime report FILE [--out PATH] [--run-url URL]
```

Writes the Markdown report of a runtime JSON file to stdout or `PATH`: wall time, seconds per stage and peak memory
per campaign, base → head when both were measured. `--run-url` links the report to its CI artifact.

### Exit codes

| Code | When |
| --- | --- |
| 0 | The runtime JSON or report was written. |
| 2 | Invalid arguments, a sample that does not match `samples.json`, or a `--run` the matrix does not have. |
| 4 | `--samples` is not a directory, or the runtime JSON cannot be read. |
| 9 | The runtime JSON cannot be written. |
