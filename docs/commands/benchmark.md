# `tinarrative benchmark sample`

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
and add runs for the campaign if needed. Run `python scripts/package_metrics.py samples` to verify the manifest.

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
