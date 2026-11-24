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
                                      [--config PATH] --out PATH [--label TEXT] [--campaign NAME]
                                      [--chars-per-token FLOAT] [--jobs N]
```
<!-- end generated -->

Runs every matrix entry against every sample campaign and writes the packages and `metrics.json`. `make
package-metrics` runs it for the working tree.

```sh
tinarrative benchmark metrics measure --out build/package-metrics --label "$(git rev-parse --short HEAD)"
```

`--campaign NAME` measures only that sample campaign (repeat it for several); a name `samples.json` does not list is a
usage error. Combine per-campaign results with [`benchmark metrics merge`](#benchmark-metrics-merge).

```sh
tinarrative benchmark metrics measure --campaign protectorate --out build/protectorate --label "$(git rev-parse --short HEAD)"
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
| `--campaign NAME` | Measure only this sample campaign; repeat for several (default: every campaign). |
| `--chars-per-token FLOAT` | Characters per estimated token (default 2.4). |
| `--jobs N` | Commands run at once (default: the CPU count). |
<!-- end generated -->

<!-- generated: exit-codes benchmark metrics measure -->
| Code | When |
| --- | --- |
| 0 | Metrics.json was written; failed runs are recorded in it. |
| 2 | Usage error, a sample that does not match samples.json, an invalid matrix or an unknown --campaign. |
| 9 | The outputs cannot be written. |
<!-- end generated -->

## `benchmark metrics merge`

<!-- generated: synopsis benchmark metrics merge -->
```
tinarrative benchmark metrics merge --out PATH METRICS [METRICS ...]
```
<!-- end generated -->

Combines the `metrics.json` files of single campaigns (see `measure --campaign`) into the one file that `compare` reads.
The inputs must agree on everything else `measure` records (tool version, label, matrix, samples hash, characters per
token), and no campaign may be in two of them. Otherwise nothing is written.

```sh
tinarrative benchmark metrics merge build/protectorate/metrics.json build/resist/metrics.json --out build/package-metrics/metrics.json
```

<!-- generated: options benchmark metrics merge -->
| Option | Meaning |
| --- | --- |
| `METRICS...` | A per-campaign metrics.json. |
| `--out PATH` | Write the merged metrics.json here. |
<!-- end generated -->

<!-- generated: exit-codes benchmark metrics merge -->
| Code | When |
| --- | --- |
| 0 | The merged metrics.json was written. |
| 2 | Usage error, metrics files that differ in their metadata, or a campaign in two of them. |
| 4 | A metrics file cannot be read or is not a metrics file. |
| 9 | The merged file cannot be written. |
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

## `benchmark runtime merge`

<!-- generated: synopsis benchmark runtime merge -->
```
tinarrative benchmark runtime merge --out FILE [--samples PATH] FILE [FILE ...]
```
<!-- end generated -->

Combines the runtime JSON files of single campaigns (see `measure --campaign`) into the one file that `report` reads.
The inputs must come from the same measurement setup, and no campaign may be in two of them.
Otherwise nothing is written. The merged file records the hash of the `samples.json` under `--samples`.

```sh
tinarrative benchmark runtime merge build/protectorate/runtime.json build/resist/runtime.json --out build/runtime.json
```

<!-- generated: options benchmark runtime merge -->
| Option | Meaning |
| --- | --- |
| `FILE...` | A per-campaign runtime JSON file. |
| `--out FILE` | The merged runtime JSON file to write. |
| `--samples PATH` | Benchmark samples directory (default benchmarks/samples). |
<!-- end generated -->

<!-- generated: exit-codes benchmark runtime merge -->
| Code | When |
| --- | --- |
| 0 | The merged runtime JSON was written. |
| 2 | Usage error, runtime files that differ in their metadata, or a campaign in two of them. |
| 4 | A runtime file cannot be read or is not a runtime file, or --samples has no samples.json. |
| 9 | The merged file cannot be written. |
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
tinarrative benchmark calibrate open [--samples PATH] [--out PATH] [--rebuild] [--jobs N]
                                     [--port PORT] [--no-open]
```
<!-- end generated -->

Serves the share calibration page on `127.0.0.1` and opens it: a page for choosing the rise shares of the starting
scalings against the sample campaigns. Slide a measure's rise share to see which events change significance level,
how the narrator package and the takeover waves change, and which events sit nearest each cut-off; open an event to
see why it has its level. Base levels, under Rise shares, switches an event type's base level, as `report --base`
does; the event inspector switches the type of the event it shows, and says when a context rule decided the event's
level, so the switch passes it by. The page's URL hash holds the explored state, which `report --state` reads. The
page slides only the rise share of each measure's starting scaling; drop shares and split-off or joined scalings
come from `report` flags or a hash, and the page keeps them.

The command replays the table in Python for every change on the page; the page only draws the answer
([ADR-0022](../adr/0022-the-calibration-table-is-replayed-once-in-python.md)). It keeps serving until it is
interrupted with Ctrl-C. A stale table is served while it is rebuilt, and the page offers to reload once the new one
is ready. The extraction's progress shows on stderr as for `report`, and on the page as a bar with the time left
and every campaign's step. A failed rebuild keeps the old table served and the command exits with 2 when interrupted; with no old
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
| `--jobs N` | Worker processes for a rebuild; 1 runs everything in one process; the table is the same (default: the CPUs, at most what memory holds). |
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

## `benchmark calibrate time`

<!-- generated: synopsis benchmark calibrate time -->
```
tinarrative benchmark calibrate time [--samples PATH] [--out PATH] [--rebuild] [--jobs N]
                                     [--repeats N] [--output PATH] [--base-python PYTHON]
                                     [--base-samples PATH] [--base-label LABEL] [--label LABEL]
                                     [--run-url URL] [--report PATH]
```
<!-- end generated -->

Measures how long the calibration page takes to get its answers, so you can see whether a change to the replay or to
the answers it sends made the page slower. It refreshes the cache the way [`calibrate report`](#benchmark-calibrate-report)
does, then prints (or writes) JSON with the median and 95th-percentile seconds and the size of the answers, for the
kinds of request the page makes. It measures the code in this checkout, unless `--base-python` names another
revision's interpreter: that interpreter extracts its own table from `--base-samples` (default `--samples`, so the same campaigns) and times the same requests through
its own server handler, and the JSON gains a `base` report beside the head's figures. A request type the other
revision cannot answer has `null` figures and shows as `n/a`. `--report` writes the base-versus-head Markdown table
that the `calibration-metrics` workflow posts ([benchmarks](../../benchmarks/README.md#on-demand-runs)).

```sh
# Time the server against the samples and print the JSON.
tinarrative benchmark calibrate time

# Ten answers per request, written to a file.
tinarrative benchmark calibrate time --repeats 10 --output timing.json

# Compare against another revision installed in its own environment.
tinarrative benchmark calibrate time --base-python ../main/.venv/bin/python --report calibration.md
```

<!-- generated: options benchmark calibrate time -->
| Option | Meaning |
| --- | --- |
| `--samples PATH` | Benchmark samples directory (default benchmarks/samples). |
| `--out PATH` | The calibration cache directory (default build/calibration). |
| `--rebuild` | Rebuild the cache even when it is fresh. |
| `--jobs N` | Worker processes for a rebuild; 1 runs everything in one process; the table is the same (default: the CPUs, at most what memory holds). |
| `--repeats N` | Times each request is sent (default 5). |
| `--output PATH` | Write the timing JSON here (default: stdout). |
| `--base-python PYTHON` | Another revision's interpreter: it extracts its own table (from --base-samples) and times the same requests through its own server handler; an answer it cannot give is n/a. The JSON gains a `base` report. |
| `--base-samples PATH` | The samples directory the base extracts from (default: --samples), so a changed sample shows its effect. |
| `--base-label LABEL` | The base revision's name in --report (default base). |
| `--label LABEL` | This revision's name in --report (default head). |
| `--run-url URL` | The workflow run the --report links to. |
| `--report PATH` | Write the base-versus-head Markdown table here (needs --base-python). |
<!-- end generated -->

<!-- generated: exit-codes benchmark calibrate time -->
| Code | When |
| --- | --- |
| 0 | The timing JSON was printed or written. |
| 2 | Usage error, a sample that does not match samples.json, a failed extraction (status.js says failed; the old table stays), or a table the server cannot answer from. |
| 4 | --samples is not a directory or its samples.json cannot be read. |
| 9 | --out or --output cannot be written. |
<!-- end generated -->

## `benchmark calibrate report`

<!-- generated: synopsis benchmark calibrate report -->
```
tinarrative benchmark calibrate report [--samples PATH] [--out PATH] [--rebuild] [--jobs N]
                                       [--rise SCALING=VALUE] [--drop SCALING=VALUE]
                                       [--scaling TYPE=SCALING] [--campaign NAME]
                                       [--type EVENT_TYPE] [--base TYPE=LEVEL] [--state HASH]
                                       [--format {text,json}]
```
<!-- end generated -->

Replays the share calibration table of the sample campaigns at other scalings and prints what would change: which
events move level, how the narrator package grows or shrinks, which takeover waves lose members, and the events
nearest each cut-off. It ends with the changed scalings written as scaling registry entries, ready to paste, followed
by one comment line for each event type moved to another scaling and each type whose base level was switched.

A scaling is a rise share, at which an event rises a level above the level it starts from, and an optional drop
share, at which it drops one ([ADR-0011](../adr/0011-significance-is-judged-once-and-scaled-by-share.md)).
`--rise` and `--drop` set a scaling's shares;
`--scaling TYPE=SCALING` moves an event type to another scaling on its measure, and `--scaling TYPE=TYPE` splits it
off into a scaling of its own, starting as a copy of its code scaling. The cut-offs are listed per scaling, one at
each level its events can reach.

The table is cached in `--out`, shared with the page, and rebuilt when the package or `samples.json` changed, or
with `--rebuild`. The campaigns are extracted one after another, each by as many worker processes as the CPUs and
memory allow; `--jobs` sets the number, and the table is the same for any. While it is extracted, stderr shows how
far it has come and the time left on one live line in a terminal, a line per finished campaign, and the time the
extraction took. A rebuild interrupted with Ctrl-C keeps the old table, and a page serving it says the rebuild
failed.

`--state` reads a state explored on the calibration page; the other flags override it.

`--base TYPE=LEVEL` shows what changing an event type's base level would do. Events whose level a context rule
decides keep it. `--base` applies even to types that `--type` leaves out of the count. The readout's state lists the switched
base levels against the code's.

The table also scores any [draft shares](#draft-shares) beside the real events, without changing their levels; the
state holds a base level for each draft, and its own section of the readout reports each one. A draft that cannot be
scored fails the rebuild.

```sh
# What would a lower power rise share do?
tinarrative benchmark calibrate report --rise power=0.05

# Two scalings, one campaign, as JSON.
tinarrative benchmark calibrate report --rise power=0.05,hab=0.4 --campaign resist --format json

# War arcs on a scaling of their own, ten times as narrow as the default.
tinarrative benchmark calibrate report --scaling war.arc=war.arc --rise war.arc=0.3 --drop war.arc=0.01

# What if nation changes were minor events?
tinarrative benchmark calibrate report --base region.nation_changed=minor

# A state copied from the calibration page.
tinarrative benchmark calibrate report --state 'rise=power:0.05'
```

<!-- generated: options benchmark calibrate report -->
| Option | Meaning |
| --- | --- |
| `--samples PATH` | Benchmark samples directory (default benchmarks/samples). |
| `--out PATH` | The calibration cache directory (default build/calibration). |
| `--rebuild` | Rebuild the cache even when it is fresh. |
| `--jobs N` | Worker processes for a rebuild; 1 runs everything in one process; the table is the same (default: the CPUs, at most what memory holds). |
| `--rise SCALING=VALUE` | A scaling's rise share; comma-separated, repeatable (default: the code's). |
| `--drop SCALING=VALUE` | A scaling's drop share, below its rise share; comma-separated, repeatable (default: the code's). |
| `--scaling TYPE=SCALING` | Move an event type to another scaling on its measure, or to its own name to split it off into a scaling of its own, starting as a copy; comma-separated, repeatable (default: the code's). |
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
| 2 | Usage error, a sample that does not match samples.json, an unknown scaling, campaign or type, a share that is not a positive number or a drop share at or above its rise share, a scaling on another measure than its type's, a base level that is not a level, an invalid --state (a link with ref= was made before scalings), a scaling or switched type given twice, a table at another schema version (run with --rebuild), or a failed extraction (status.js says failed; the old table stays). |
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
   A draft reads its measure's starting scaling unless it names one of its own in `scalings`: a `ScalingSpec` on a
   measure one of its readings reads, at most one per measure.
3. Run `tinarrative benchmark calibrate open`, which rebuilds the table, and calibrate the draft's rise share and base
   on the page, or its own scaling with `report --rise`/`--drop`.

#### Graduating a draft

One PR as well: add a `ShareOf` member, move the draft's share reading into `SHARE_IMPLEMENTATIONS`, set `share=`
(and `base=` if the calibrated base differs) on the kinds of the draft's types, set `scaling=` beside `share=`
(the measure's starting scaling, or a new `Scaling` member whose `SCALINGS` entry holds the calibrated rise and drop
shares and the game quantity that explains them), and delete the draft from `DRAFT_SHARES`.
