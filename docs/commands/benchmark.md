# `tinarrative benchmark`

## `tinarrative benchmark sample`

```
tinarrative benchmark sample <name> <path> [<path>...] [--description TEXT] [--campaign SELECTOR]
```

Compresses saves into `benchmarks/samples/<name>/` and refreshes `samples.json`. If that campaign already exists,
its sample directory is replaced. Explicit save paths are all checked before replacement; an invalid save rejects the
import. A directory is read one level deep, and unusable files are skipped and reported.

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
  --out PATH [--label TEXT] [--chars-per-token N] [--jobs N]
```

Runs every matrix entry against every sample campaign, writes packages and narrator plans under `PATH`, then writes
`metrics.json`. The selected `--python` runs `events` and `narrate`; the current CLI performs the measurement.
Progress appears on stderr in a terminal. Failed runs are recorded in the metrics output.

### Compare

```sh
tinarrative benchmark metrics compare BASE HEAD [--out PATH] [--threshold PERCENT] [--run-url URL]
```

Writes a Markdown comparison to stdout or `PATH`. The report highlights package-size changes at or above the threshold
(1% by default). `--run-url` links the report to its CI artifact.
