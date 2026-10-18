# Commands

One page per implemented `tinarrative` subcommand. Each page covers purpose,
options, output, and exit codes. Run `tinarrative COMMAND --help` (or
`tinarrative save COMMAND --help`) for the authoritative option list of the installed version.

The top level holds the campaign commands and the maintenance command:

| Command | Status | Page |
| --- | --- | --- |
| `campaigns <path>...` | Implemented | [campaigns.md](campaigns.md) |
| `events <path> <path>...` | Implemented | [events.md](events.md) |
| `unknowns <path>...` | Implemented | [unknowns.md](unknowns.md) |

The `save` group holds the per-save evidence and debugging commands. `tinarrative save`
without a command is a usage error (exit 2).

| Command | Status | Page |
| --- | --- | --- |
| `save inspect <save>` | Implemented | [inspect.md](inspect.md) |
| `save parse <save>` | Implemented | [parse.md](parse.md) |
| `save diff <before> <after>` | Implemented | [diff.md](diff.md) |

## Global options

Global options precede the command name.

| Option | Default | Meaning |
| --- | --- | --- |
| `--version` | | Print the package version and exit. |
| `--log-level LEVEL` | `warning` | Diagnostic log level on stderr: `debug`, `info`, `warning`, or `error`. Overrides the `TINARRATIVE_LOG_LEVEL` environment variable. See the [debugging guide](../debugging.md). |

`save parse` and `unknowns` share a per-command `--registry PATH` option whose default is the
`TINARRATIVE_UNKNOWNS_REGISTRY` environment variable; see the
[unknowns registry](../game-data-notes/unknowns/README.md).

## Shared exit codes

Exit codes are stable and defined at the top of `src/tinarrative/cli.py`.

| Code | Meaning |
| --- | --- |
| 0 | Success. |
| 2 | Usage error (argparse). |
| 3 | Reserved for a command registered before it is implemented; no command uses it at present. |
| 4 | An input path could not be read. |
| 5 | Input bytes were read but are not in a decodable, documented format (`save parse`: malformed data or unsupported shape or format). |
| 6 | A user-selected path did not resolve. |
| 7 | The unknowns registry could not be read, is not a valid registry document, or could not be written; the report or summary is still printed. |

Command pages state which of these codes they use and what is printed in each
case.
