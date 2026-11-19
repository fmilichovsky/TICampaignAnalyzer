# `tinarrative benchmark`

Maintainer tooling for the real sample campaigns in `benchmarks/`: import them, measure how big the narrator
packages are and how long `events` takes, and calibrate the share references against them. Pull requests get both measurements automatically; what they measure is in
[benchmarks/README.md](../../benchmarks/README.md). Run these commands from the repository root.

## `benchmark sample`

<!-- generated: synopsis benchmark sample -->
```
tinarrative benchmark sample [--description TEXT] [--campaign SELECTOR] name PATH [PATH ...]
```
<!-- end generated -->

Adds a campaign to the samples, or replaces it. Afterwards, add a description in `samples.json` if it has none, and
add runs for the campaign to `benchmarks/matrix.toml` if needed. On refresh, unchanged files with the same name are
reused without recompression.

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
tinarrative benchmark calibrate open [--samples PATH] [--out PATH] [--rebuild] [--port PORT]
                                     [--no-open]
```
<!-- end generated -->

Serves the share calibration page on `127.0.0.1` and opens it: a page for choosing the share references of the
measures against the sample campaigns. Slide a measure's reference to see which events change significance level,
how the narrator package and the takeover waves change, and which events sit nearest each cut-off; open an event to
see why it has its level. Base levels, under References, switches an event type's base level, as `report --base`
does; the event inspector switches the type of the event it shows, and says when a context rule decided the event's
level, so the switch passes it by. The page's URL hash holds the explored state, which `report --state` reads.

The command replays the table in Python for every change on the page; the page only draws the answer
([ADR-0022](../adr/0022-the-calibration-table-is-replayed-once-in-python.md)). It keeps serving until it is
interrupted with Ctrl-C. A stale table is served while it is rebuilt, and the page offers to reload once the new one
is ready. A failed rebuild keeps the old table served and the command exits with 2 when interrupted; with no old
table it stops at once. A slider replays when it is let go. Opened from disk, or once the command has stopped, the
page says so and names the command to run.

```sh
# Build the table if needed, serve the page and open it.
tinarrative benchmark calibrate open

# Print the page's URL only, for a browser started by hand or a launch configuration.
tinarrative benchmark calibrate open --no-open

# Serve on another port.
tinarrative benchmark calibrate open --port 8770
```

<!-- generated: options benchmark calibrate open -->
| Option | Meaning |
| --- | --- |
| `--samples PATH` | Benchmark samples directory (default benchmarks/samples). |
| `--out PATH` | The calibration cache directory (default build/calibration). |
| `--rebuild` | Rebuild the cache even when it is fresh. |
| `--port PORT` | The port on 127.0.0.1 to serve the page on (default 8769). |
| `--no-open` | Print the page's URL without opening a browser. |
<!-- end generated -->

<!-- generated: exit-codes benchmark calibrate open -->
| Code | When |
| --- | --- |
| 0 | The page was served with a current table until interrupted; a browser that cannot be opened only warns. |
| 2 | Usage error, a sample that does not match samples.json, or a failed extraction (status.js says failed). With no old table the command stops at once; an old table is served until interrupted. |
| 4 | --samples is not a directory or its samples.json cannot be read. |
| 9 | --out cannot be written, or the port cannot be served on. |
<!-- end generated -->

## `benchmark calibrate report`

<!-- generated: synopsis benchmark calibrate report -->
```
tinarrative benchmark calibrate report [--samples PATH] [--out PATH] [--rebuild]
                                       [--reference MEASURE=VALUE] [--campaign NAME]
                                       [--type EVENT_TYPE] [--base TYPE=LEVEL] [--state HASH]
                                       [--format {text,json}]
```
<!-- end generated -->

Replays the share calibration table of the sample campaigns at other references and prints what would change: which
events move level, how the narrator package grows or shrinks, which takeover waves lose members, and the events
nearest each cut-off. It ends with the changed references written as measure registry entries, ready to paste,
followed by one comment line for each event type whose base level was switched.

The table is cached in `--out`, shared with the page, and rebuilt when the package or `samples.json` changed, or
with `--rebuild`.

`--state` reads a state explored on the calibration page; the other flags override it.

`--base TYPE=LEVEL` shows what changing an event type's base level would do. Events whose level a context rule
decides keep it. `--base` applies even to types that `--type` leaves out of the count. The readout's state lists the switched
base levels against the code's.

The table also scores any [draft shares](#draft-shares) beside the real events, without changing their levels; the
state holds a base level for each draft, and its own section of the readout reports each one. A draft that cannot be
scored fails the rebuild.

```sh
# What would a lower power reference do?
tinarrative benchmark calibrate report --reference power=0.002

# Two measures, one campaign, as JSON.
tinarrative benchmark calibrate report --reference power=0.002,hab=0.03 --campaign resist --format json

# What if nation changes were minor events?
tinarrative benchmark calibrate report --base region.nation_changed=minor

# A state copied from the calibration page.
tinarrative benchmark calibrate report --state 'ref=power:0.002'
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
| `--base TYPE=LEVEL` | Try a base level on an event type; comma-separated, repeatable (default: the code's). |
| `--state HASH` | A calibration page's URL hash; the other flags override what it sets. |
| `--format text\|json` | Report format (default text). |
<!-- end generated -->

<!-- generated: exit-codes benchmark calibrate report -->
| Code | When |
| --- | --- |
| 0 | The readout was printed. |
| 2 | Usage error, a sample that does not match samples.json, an unknown measure, campaign or type, a base level that is not a level, an invalid --state, a measure or switched type given twice, a table at another schema version (run with --rebuild), or a failed extraction (status.js says failed; the old table stays). |
| 4 | --samples is not a directory or its samples.json cannot be read. |
| 9 | --out cannot be written. |
<!-- end generated -->

### Draft shares

A draft share is a share tried on the events of existing narrative types before a kind declares it. Its rows are
scored beside the real events and never enter their counts, totals, moves or cut-offs, so a draft changes no real
panel or readout section.

On the page, each draft with a candidate on the focused measure has a panel under the cut-offs, marked `draft #N`
with its issue; two drafts on the same measure sit side by side. A panel holds:

- a base selector: the level the draft's rows start from. `own` marks the draft's own base. A row marked `ruled` is
  decided by its kind's context rule, so the base does not apply to it. The chosen base goes into the URL hash
  (`base=<draft>:<level>`).
- the level counts of its rows at that base, each with its change against the draft's own base;
- how many of its rows a cited event sets instead of the draft's own share;
- its own rows nearest the two cut-offs the tide tables show, badged `draft #N` and, where it applies, `ruled`. A
  row opens the event it shadows in the inspector.

The readout's Draft shares section reports the same numbers, with every draft's nearest rows at every cut-off of its
measures, and the summary paragraph names every draft with its issue, so a draft left behind after its issue closed
still shows.

#### Adding a draft

One small PR:

1. If the share needs a measure the code does not have, add it: a `Measure` member, its `MeasureSpec` entry in
   `MEASURES` (`narrative/measures.py`) and the branch that reads its shares in `narrative/significance.py`.
2. Add a `DraftShare` to `DRAFT_SHARES` in `benchmarking/calibration/drafts.py`: a slug `name`, a `label`, the
   `issue` it calibrates for, the existing narrative `event_types` it is tried on, one `ShareReading` per
   candidate (the highest scale wins) and, if its types' kinds do not share one, a `base`.
3. Run `tinarrative benchmark calibrate open`, which rebuilds the table, and calibrate the draft's reference and base
   on the page.

#### Graduating a draft

One PR as well: add a `ShareOf` member, move the draft's share reading into `SHARE_IMPLEMENTATIONS`, set `share=`
(and `base=` if the calibrated base differs) on the kinds of the draft's types, write the calibrated reference into
the measure's registry entry, and delete the draft from `DRAFT_SHARES`.
