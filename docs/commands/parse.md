# `tinarrative save parse`

```
tinarrative save parse <save> [--record-unknowns] [--registry PATH]
```

Reads one save, checks that it is a supported Terra Invicta save, and prints a short summary of
what it holds. Use it to check that a save loads before passing it to `events` or `narrate`, and
to count the structures the parser does not yet describe.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `save` | required | Path to a single save file. |
| `--record-unknowns` | off | Also fold the unknown structures found in this save into the unknowns registry. |
| `--registry PATH` | `$TINARRATIVE_UNKNOWNS_REGISTRY` | The registry file to update; created when missing. Without `--record-unknowns` nothing is written. |

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

| Code | When |
| --- | --- |
| 0 | The save was loaded and read. |
| 2 | Usage error, including `--record-unknowns` without `--registry` or the environment variable (the summary is still printed). |
| 4 | The path cannot be read (missing, unreadable, or a directory). |
| 5 | The file is not a supported save: empty, compressed, not UTF-8 JSON, an unsupported format, or an unexpected shape. |
| 7 | `--record-unknowns` was given but the registry cannot be read, is invalid, or cannot be written; the summary is still printed. |

## Examples

```sh
tinarrative save parse Autosave.json
tinarrative save parse Autosave.json --record-unknowns --registry docs/game-data-notes/unknowns/registry.json
```
