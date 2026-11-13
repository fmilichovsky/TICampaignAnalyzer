# `tinarrative save parse`

<!-- generated: synopsis save parse -->
```
tinarrative save parse [--record-unknowns] [--registry PATH] save
```
<!-- end generated -->

Checks that a save loads and prints a short summary: game version, date, player faction and how many nations,
councilors, fleets and other entities it holds. Use it when `events` or `narrate` rejects a save, or to count the
structures the parser does not describe yet ([`unknowns`](unknowns.md) lists them).

## Examples

```sh
# Does this save load?
tinarrative save parse Autosave.json

# Also record its unknown structures in the registry.
tinarrative save parse Autosave.json --record-unknowns --registry docs/game-data-notes/unknowns/registry.json
```

## Options

<!-- generated: options save parse -->
| Option | Meaning |
| --- | --- |
| `SAVE` | Path to a single save file. |
| `--record-unknowns` | Also fold the unknown structures in this save into the unknowns registry. |
| `--registry PATH` | Unknowns registry JSON file to update, created when missing (default: $TINARRATIVE_UNKNOWNS_REGISTRY). |
<!-- end generated -->

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
