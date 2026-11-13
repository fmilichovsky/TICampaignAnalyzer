# `tinarrative unknowns`

<!-- generated: synopsis unknowns -->
```
tinarrative unknowns [--registry PATH] [--format {text,json}] PATH [PATH ...]
```
<!-- end generated -->

Scans saves for structures the parser does not describe yet (unknown state types, undocumented fields, unexpected
shapes) and, with a registry, records them for triage. Run it on new saves after a game update. The report and the
registry hold only type labels and member names, never a value, ID, name or path from a save, so both can be shared.
The triage workflow is in the [unknowns registry README](../game-data-notes/unknowns/README.md).

## Examples

```sh
# What does this save hold that the parser does not know?
tinarrative unknowns Save.json

# Record the findings of a whole directory.
tinarrative unknowns ~/saves --registry docs/game-data-notes/unknowns/registry.json
```

`TINARRATIVE_UNKNOWNS_REGISTRY` can name the registry instead of `--registry`. Registry entries the parser now
describes are pruned.

## Options

<!-- generated: options unknowns -->
| Option | Meaning |
| --- | --- |
| `PATH...` | Save files or directories, in any order; a directory is read one level deep. |
| `--registry PATH` | Unknowns registry JSON file to update, created when missing (default: $TINARRATIVE_UNKNOWNS_REGISTRY). |
| `--format text\|json` | Report format (default text). |
<!-- end generated -->

## Exit codes

<!-- generated: exit-codes unknowns -->
| Code | When |
| --- | --- |
| 0 | Every named path was scanned; findings are not failures. |
| 2 | Usage error. |
| 4 | A named path cannot be read, or a named directory holds no files. |
| 5 | A named file is not a supported save. |
| 7 | The registry cannot be read, is invalid or cannot be written; the report is printed. 7 wins over 4 and 5. |
<!-- end generated -->
