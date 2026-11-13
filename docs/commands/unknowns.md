# `tinarrative unknowns`

<!-- generated: synopsis unknowns -->
```
tinarrative unknowns [--registry PATH] [--format {text,json}] PATH [PATH ...]
```
<!-- end generated -->

Scans saves for structures the parser does not describe (unknown state types, undocumented
fields, unexpected shapes) and, optionally, folds them into the unknowns registry
(`docs/game-data-notes/unknowns/registry.json`). It is a maintenance command: it writes nothing
unless a registry is named. The triage workflow and the registry format are in the
[unknowns registry README](../game-data-notes/unknowns/README.md).

## Options

<!-- generated: options unknowns -->
| Option | Meaning |
| --- | --- |
| `PATH...` | Save files or directories, in any order; a directory is read one level deep. |
| `--registry PATH` | Unknowns registry JSON file to update, created when missing (default: $TINARRATIVE_UNKNOWNS_REGISTRY). |
| `--format text\|json` | Report format (default text). |
<!-- end generated -->

## Output

Every finding has a kind, a state type, usually a field, and a content-free shape: JSON type
labels and member names only. No value, ID, name or path from a save is recorded, so the report
and the registry can be shared.

```text
tinarrative unknowns report
saves:
  saves/campaign_assets.json: 0 unknown structures
  saves/malformed_truncated.json: skipped (MalformedSaveError: The save is not valid JSON: ...)
  saves/political_control.json: 2 unknown structures
findings: 2 across 2 saves
  unknown_field TINationState.fixtureOnlyUndocumentedField: 1 occurrence, 1 save
    shape: number
  unknown_state_type TIFixtureUnknownState: 1 entry, 1 save
    shape: object; keys $type, ID, archived, displayName, exists, templateName
registry: not updated
```

With a registry, the last line becomes `registry: <path>: N added, M updated, P pruned, T total`;
pruned entries are those the parser now describes. `--format json` prints
`{"saves": [...], "findings": [...], "registry": {...} | null}` with the same content.

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

Files inside a given directory that fail never change the exit code. 7 takes precedence over 4,
and 4 over 5.

## Examples

```sh
tinarrative unknowns Save.json
tinarrative unknowns ~/path/to/saves --registry docs/game-data-notes/unknowns/registry.json
TINARRATIVE_UNKNOWNS_REGISTRY=docs/game-data-notes/unknowns/registry.json tinarrative unknowns ~/path/to/saves
```
