# Commands

One page per `tinarrative` subcommand. Each page covers purpose, options,
output, and exit codes. Run `tinarrative COMMAND --help` for the authoritative
option list of the installed version.

| Command | Status | Page |
| --- | --- | --- |
| `inspect <save>` | Implemented | [inspect.md](inspect.md) |
| `parse <save>` | Stub | [parse.md](parse.md) |
| `diff <before> <after>` | Stub | [diff.md](diff.md) |

## Shared exit codes

Exit codes are stable and defined at the top of `src/tinarrative/cli.py`.

| Code | Meaning |
| --- | --- |
| 0 | Success. |
| 2 | Usage error (argparse). |
| 3 | The command is registered but not implemented yet. |
| 4 | An input path could not be read. |
| 5 | Input bytes were read but are not in a decodable, documented format. |
| 6 | A user-selected path did not resolve. |

Command pages state which of these codes they use and what is printed in each
case.
