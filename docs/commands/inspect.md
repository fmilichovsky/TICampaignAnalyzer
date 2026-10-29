# `tinarrative save inspect`

```
tinarrative save inspect <save> [-p|--path POINTER]... [--max-items N] [--max-string N] [--max-depth N] [--format text|json]
```

Reports the raw structure of one save file without interpreting it: file facts, the JSON root,
the top-level keys with their types and sizes, an ID census per entity type, and any parts of the
document you select by JSON pointer. Use it to check format observations in
[docs/game-data-notes](../game-data-notes/README.md) or to find out why a save does not load.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `save` | required | Path to a single save file. Only the file name appears in the report. |
| `-p`, `--path POINTER` | none | RFC 6901 JSON pointer to print. May be repeated. Dotted state-type names need no escaping; `~0` and `~1` escape `~` and `/`. |
| `--max-items N` | 10 | Maximum array items or object keys shown per container in a selected path. |
| `--max-string N` | 80 | Maximum characters shown per string in a selected path. |
| `--max-depth N` | 3 | Maximum nesting depth shown in a selected path. |
| `--format text\|json` | `text` | Human-readable report or the same report as JSON. |

All limits accept 0, which shows only the truncation marker. The global `--log-level debug`
option (before `save`) explains the decoding on stderr; see the [debugging guide](../debugging.md).

## Output

The report lists, in order: file facts (size, SHA-256, leading bytes, byte-order mark, line
endings), the decode result, the root type, the top-level keys and one further level, the
[entity-identity](../game-data-notes/entity-identity.md) census, the selected paths, and
diagnostics. Hidden content in a selected path is always marked, as in `"...(+21 keys)"` or
`"[...]"`. The report is the same on every run and holds no absolute paths.

```text
tinarrative save inspect report
file: representative_campaign.json
  size_bytes: 2366
  sha256: c01379f493338b6016b04432a805ad1fbeb43918dee6de7b6d208a0534590911
  leading_bytes: 7b 0a 20 20 22 63 75 72
  utf8_bom: no
  line_endings: lf
  decoded_chars: 2366
decode: ok (json)
root: object (2 keys)
top-level keys:
  currentID: object (1 key)
  gamestates: object (6 keys)
  ...
selected paths: none
diagnostics: none
```

Diagnostics are stable codes, such as `empty_file`, `gzip_magic`, `invalid_utf8`,
`json_decode_error`, `id_duplicate` or `pointer_not_found`, each with a message. Findings inside
valid JSON do not fail the command.

## Exit codes

| Code | Meaning | Output |
| --- | --- | --- |
| 0 | Report printed. | Full report on stdout. |
| 2 | Usage error, including a negative limit. | argparse message on stderr. |
| 4 | The save path is missing, unreadable, or a directory. | One line on stderr; nothing on stdout. |
| 5 | Bytes were read but are not decodable UTF-8 JSON. | File facts and diagnostics on stdout. |
| 6 | At least one `--path` did not resolve. | Full report on stdout. |

Code 5 takes precedence over 6.

## Examples

```sh
tinarrative save inspect Autosave.json
tinarrative save inspect Autosave.json --path /gamestates/PavonisInteractive.TerraInvicta.TIMetadataState/0/Value
tinarrative save inspect Autosave.json --path /currentID --max-items 5 --format json
```
