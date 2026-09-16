# `tinarrative parse <save>`

**Status: not implemented.** The command is registered so its exit code is
stable. It currently accepts no arguments: `tinarrative parse` prints
`tinarrative parse is not implemented yet.` to stderr and exits with code 3,
and passing a save path is a usage error until the command is implemented.

## Intended behavior

Decode one save through the version-specific `parsing` stage and produce a
normalized campaign snapshot (`SaveSnapshot`) that downstream stages can diff
and analyze. Unsupported format identifiers and explicit, undocumented game
versions must be rejected clearly rather than guessed; see
[the format notes](../game-data-notes/terra_invicta_json_v1.md).

To look at a save before this command exists, use
[`tinarrative inspect`](inspect.md).

## Exit codes

| Code | Meaning |
| --- | --- |
| 2 | Usage error. |
| 3 | Not implemented. |
