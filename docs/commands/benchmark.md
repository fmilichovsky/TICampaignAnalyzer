# `tinarrative benchmark`

## `tinarrative benchmark sample`

<!-- generated: synopsis benchmark sample -->
```
tinarrative benchmark sample [--description TEXT] [--campaign SELECTOR] name PATH [PATH ...]
```
<!-- end generated -->

Compresses saves into `benchmarks/samples/<name>/` and refreshes `samples.json`. If that campaign already exists,
its sample directory is replaced. Explicit save paths are all checked before replacement; an invalid save rejects the
import. The benchmark data directory is resolved from the current working directory. A directory is read one level
deep, and unusable files are skipped and reported.

## Options

<!-- generated: options benchmark sample -->
| Option | Meaning |
| --- | --- |
| `NAME` | The sample campaign's directory name under benchmarks/samples/. |
| `PATH...` | One directory, or save files. |
| `--description TEXT` | Campaign description for samples.json (default: keep the existing one). |
| `--campaign SELECTOR` | The campaign to import from a directory that holds several. |
<!-- end generated -->

After a successful import, add a description in `samples.json` if one is missing, review `benchmarks/matrix.toml`,
and add runs for the campaign if needed. Run `tinarrative benchmark metrics samples` to verify the manifest.

## Examples

```sh
tinarrative benchmark sample protectorate ~/saves --campaign protectorate \
  --description "Protectorate campaign, early game"
tinarrative benchmark sample resist ~/campaign/save1.json ~/campaign/save2.json
```

## Exit codes

<!-- generated: exit-codes benchmark sample -->
| Code | When |
| --- | --- |
| 0 | The sample and samples.json were updated. |
| 2 | Usage error, or a campaign selector that cannot be resolved without a terminal. |
| 4 | A named path cannot be read, or a named directory holds no usable save. |
| 5 | A named file is not a supported save or has no game time. |
| 9 | The sample directory or samples.json cannot be written. |
<!-- end generated -->

## `tinarrative benchmark metrics`

### Verify samples

<!-- generated: synopsis benchmark metrics samples -->
```
tinarrative benchmark metrics samples [--samples PATH] [--update]
```
<!-- end generated -->

Checks every compressed save against `samples.json`. `--update` rebuilds the manifest while retaining campaign
descriptions and the configured size limit. 
<!-- generated: options benchmark metrics samples -->
| Option | Meaning |
| --- | --- |
| `--samples PATH` | Benchmark samples directory (default benchmarks/samples). |
| `--update` | Rewrite samples.json from the files. |
<!-- end generated -->

<!-- generated: exit-codes benchmark metrics samples -->
| Code | When |
| --- | --- |
| 0 | Every sample matches samples.json. |
| 2 | Usage error, or a sample does not match samples.json. |
| 9 | The samples or samples.json cannot be read or written. |
<!-- end generated -->

### Measure

<!-- generated: synopsis benchmark metrics measure -->
```
tinarrative benchmark metrics measure [--python PYTHON] [--samples PATH] [--matrix PATH]
                                      [--config PATH] --out PATH [--label TEXT]
                                      [--chars-per-token FLOAT] [--jobs N]
```
<!-- end generated -->

By default, reads `benchmarks/samples`, `benchmarks/matrix.toml`, and `benchmarks/config.toml` relative to the current
working directory. Runs every matrix entry against every sample campaign, writes packages and narrator plans under `PATH`, then writes
`metrics.json`. The selected `--python` runs `events` and `narrate`; the current CLI performs the measurement.
`--chars-per-token` accepts a decimal estimate (minimum 1). Progress appears on stderr in a terminal. Failed runs are
recorded in the metrics output.

<!-- generated: options benchmark metrics measure -->
| Option | Meaning |
| --- | --- |
| `--python PYTHON` | The interpreter whose tinarrative is measured (default: this one). |
| `--samples PATH` | Benchmark samples directory (default benchmarks/samples). |
| `--matrix PATH` | The run matrix (default benchmarks/matrix.toml). |
| `--config PATH` | Settings file for the measured runs (default benchmarks/config.toml). |
| `--out PATH` | Directory for the packages, plans and metrics.json. |
| `--label TEXT` | What is measured, such as a commit (default working tree). |
| `--chars-per-token FLOAT` | Characters per estimated token (default 2.4). |
| `--jobs N` | Commands run at once (default: the CPU count). |
<!-- end generated -->

<!-- generated: exit-codes benchmark metrics measure -->
| Code | When |
| --- | --- |
| 0 | Metrics.json was written; failed runs are recorded in it. |
| 2 | Usage error, a sample that does not match samples.json, or an invalid matrix. |
| 9 | The outputs cannot be written. |
<!-- end generated -->

### Compare

<!-- generated: synopsis benchmark metrics compare -->
```
tinarrative benchmark metrics compare [--out PATH] [--run-url URL] [--threshold PERCENT] base head
```
<!-- end generated -->

Writes a Markdown comparison to stdout or `PATH`. The report highlights package-size changes at or above the threshold
(1% by default). `--run-url` links the report to its CI artifact.

<!-- generated: options benchmark metrics compare -->
| Option | Meaning |
| --- | --- |
| `BASE` | The base metrics.json. |
| `HEAD` | The head metrics.json. |
| `--out PATH` | Write the report here (default: stdout). |
| `--run-url URL` | Link the report to this CI run. |
| `--threshold PERCENT` | Highlight size changes of at least this percentage (default 1.0). |
<!-- end generated -->

<!-- generated: exit-codes benchmark metrics compare -->
| Code | When |
| --- | --- |
| 0 | The report was written. |
| 2 | Usage error. |
| 4 | A metrics file cannot be read or is not a metrics file, or the report cannot be written. |
<!-- end generated -->

## `tinarrative benchmark runtime`

### Measure

<!-- generated: synopsis benchmark runtime measure -->
```
tinarrative benchmark runtime measure --out FILE [--python PYTHON] [--label TEXT]
                                      [--base-python PYTHON] [--base-label TEXT] [--samples PATH]
                                      [--campaign SELECTOR] [--matrix PATH] [--config PATH]
                                      [--run ID] [--repeats N]
```
<!-- end generated -->

Times one `events` run per campaign and writes the runtime JSON to `FILE`. `--run` names the matrix's `events` run
to time (default `major`). `--samples` is either a benchmark samples directory (it holds `samples.json`, which is
verified first) or one directory of saves. For a directory of saves that holds several campaigns, `--campaign` is
passed on to `events`. With `--base-python`, the base and `--python` are measured in alternation. Each side keeps
the fastest of `--repeats` runs (default 1). Commands run one at a time. A failed run is recorded with its exit
code and the end of its stderr. See [benchmarks](../../benchmarks/README.md#runtime) for what is measured.

<!-- generated: options benchmark runtime measure -->
| Option | Meaning |
| --- | --- |
| `--out FILE` | The runtime JSON file to write. |
| `--python PYTHON` | The interpreter whose tinarrative is measured (default: this one). |
| `--label TEXT` | What is measured, such as a commit (default working tree). |
| `--base-python PYTHON` | A second interpreter measured as the base, alternating with --python. |
| `--base-label TEXT` | What the base is, such as a commit (default base). |
| `--samples PATH` | Benchmark samples (a directory with samples.json) or one directory of saves (default benchmarks/samples). |
| `--campaign SELECTOR` | Passed to events --campaign, for a directory of several campaigns. |
| `--matrix PATH` | The run matrix (default benchmarks/matrix.toml). |
| `--config PATH` | Settings file for the measured runs (default benchmarks/config.toml). |
| `--run ID` | The matrix's events run to time (default major). |
| `--repeats N` | Runs per side; the fastest is kept (default 1). |
<!-- end generated -->

<!-- generated: exit-codes benchmark runtime measure -->
| Code | When |
| --- | --- |
| 0 | The runtime JSON was written; failed runs are recorded in it. |
| 2 | Usage error, a sample that does not match samples.json, or a --run the matrix lacks. |
| 4 | --samples is not a directory. |
| 9 | The runtime JSON cannot be written. |
<!-- end generated -->

### Report

<!-- generated: synopsis benchmark runtime report -->
```
tinarrative benchmark runtime report [--out PATH] [--run-url URL] FILE
```
<!-- end generated -->

Writes the Markdown report of a runtime JSON file to stdout or `PATH`: wall time, seconds per stage and peak memory
per campaign, base → head when both were measured. `--run-url` links the report to its CI artifact.

<!-- generated: options benchmark runtime report -->
| Option | Meaning |
| --- | --- |
| `FILE` | The runtime JSON file. |
| `--out PATH` | Write the report here (default: stdout). |
| `--run-url URL` | Link the report to this CI run. |
<!-- end generated -->

<!-- generated: exit-codes benchmark runtime report -->
| Code | When |
| --- | --- |
| 0 | The report was written. |
| 2 | Usage error. |
| 4 | The runtime JSON cannot be read or is not a runtime file, or the report cannot be written. |
<!-- end generated -->
