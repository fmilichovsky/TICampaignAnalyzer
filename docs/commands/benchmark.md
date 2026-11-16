# `tinarrative benchmark`

Maintainer tooling for the real sample campaigns in `benchmarks/`: import them, measure how big the narrator
packages are and how long `events` takes, and calibrate the stake references against them. Pull requests get both measurements automatically; what they measure is in
[benchmarks/README.md](../../benchmarks/README.md). Run these commands from the repository root.

## `benchmark sample`

<!-- generated: synopsis benchmark sample -->
```
tinarrative benchmark sample [--description TEXT] [--campaign SELECTOR] name PATH [PATH ...]
```
<!-- end generated -->

Adds a campaign to the samples, or replaces it. Afterwards, add a description in `samples.json` if it has none, and
add runs for the campaign to `benchmarks/matrix.toml` if needed.

```sh
# Import one campaign from a save directory.
tinarrative benchmark sample protectorate ~/saves --campaign protectorate --description "Protectorate, early game"

# Refresh a sample from chosen saves.
tinarrative benchmark sample resist ~/campaign/save1.json ~/campaign/save2.json
```

<!-- generated: options benchmark sample -->
| Option | Meaning |
| --- | --- |
| `NAME` | The sample campaign's directory name under benchmarks/samples/. |
| `PATH...` | One directory, or save files. |
| `--description TEXT` | Campaign description for samples.json (default: keep the existing one). |
| `--campaign SELECTOR` | The campaign to import from a directory that holds several. |
<!-- end generated -->

<!-- generated: exit-codes benchmark sample -->
| Code | When |
| --- | --- |
| 0 | The sample and samples.json were updated. |
| 2 | Usage error, or a campaign selector that cannot be resolved without a terminal. |
| 4 | A named path cannot be read, or a named directory holds no usable save. |
| 5 | A named file is not a supported save or has no game time. |
| 9 | The sample directory or samples.json cannot be written. |
<!-- end generated -->

## `benchmark metrics samples`

<!-- generated: synopsis benchmark metrics samples -->
```
tinarrative benchmark metrics samples [--samples PATH] [--update]
```
<!-- end generated -->

Checks the sample files against `samples.json`, for example after editing them by hand.

```sh
tinarrative benchmark metrics samples
```

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

## `benchmark metrics measure`

<!-- generated: synopsis benchmark metrics measure -->
```
tinarrative benchmark metrics measure [--python PYTHON] [--samples PATH] [--matrix PATH]
                                      [--config PATH] --out PATH [--label TEXT]
                                      [--chars-per-token FLOAT] [--jobs N]
```
<!-- end generated -->

Runs every matrix entry against every sample campaign and writes the packages and `metrics.json`. `make
package-metrics` runs it for the working tree.

```sh
tinarrative benchmark metrics measure --out build/package-metrics --label "$(git rev-parse --short HEAD)"
```

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

## `benchmark metrics compare`

<!-- generated: synopsis benchmark metrics compare -->
```
tinarrative benchmark metrics compare [--out PATH] [--run-url URL] [--threshold PERCENT] base head
```
<!-- end generated -->

Compares two `metrics.json` files, such as a base and a head, in Markdown.

```sh
tinarrative benchmark metrics compare base/metrics.json head/metrics.json --out compare.md
```

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

## `benchmark runtime measure`

<!-- generated: synopsis benchmark runtime measure -->
```
tinarrative benchmark runtime measure --out FILE [--python PYTHON] [--label TEXT]
                                      [--base-python PYTHON] [--base-label TEXT] [--samples PATH]
                                      [--campaign SELECTOR] [--matrix PATH] [--config PATH]
                                      [--run ID] [--repeats N]
```
<!-- end generated -->

Times one `events` run per sample campaign. With `--base-python`, a base and a head are timed in alternation. `make
runtime-metrics` runs it for the working tree.

```sh
# Time the working tree.
tinarrative benchmark runtime measure --out build/runtime.json

# Time a base against a head, three times each.
tinarrative benchmark runtime measure --out build/runtime.json --base-python ../base/.venv/bin/python --repeats 3
```

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

## `benchmark runtime report`

<!-- generated: synopsis benchmark runtime report -->
```
tinarrative benchmark runtime report [--out PATH] [--run-url URL] FILE
```
<!-- end generated -->

Writes the Markdown report of a runtime JSON file: wall time, time per stage and peak memory per campaign.

```sh
tinarrative benchmark runtime report build/runtime.json --out build/runtime.md
```

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

## `benchmark calibrate open`

<!-- generated: synopsis benchmark calibrate open -->
```
tinarrative benchmark calibrate open [--samples PATH] [--out PATH] [--rebuild] [--no-open]
```
<!-- end generated -->

Writes the stake calibration page into `--out`, prints its path and opens it in the default browser. The page is a
static file that works from disk with no network: pick a measure, slide its reference, and see the three totals,
which takeover waves lose members, the level counts per type, and the real events on each side of each cut-off.
Level counts also shows what moves: a band under each bar marks the events that rose or dropped into a level, and
the exact changes stand beside it. Its rows are ordered by events, or by moves once the reference settles. Hover a
bar, a segment, a band or a change for its six largest events; click it for the full list. Every list of events
uses the same row: share, level, label, the level change, campaign and date, and the event type. Lists of several
types show the type under the label. Under each cut-off, a line lists the types of its rows, or the type of the row
under the pointer or in focus. Click a type to filter by it. Click an event row, or press Enter on it, to open the
event inspector: a drawer on the right with the full label, type, tier, campaign, date, interval and event ID; the
level now against the code's, the score and the base; every stake, with the focused measure in bold and its share set against the current reference and window; the entities;
and, for a narrative event, its cited constituents. When a cited event sets the level, the inspector names it with
its stake. The level, score and deciding event follow the slider. A cited or deciding event opens in the inspector
when you click it, and **Back** returns along the way you came. A full list stays open beside the inspector, with the
inspected row marked, so you can open its events one after another. **Close** or Escape closes the inspector and
returns focus to the row, or to what opened the list. The inspected event is not part of the URL hash. The
URL hash holds the whole state, so a reloaded page comes back as it was, and **Copy readout** copies the snippet,
the shared paragraph and the hash, ready for `report --state`.

The page uses the same cache as `report`. A fresh cache opens at once. A stale one opens the old page at once,
then rebuilds behind it: the page shows a banner while `status.js` says `rebuilding` and offers a reload when the
new table is ready, or shows the message when the rebuild failed. With no cache, the table is built first. The
page files are copied from the package on every run. When no browser can be opened, the command warns, still prints
the path and exits 0.

```sh
# Build the table if needed and open the page.
tinarrative benchmark calibrate open

# Print the page path only, for a browser on another machine or a script.
tinarrative benchmark calibrate open --no-open
```

<!-- generated: options benchmark calibrate open -->
| Option | Meaning |
| --- | --- |
| `--samples PATH` | Benchmark samples directory (default benchmarks/samples). |
| `--out PATH` | The calibration cache directory (default build/calibration). |
| `--rebuild` | Rebuild the cache even when it is fresh. |
| `--no-open` | Print the page path without opening a browser. |
<!-- end generated -->

<!-- generated: exit-codes benchmark calibrate open -->
| Code | When |
| --- | --- |
| 0 | The page was written and its table is current; a browser that cannot be opened only warns. |
| 2 | Usage error, a sample that does not match samples.json, or a failed extraction (status.js says failed; the old table stays, and an old page was already opened). |
| 4 | --samples is not a directory or its samples.json cannot be read. |
| 9 | --out cannot be written. |
<!-- end generated -->

## `benchmark calibrate report`

<!-- generated: synopsis benchmark calibrate report -->
```
tinarrative benchmark calibrate report [--samples PATH] [--out PATH] [--rebuild]
                                       [--reference MEASURE=VALUE] [--campaign NAME]
                                       [--type EVENT_TYPE] [--clamp {on,off}] [--state HASH]
                                       [--format {text,json}]
```
<!-- end generated -->

Replays the stake calibration table of the sample campaigns at other references and prints what would change: which
events move level, how the narrator package grows or shrinks, which takeover waves lose members, and the events
nearest each cut-off. It ends with the changed references written as measure registry entries, ready to paste.

The table is cached in `--out` and rebuilt only when the package or `samples.json` changed, or with `--rebuild`; a
rebuild takes a few seconds per campaign. `status.js` in `--out` says whether the table is fresh, rebuilding or
failed. A failed rebuild keeps the previous table.

`--state` takes the URL hash of the calibration page, so a state explored there can be read here in full; the other
flags override what it sets.

The table also scores the draft stakes declared in `DRAFT_STAKES` (`tinarrative.benchmarking.calibration.drafts`):
each one tries a stake on existing narrative event types before a kind declares it. Its rows sit beside the real
events and never change their levels, and the state holds a base level for each draft. A draft that names an unknown
or non-narrative event type, or repeats a name, fails the rebuild.

```sh
# What would a lower power reference do?
tinarrative benchmark calibrate report --reference power=0.002

# Two measures, one campaign, as JSON.
tinarrative benchmark calibrate report --reference power=0.002,hab=0.03 --campaign resist --format json

# A state copied from the calibration page, with the clamp turned off.
tinarrative benchmark calibrate report --state 'ref=power:0.002' --clamp off
```

<!-- generated: options benchmark calibrate report -->
| Option | Meaning |
| --- | --- |
| `--samples PATH` | Benchmark samples directory (default benchmarks/samples). |
| `--out PATH` | The calibration cache directory (default build/calibration). |
| `--rebuild` | Rebuild the cache even when it is fresh. |
| `--reference MEASURE=VALUE` | A measure's reference share; comma-separated, repeatable (default: the code's). |
| `--campaign NAME` | Replay only these sample campaigns; comma-separated, repeatable (default: every one). |
| `--type EVENT_TYPE` | Count only these event types; comma-separated, repeatable (default: every type). |
| `--clamp on\|off` | Clamp the stake's scale, as the page's toggle (default on). |
| `--state HASH` | A calibration page's URL hash; the other flags override what it sets. |
| `--format text\|json` | Report format (default text). |
<!-- end generated -->

<!-- generated: exit-codes benchmark calibrate report -->
| Code | When |
| --- | --- |
| 0 | The readout was printed. |
| 2 | Usage error, a sample that does not match samples.json, an unknown measure, campaign or type, an invalid --state, a measure given twice, a table at another schema version (run with --rebuild), or a failed extraction (status.js says failed; the old table stays). |
| 4 | --samples is not a directory or its samples.json cannot be read. |
| 9 | --out cannot be written. |
<!-- end generated -->
