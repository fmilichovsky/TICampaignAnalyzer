# Debugging

`tinarrative` can explain what the parser decided and why a save was rejected. The
diagnostic log is off by default, goes to stderr only, and is written so it can be pasted
into an issue without leaking campaign or machine details.

## Turning it on

```sh
# Everything the pipeline decided, to a file; the report stays on stdout.
tinarrative --log-level debug parse Save.json 2> parse-debug.log

# The same through the environment, here with pointer resolution included.
TINARRATIVE_LOG_LEVEL=debug tinarrative inspect Save.json \
  --path /gamestates/PavonisInteractive.TerraInvicta.TITimeState/0/Value

# One line per stage only.
tinarrative --log-level info parse Save.json
```

`--log-level` is a global option and must precede the subcommand. It accepts `debug`,
`info`, `warning` (the default), and `error`, overrides `TINARRATIVE_LOG_LEVEL`, and an
unrecognized value in either place is a usage error (exit code 2).

## What a line looks like

```text
INFO tinarrative.cli: parse start save=Save.json
DEBUG tinarrative.parsing.raw_save: format accepted format=terra_invicta_json_v1 bytes=84312715
DEBUG tinarrative.parsing.raw_save: utf-8 decoded bytes=84312715 chars=84312715
DEBUG tinarrative.parsing.raw_save: json decoded root=dict
DEBUG tinarrative.parsing.raw_save: envelope ok top_level_keys=2 state_types=61
DEBUG tinarrative.parsing.game_version: game_version absent, accepted
DEBUG tinarrative.parsing.references: reference index built ids=12345 skipped_types=0
DEBUG tinarrative.parsing.normalization: date parsed date=2046-10-08T00:00:00
DEBUG tinarrative.parsing.normalization: domain normalized state_type=TIFactionState domain=faction entities=8 missing_fields=0 unresolved_references=2 unparseable=0 unknown_fields=124
DEBUG tinarrative.parsing.unknowns: unknown fields state_type=TIFactionState fields=124 entities=8
INFO tinarrative.parsing.unknowns: unknown structures total=388 state_types=0 fields=386 envelope_keys=0 field_shapes=0 reference_domains=2 singletons=0 containers=0
INFO tinarrative.parsing.normalization: normalized state_types=61 entities=3210 technologies=240
INFO tinarrative.cli: parse done save=Save.json state_types=61 game_version=none unknowns=388 exit=0
```

Every line is `LEVEL logger: message key=value ...`. There are no timestamps, so two runs
on the same save produce the same log. The logger name says which module made the
decision.

Levels:

| Level | Carries |
| --- | --- |
| `info` | One line per command stage: start, unknown-structure counts per kind, normalized, done; `unknowns` adds one line per scanned or skipped save. |
| `debug` | Parser decisions and per-state-type aggregates: decode rejections with their byte offset or line/column, envelope checks, the game-version decision, containers the reference index skipped and why, singleton entries, date parsing, per-domain entity and unknown-field counts, research counts, root shape, ID census totals, each `--path` resolution, and registry load/update counts. |
| `warning`, `error` | Nothing on the success path. The CLI promises an empty stderr there, so a warning in normal operation is a bug. |

When `parse` rejects a save, the one-line stderr message is unchanged; at `debug` it is
preceded by a `parse failed save=... error=<ErrorClass>` line and the traceback.

## What is never logged

Debug logs are meant to be shared, so they follow the rules in `src/tinarrative/log.py`:

- **Paths**: only the file name (`save=Save.json`), never the directory. The regular
  `parse` summary on stdout still prints the path you passed.
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
