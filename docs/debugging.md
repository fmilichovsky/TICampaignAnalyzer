# Debugging

`tinarrative` can explain what the parser decided and why a save was rejected. The
diagnostic log is off by default, goes to stderr only, and is written so it can be pasted
into an issue without leaking campaign or machine details.

## Turning it on

```sh
# Everything the pipeline decided, to a file; the report stays on stdout.
tinarrative --log-level debug save parse Save.json 2> parse-debug.log

# The same through the environment, here with pointer resolution included.
TINARRATIVE_LOG_LEVEL=debug tinarrative save inspect Save.json \
  --path /gamestates/PavonisInteractive.TerraInvicta.TITimeState/0/Value

# One line per stage only.
tinarrative --log-level info save parse Save.json
```

`--log-level` is a global option and must precede the subcommand. It accepts `debug`,
`info`, `warning` (the default), and `error`, overrides `TINARRATIVE_LOG_LEVEL`, and an
unrecognized value in either place is a usage error (exit code 2).

## What a line looks like

```text
INFO tinarrative.cli: save parse start save=Save.json
DEBUG tinarrative.parsing.raw_save: format accepted format=terra_invicta_json_v1 bytes=84312715
DEBUG tinarrative.parsing.raw_save: utf-8 decoded bytes=84312715 chars=84312715
DEBUG tinarrative.parsing.raw_save: json decoded root=dict
DEBUG tinarrative.parsing.raw_save: envelope ok top_level_keys=2 state_types=61
DEBUG tinarrative.parsing.game_version: game_version detected source=global_values
DEBUG tinarrative.parsing.references: reference index built ids=12345 skipped_types=0
DEBUG tinarrative.parsing.normalization: date parsed date=2046-10-08T00:00:00
DEBUG tinarrative.parsing.normalization: domain normalized state_type=TIFactionState domain=faction entities=8 missing_fields=0 unresolved_references=2 unparseable=0 unknown_fields=124
DEBUG tinarrative.parsing.records: records normalized state_type=TIFactionState fields=17 entities=8 sets=136 known_sets=136 missing=0 entries=6146 unparseable_dates=0 unresolved_references=7 shape_findings=0
DEBUG tinarrative.parsing.unknowns: unknown fields state_type=TIFactionState fields=124 entities=8
INFO tinarrative.parsing.unknowns: unknown structures total=388 state_types=0 fields=386 envelope_keys=0 field_shapes=0 reference_domains=2 singletons=0 containers=0
INFO tinarrative.parsing.normalization: normalized state_types=61 entities=3210 technologies=240 record_sets=726 record_entries=7326
INFO tinarrative.cli: save parse done save=Save.json state_types=61 game_version=0.4.99 unknowns=388 exit=0
```

Every line is `LEVEL logger: message key=value ...`. There are no timestamps, so two runs
on the same save produce the same log. The logger name says which module made the
decision.

Levels:

| Level | Carries |
| --- | --- |
| `info` | One line per command stage: start, unknown-structure counts per kind, normalized, done; `unknowns` adds one line per scanned or skipped save; `save diff` reports the total change count on its done line. |
| `debug` | Parser decisions and per-state-type aggregates: decode rejections with their byte offset or line/column, envelope checks, the game-version decision, containers the reference index skipped and why, singleton entries, date parsing, per-domain entity and unknown-field counts, per-type record-set counts (sets, entries, unparseable dates, unresolved references; never a label or value), research counts, root shape, ID census totals, each `--path` resolution, registry load/update counts, and for `save diff` one line per compared collection, one for the record sets and one for the singletons, with counts on each side and the number of changes per kind (never the entities or values themselves). |
| `warning`, `error` | Nothing on the success path. The CLI promises an empty stderr there, so a warning in normal operation is a bug. |

Stage durations stay out of these levels, so the log is the same on every run. `TINARRATIVE_TIMING=1` adds
`INFO tinarrative.timing:` lines at any level, each with its seconds: one per surveyed, normalized and loaded save,
one per interval and per narrative rule, and one for the aggregation. `tinarrative benchmark runtime` reads them
([benchmarks](../benchmarks/README.md#runtime)).

When `save parse` rejects a save, the one-line stderr message is unchanged; at `debug` it is
preceded by a `parse failed save=... error=<ErrorClass>` line and the traceback. `save diff`
normalizes both saves with the same lines, then adds its own aggregates:

```text
INFO tinarrative.cli: save diff start before=Earlier.json after=Later.json
DEBUG tinarrative.diff.state_diff: collection compared collection=nations before=295 after=295 matched=295 appeared=0 disappeared=0 value=502 membership=42 map=0 unknown=0 records=0
DEBUG tinarrative.diff.state_diff: records compared before=726 after=726 matched=726 appeared=0 disappeared=0 value=1 membership=0 map=0 unknown=0 records=36
DEBUG tinarrative.diff.state_diff: singletons compared appeared=0 disappeared=0 value=4 membership=1 map=0 unknown=0 records=0
INFO tinarrative.cli: save diff done before=Earlier.json after=Later.json changes=1180 exit=0
```

## What is never logged

Debug logs are meant to be shared, so they follow the rules in `src/tinarrative/log.py`:

- **Paths**: only the file name (`save=Save.json`), never the directory. The regular
  `save parse` summary on stdout still prints the path you passed.
- **Save content**: no string value read from a save, so no faction, player, councilor,
  or campaign names. Where a value matters, the log gives its JSON shape
  (`value=object{7}`, `value=string[12]`) through `tinarrative.log.shape`, or a bounded
  excerpt through `tinarrative.log.excerpt`.
- **Volume**: no per-entity lines. An ~80 MB save produces a few dozen lines.

Safe to log verbatim: counts, byte offsets, JSON pointers, state-type and field names,
finding kinds, map IDs, the format identifier, the `game_version` string, exception class
names, and this package's own error messages (they name types, keys, and IDs only). The
unknowns registry follows the same rules and additionally keeps only identifier-like nested
member names; see [its README](game-data-notes/unknowns/README.md).

## Adding a log point

```python
from ..log import fields, get_logger, shape

logger = get_logger(__name__)

logger.debug("date unparseable %s", fields(state_type="TITimeState", value=shape(raw)))
```

- Use `%s` with `fields(...)` so the message is only built when the level is enabled;
  guard expensive aggregates with `logger.isEnabledFor(logging.DEBUG)`.
- Log the decision, not the data: a fixed phrase plus structured `key=value` context in
  call order. Aggregate across loops instead of logging inside them.
- A new `warning` on a success path needs a CLI test for its stderr.
- `tinarrative.log` imports only the standard library, so both `inspection` and
  `parsing` may use it; the rule that `inspection` never imports `parsing` is unchanged.
