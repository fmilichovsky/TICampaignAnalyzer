# `tinarrative parse`

```
tinarrative parse <save>
```

Reads one save, validates it as a `terra_invicta_json_v1` raw save (see the
[format note](../game-data-notes/terra_invicta_json_v1.md#loader-validation)), normalizes it
into a `SaveSnapshot`, and prints a short summary:

- envelope: source path, format identifier, game version (or `not serialized`), size in
  bytes, top-level keys, and the number of state types;
- snapshot: the game `date` (ISO-8601 from `TITimeState.currentDateTime`, no timezone),
  `campaign day`, `player faction`, and the number of normalized `factions`, `nations`,
  `regions`, and `control points`.

A value the save does not establish prints as `unknown (<reason>)`, where the reason is
`missing`, `unparseable`, or `unresolved_reference`; it is never replaced by a default.
The normalizer copies only the fields listed in the
[domain field map](../game-data-notes/domain-field-map.md), resolves references only to
entities present in the same save, and infers nothing about causes.

Failures print one message to stderr and no traceback.

## Exit codes

| Code | When |
| --- | --- |
| 0 | The save was loaded, validated, and normalized. |
| 2 | Usage error. |
| 4 | The path cannot be read (missing, unreadable, or a directory). |
| 5 | The bytes are empty, compressed, not UTF-8 JSON, lack the documented envelope, carry an unsupported format or game version, or a normalized state collection does not follow the documented pair-map shape. |
