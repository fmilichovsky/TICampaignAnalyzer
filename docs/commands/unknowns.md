# `tinarrative unknowns <path>...`

Scan one or more saves for structures the parser does not describe and, optionally, fold
them into the unknowns registry (`docs/game-data-notes/unknowns/registry.json`). This is a
maintenance command: it normalizes each save exactly as `parse` does, has no effect on the
snapshot, and writes nothing unless `--registry` or the environment names a registry. The
triage workflow and the registry format are in
[docs/game-data-notes/unknowns/README.md](../game-data-notes/unknowns/README.md).

## Usage

```sh
tinarrative unknowns Save.json
tinarrative unknowns ~/path/to/saves --registry docs/game-data-notes/unknowns/registry.json
TINARRATIVE_UNKNOWNS_REGISTRY=docs/game-data-notes/unknowns/registry.json tinarrative unknowns ~/path/to/saves
tinarrative unknowns Save.json --format json
```

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `PATH...` | required | Save files or directories. A directory contributes its files one level deep, in sorted order; files inside it that are not saves are listed as skipped. |
| `--registry PATH` | `$TINARRATIVE_UNKNOWNS_REGISTRY` | Registry JSON file to update; created when missing. Without a registry the command only prints the report. |
| `--format text\|json` | `text` | Human-readable report or the same report as JSON. |

The global `--log-level info` option (before `unknowns`) adds one line per scanned or skipped
save plus the per-save `unknown structures total=...` aggregate; see the
[debugging guide](../debugging.md).

## What is reported

Every finding has a kind, a state type, usually a field, an optional detail, and a per-save
occurrence count. Findings carry a **content-free shape**: JSON type labels, identifier-like
member names one level deep (at most 32), and element types of arrays (first 64 elements).
No string value, number, map ID, name or path from a save is ever recorded, so the report and
the registry can be shared. Detection is driven by the code-form schema in
`src/tinarrative/parsing/fields.py` (`ENTITY_FIELDS`, `RECORD_FIELDS`, the singleton tables,
`SERIALIZATION_FIELDS`, `ACKNOWLEDGED_FIELDS`) and `src/tinarrative/parsing/inventory.py`
(`KNOWN_STATE_TYPES`).

| Kind | When | `occurrences` |
| --- | --- | --- |
| `unknown_state_type` | A `gamestates` key outside the observed inventory. The shape lists the member names of its entries; `detail` is `pair_map_violation` when the container is not the documented pair map. | Entries in the container. |
| `unknown_field` | A `Value` member of a normalized state type or singleton that is neither copied, a serializer member, nor acknowledged. | Entities carrying the member. |
| `unknown_envelope_key` | A root member other than `currentID` and `gamestates`. `state_type` is empty. | 1 |
| `unexpected_field_shape` | A known field whose value is not the documented shape; `detail` names the expected shape (`array_of_references`, `reference_object`, `componentized_date`, `array`, `object`, `array_of_objects`, `pair_map`, `array_of_keyed_objects`). For a record field, `field` may also name a member inside an entry (`HabDestructionLog.Destroyer`). | Values with that shape. |
| `unexpected_reference_domain` | A reference whose ID exists in the save, but under a state type outside the field's documented domains; `detail` is that state type. The field (or record entry member) still resolves to `unknown (unresolved_reference)`. | References. |
| `unexpected_singleton_count` | `TITimeState`, `TIMetadataState` or `TIGlobalResearchState` with more than one entry. | Entries. |
| `unexpected_container_shape` | A pair-map violation in an entity-domain container that is not normalized (the reference index skips it); `detail` is `pair_map_violation`. | 1 |

The same detection runs inside `parse`, whose summary ends with `unknown structures: N`.

### Text report

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

Paths are printed as given, like the `source:` line of `parse`; they never enter the log or the
registry. Findings are merged across the scanned saves (occurrences summed, shapes unioned,
saves counted) and sorted by kind, state type, field and detail, so the report is
byte-identical across runs. Non-ASCII characters are escaped.

With a registry, the last line becomes `registry: <path>: N added, M updated, P pruned, T
total`: entries created by this scan, entries seen again, entries removed because the schema
now covers them, and the registry size.

### JSON report

`{"saves": [...], "findings": [...], "registry": {...} | null}`. Each save has `path`,
`status` (`scanned` or `skipped`), `findings`, `game_version`, `error` and `error_class`; each
finding is the text report's finding with its `shape` object and a `saves` count; `registry`
carries the same numbers as the text line.

## Exit codes

| Code | Meaning | Output |
| --- | --- | --- |
| 0 | Every path given on the command line was scanned. Findings are not failures. | Full report on stdout. |
| 2 | Usage error. | argparse message on stderr. |
| 4 | A given path cannot be read, or a given directory holds no files. | Full report on stdout; the input is listed as skipped. |
| 5 | A given file was read but is not a supported save. | Full report on stdout; the input is listed as skipped. |
| 7 | The registry cannot be read, is not a valid registry document, belongs to another format, or cannot be written. | Full report on stdout with `registry: not updated`; one line on stderr. |

Files found inside a given directory that fail never change the exit code; directories hold
manifests, sidecars and other non-saves. 7 takes precedence over 4, and 4 over 5.

## Testing

`tests/cli/test_unknowns_cli.py` and `tests/maintenance/` cover the command, the scan and the
registry on checked-in fixtures; `tests/maintenance/test_committed_registry.py` validates the
committed registry on every run. An opt-in `real_save` test checks that a private save produces
field-level findings only and that no value leaks into the report.
