# `tinarrative save inspect`

<!-- generated: synopsis save inspect -->
```
tinarrative save inspect [-p POINTER] [--max-items N] [--max-string N] [--max-depth N]
                         [--format {text,json}]
                         save
```
<!-- end generated -->

Reports the raw structure of one save without interpreting it: file facts, top-level keys with their types and sizes,
an ID count per entity type, and any part of the document you select by JSON pointer. Use it to find out why a save
does not load, or to check a format note in [game-data notes](../game-data-notes/README.md). The report holds no
absolute paths and is the same on every run, so it can be shared.

## Examples

```sh
# Why does this save not load?
tinarrative save inspect Autosave.json

# Show one part of the document.
tinarrative save inspect Autosave.json --path /gamestates/PavonisInteractive.TerraInvicta.TIMetadataState/0/Value

# A smaller excerpt, as JSON.
tinarrative save inspect Autosave.json --path /currentID --max-items 5 --format json
```

Dotted state-type names in a pointer need no escaping; `~0` and `~1` escape `~` and `/`. Hidden content in a selected
path is marked, as in `"...(+21 keys)"`.

## Options

<!-- generated: options save inspect -->
| Option | Meaning |
| --- | --- |
| `SAVE` | Path to a single save file. |
| `-p, --path POINTER` | RFC 6901 JSON pointer to print, such as /gamestates/Some.State/0/Value; may be repeated. |
| `--max-items N` | Maximum array items or object keys shown per container in a selected path (default 10). |
| `--max-string N` | Maximum characters shown per string in a selected path (default 80). |
| `--max-depth N` | Maximum nesting depth shown in a selected path (default 3). |
| `--format text\|json` | Report format (default text). |
<!-- end generated -->

## Exit codes

<!-- generated: exit-codes save inspect -->
| Code | When |
| --- | --- |
| 0 | The report was printed. |
| 2 | Usage error, including a negative limit. |
| 4 | The save cannot be read. |
| 5 | The bytes are not decodable JSON; file facts and diagnostics are still printed. |
| 6 | A --path did not resolve; the report is still printed. 5 wins over 6. |
<!-- end generated -->
