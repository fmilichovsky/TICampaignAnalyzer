# `tinarrative unknowns`

```
tinarrative unknowns <path>... [--registry PATH] [--format text|json]
```

Scans saves for structures the parser does not describe (unknown state types, undocumented
fields, unexpected shapes) and, optionally, folds them into the unknowns registry
(`docs/game-data-notes/unknowns/registry.json`). It is a maintenance command: it writes nothing
unless a registry is named. The triage workflow and the registry format are in the
[unknowns registry README](../game-data-notes/unknowns/README.md).

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `PATH...` | required | Save files or directories. A directory is read one level deep; files in it that are not saves are listed as skipped. |
| `--registry PATH` | `$TINARRATIVE_UNKNOWNS_REGISTRY` | Registry JSON file to update; created when missing. Without a registry the command only prints the report. |
| `--format text\|json` | `text` | Human-readable report or the same report as JSON. |

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

| Code | Meaning | Output |
| --- | --- | --- |
| 0 | Every path given on the command line was scanned. Findings are not failures. | Full report on stdout. |
| 2 | Usage error. | argparse message on stderr. |
| 4 | A given path cannot be read, or a given directory holds no files. | Full report on stdout; the input is listed as skipped. |
| 5 | A given file was read but is not a supported save. | Full report on stdout; the input is listed as skipped. |
| 7 | The registry cannot be read, is not a valid registry document, or cannot be written. | Full report on stdout with `registry: not updated`; one line on stderr. |

Files inside a given directory that fail never change the exit code. 7 takes precedence over 4,
and 4 over 5.

## Examples

```sh
tinarrative unknowns Save.json
tinarrative unknowns ~/path/to/saves --registry docs/game-data-notes/unknowns/registry.json
TINARRATIVE_UNKNOWNS_REGISTRY=docs/game-data-notes/unknowns/registry.json tinarrative unknowns ~/path/to/saves
```
