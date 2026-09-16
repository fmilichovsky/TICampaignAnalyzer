# `tinarrative diff <before> <after>`

**Status: not implemented.** The command is registered so its exit code is
stable. It currently accepts no arguments: `tinarrative diff` prints
`tinarrative diff is not implemented yet.` to stderr and exits with code 3,
and passing snapshot paths is a usage error until the command is implemented.

## Intended behavior

Compare two normalized campaign snapshots and report literal state changes,
keeping objective changes separate from any inferred events. See
[the architecture](../architecture.md) for the pipeline stages this command
will span.

## Exit codes

| Code | Meaning |
| --- | --- |
| 2 | Usage error. |
| 3 | Not implemented. |
