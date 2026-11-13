# `tinarrative save diff`

<!-- generated: synopsis save diff -->
```
tinarrative save diff [--format {text,json}] before after
```
<!-- end generated -->

Reads two saves and lists every literal difference between them: which value of which entity
changed, from what to what, and where in each save it came from. It infers nothing about causes;
an entity missing from one save is reported as absent from it, never as destroyed or created. For
the analyzed view of the same saves (events, significance, inferences), use [`events`](events.md).

## Options

<!-- generated: options save diff -->
| Option | Meaning |
| --- | --- |
| `BEFORE` | The earlier save file. |
| `AFTER` | The later save file; the saves are compared in argument order. |
| `--format text\|json` | Report format (default text). |
<!-- end generated -->

The saves are compared in argument order, whatever their game dates, so swapping them reverses
the report.

## Output

The text report prints the two saves with their game dates and versions, a count of changes per
domain, then one line per change:

```
nation:20 GDP: 1000.0 -> 1200.0
nation:20 allies: +nation:22 -nation:21
councilor:100 location: region:40 -> unknown (unresolved_reference, raw={...})
fleet:121: present only in the after snapshot
faction:15 Transactions: +240 entries
```

Entities are printed by ID only; `events` names them. A save-carried log (see the
[save-carried records](../game-data-notes/domain-field-map.md#save-carried-records) table) shows
entry counts only, because its entries carry campaign content.

`--format json` prints `before`, `after`, `before_date`, `after_date` and `changes`, each change
with its values, detail and source location in both saves. The change types are in
[`model/changes.py`](../../src/tinarrative/model/changes.py). The output is deterministic: the
same two saves always give the same report.

Failures print one message to stderr naming the save that failed. The global `--log-level debug`
option (before `save`) explains more; see the [debugging guide](../debugging.md).

## Exit codes

<!-- generated: exit-codes save diff -->
| Code | When |
| --- | --- |
| 0 | Both saves were compared. |
| 2 | Usage error. |
| 4 | A save cannot be read. |
| 5 | A save is not a supported save. |
<!-- end generated -->

## Examples

```sh
tinarrative save diff Save_2032-01.json Save_2032-04.json
tinarrative save diff Save_2032-01.json Save_2032-04.json --format json > diff.json
```
