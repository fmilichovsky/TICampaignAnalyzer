# `tinarrative inspect <save>`

Report the raw structure of one save file without normalizing it. The report
describes what is literally serialized; the only game-specific knowledge it
applies is the documented envelope keys and the entity-identity table, whose
census counts serialized IDs without comparing saves. The command is a
static-analysis aid: it lets format observations in
[docs/game-data-notes](../game-data-notes/README.md) be checked and unsupported
saves be diagnosed. It never imports from `tinarrative.parsing`.

## Usage

```sh
tinarrative inspect Autosave.json
tinarrative inspect Autosave.json --path /gamestates/PavonisInteractive.TerraInvicta.TIMetadataState/0/Value
tinarrative inspect Autosave.json --path /currentID --max-items 5 --max-string 40
tinarrative inspect Autosave.json --format json
```

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `save` | required | Path to a single save file. Only the file name appears in the report. |
| `-p`, `--path POINTER` | none | RFC 6901 JSON pointer to render. May be repeated; each is reported in the given order. Dotted state-type names need no escaping; `~0` and `~1` escape `~` and `/`. |
| `--max-items N` | 10 | Maximum array items or object keys shown per container in a selected path. |
| `--max-string N` | 80 | Maximum characters shown per string in a selected path. |
| `--max-depth N` | 3 | Maximum nesting depth rendered in a selected path. |
| `--format text\|json` | `text` | Human-readable report or the same report as JSON. |

All limits accept 0, which shows only the truncation marker.

The global `--log-level debug` option (before `inspect`) explains the decode steps,
the ID census totals, and each pointer resolution on stderr; see the
[debugging guide](../debugging.md). The report on stdout is unaffected.

## Report contents

The report is produced in this order and is byte-identical across runs for the
same input and options. It contains no timestamps and no absolute paths.

1. **File facts**: size in bytes, SHA-256, first eight bytes as hex, whether a
   UTF-8 byte-order mark is present, line-ending style (`lf`, `crlf`, `mixed`,
   `none`), and decoded character count.
2. **Decode result**: `ok (json)` or `failed`.
3. **Root**: the JSON root type and, for an object, its key count.
4. **Top-level keys**: every root key with its type and length, in serialized
   order. For each root key whose value is an object, one further section lists
   that object's keys the same way. On a documented save this shows every
   `gamestates` container with its item count, including empty ones as
   `object (0 keys)`.
5. **Identity**: for every entity domain in the
   [entity-identity strategy](../game-data-notes/entity-identity.md), the ID
   source, confidence (`in-save-id` or `name-key`), secondary key, and a census
   of each state type (entries, ID range, `Key.value == Value.ID.value` matches,
   mismatches, missing and duplicate IDs). Global lines give the distinct ID
   count, IDs shared across state types, the largest observed ID, and
   `currentID`.
   Omitted when the root or `gamestates` is not an object. In `--format json`
   this is the `identity` field.
6. **Selected paths**: for each `--path`, the target's type and length followed
   by a bounded JSON rendering. Hidden content is always marked:
   `"...(+21 keys)"`, `"...(+3 items)"`, `"...(+92 chars)"`, and `"{...}"` or
   `"[...]"` beyond `--max-depth`. Empty containers are shown as `{}` or `[]`.
7. **Diagnostics**: stable codes with a message, or `none`.

Types use JSON vocabulary: `object`, `array`, `string`, `number`, `boolean`,
`null`. Non-ASCII characters are escaped in both formats so output is stable on
any console.

### Example

```text
tinarrative inspect report
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
currentID keys:
  value: number
gamestates keys:
  PavonisInteractive.TerraInvicta.TIMetadataState: array (1 item)
  ...
selected paths: none
diagnostics: none
```

## Diagnostics

| Code | When | Effect |
| --- | --- | --- |
| `empty_file` | The file has no bytes. | Decode fails. |
| `gzip_magic`, `zip_magic` | Leading bytes indicate a compressed container. | Decode fails; compressed saves are not a documented format. |
| `utf16_bom` | A UTF-16 byte-order mark is present. | Decode fails; only UTF-8 is documented. |
| `utf8_bom` | A UTF-8 byte-order mark precedes the JSON. | Skipped and reported; decoding continues. |
| `invalid_utf8` | Bytes are not valid UTF-8. | Decode fails; the byte offset is reported. |
| `json_decode_error` | The text is not valid JSON. | Decode fails; line, column, character offset, and surrounding context are reported. |
| `root_not_object` | Valid JSON whose root is not an object. | Reported; the root type is still shown and paths still resolve. |
| `missing_key` | A key documented in the envelope (`currentID`, `gamestates`) is absent. | Reported as a finding only. |
| `id_key_mismatch`, `id_missing`, `id_duplicate` | A state type has entries whose `Key.value` differs from `Value.ID.value`, lacks an integer ID, or repeats a key. | Reported as a finding only. |
| `id_shared_across_types` | An ID occurs in more than one state type. | Reported as a finding only. |
| `current_id_behind` | `currentID` is below the largest observed ID. | Reported as a finding only. |
| `pointer_syntax` | A `--path` is neither empty nor starts with `/`. | Reported; exit code 6. |
| `pointer_not_found` | A `--path` step is a missing key, an out-of-range or non-decimal index, or descends into a scalar. | Reported with the deepest resolved prefix; exit code 6. |

## Exit codes

| Code | Meaning | Output |
| --- | --- | --- |
| 0 | Report printed. Findings inside valid JSON are diagnostics, not failures. | Full report on stdout. |
| 2 | Usage error, including a negative limit. | argparse message on stderr. |
| 4 | The save path is missing, unreadable, or a directory. | One line on stderr; nothing on stdout. |
| 5 | Bytes were read but are not decodable UTF-8 JSON. | File facts and diagnostics on stdout; selected paths are listed as `not evaluated`. |
| 6 | At least one `--path` did not resolve. | Full report on stdout. |

Code 5 takes precedence over 6.

## Performance

The whole document is decoded with the standard library. An ~84 MB save is
inspected in well under a second and needs roughly 300 MB of memory.

## Testing

Golden reports for every checked-in fixture live under
`tests/fixtures/inspection/`; see [the testing guide](../testing.md) for how to
regenerate them. An opt-in `real_save` test reads a private save from the
`TINARRATIVE_REAL_SAVE` environment variable.
