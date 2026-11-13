# `tinarrative save parse`

<!-- generated: synopsis save parse -->
```
tinarrative save parse [--record-unknowns] [--registry PATH] save
```
<!-- end generated -->

Reads one save, checks that it is a supported Terra Invicta save, and prints a short summary of
what it holds. Use it to check that a save loads before passing it to `events` or `narrate`, and
to count the structures the parser does not yet describe.

## Options

<!-- generated: options save parse -->
| Option | Meaning |
| --- | --- |
| `SAVE` | Path to a single save file. |
| `--record-unknowns` | Also fold the unknown structures in this save into the unknowns registry. |
| `--registry PATH` | Unknowns registry JSON file to update, created when missing (default: $TINARRATIVE_UNKNOWNS_REGISTRY). |
<!-- end generated -->

## Output

- the file: path, format, game version, size, top-level keys and number of state types;
- the snapshot: game `date`, `campaign day`, `player faction`, and how many factions, nations,
  regions, councilors, fleets, habs and other entities the save holds;
- `records`: how many save-carried logs and counters were read, and their entries;
- `unknown structures`: how many structures outside the parser's schema the save contains;
  [`unknowns`](unknowns.md) lists them.

A value the save does not establish prints as `unknown (<reason>)` and is never replaced by a
default. With `--record-unknowns`, a final `registry: <path>: N added, M updated, P pruned, T total`
line is printed (see the [unknowns registry](../game-data-notes/unknowns/README.md)).

Failures print one message to stderr. To see why, run with the global `--log-level debug` option
(before `save`); see the [debugging guide](../debugging.md).

## Exit codes

<!-- generated: exit-codes save parse -->
| Code | When |
| --- | --- |
| 0 | The save was loaded. |
| 2 | Usage error, including --record-unknowns without a registry. |
| 4 | The save cannot be read. |
| 5 | The file is not a supported save. |
| 7 | The registry cannot be read, is invalid or cannot be written; the summary is printed. |
<!-- end generated -->

## Examples

```sh
tinarrative save parse Autosave.json
tinarrative save parse Autosave.json --record-unknowns --registry docs/game-data-notes/unknowns/registry.json
```
