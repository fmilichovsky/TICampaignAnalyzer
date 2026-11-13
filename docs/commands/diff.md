# `tinarrative save diff`

<!-- generated: synopsis save diff -->
```
tinarrative save diff [--format {text,json}] before after
```
<!-- end generated -->

Lists every literal difference between two saves: which value of which entity changed, from what to what. Use it to
check what the game actually changed between two saves, before trusting an event that [`events`](events.md) reports.
It infers nothing: an entity missing from one save is reported as absent from it, never as destroyed or created.

## Examples

```sh
# What changed between these two saves?
tinarrative save diff Save_2032-01.json Save_2032-04.json

# The same, with each change's location in both saves.
tinarrative save diff Save_2032-01.json Save_2032-04.json --format json > diff.json
```

## Options

<!-- generated: options save diff -->
| Option | Meaning |
| --- | --- |
| `BEFORE` | The earlier save file. |
| `AFTER` | The later save file; the saves are compared in argument order. |
| `--format text\|json` | Report format (default text). |
<!-- end generated -->

## Output

```
nation:20 GDP: 1000.0 -> 1200.0
nation:20 allies: +nation:22 -nation:21
fleet:121: present only in the after snapshot
faction:15 Transactions: +240 entries
```

Entities are printed by ID only; `events` names them. Swapping the saves reverses the report.

## Exit codes

<!-- generated: exit-codes save diff -->
| Code | When |
| --- | --- |
| 0 | Both saves were compared. |
| 2 | Usage error. |
| 4 | A save cannot be read. |
| 5 | A save is not a supported save. |
<!-- end generated -->
