# Commands

One page per implemented `tinarrative` subcommand. Each page covers purpose,
options, output, and exit codes. Run `tinarrative COMMAND --help` for the authoritative
option list of the installed version.

| Command | Status | Page |
| --- | --- | --- |
| `inspect <save>` | Implemented | [inspect.md](inspect.md) |
| `parse <save>` | Implemented | [parse.md](parse.md) |
| `unknowns <path>...` | Implemented | [unknowns.md](unknowns.md) |
| `diff <before> <after>` | Stub | Reports literal state changes between two snapshots. |

## Global options

Global options precede the command name.

| Option | Default | Meaning |
| --- | --- | --- |
| `--version` | | Print the package version and exit. |
| `--log-level LEVEL` | `warning` | Diagnostic log level on stderr: `debug`, `info`, `warning`, or `error`. Overrides the `TINARRATIVE_LOG_LEVEL` environment variable. See the [debugging guide](../debugging.md). |

`parse` and `unknowns` share a per-command `--registry PATH` option whose default is the
`TINARRATIVE_UNKNOWNS_REGISTRY` environment variable; see the
[unknowns registry](../game-data-notes/unknowns/README.md).

Stubs (currently `diff`) are registered so their exit code is stable. They accept
no arguments: running one prints `tinarrative <command> is not implemented yet.`
to stderr and exits with code 3. A command gets its own page when it is implemented.

## Shared exit codes

Exit codes are stable and defined at the top of `src/tinarrative/cli.py`.

| Code | Meaning |
| --- | --- |
| 0 | Success. |
| 2 | Usage error (argparse). |
| 3 | The command is registered but not implemented yet. |
| 4 | An input path could not be read. |
| 5 | Input bytes were read but are not in a decodable, documented format (`parse`: malformed data or unsupported shape, format, or game version). |
| 6 | A user-selected path did not resolve. |
| 7 | The unknowns registry could not be read, is not a valid registry document, or could not be written; the report or summary is still printed. |

Command pages state which of these codes they use and what is printed in each
case.
