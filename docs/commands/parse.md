# `tinarrative parse`

```
tinarrative parse <save>
```

Reads one save, validates it as a `terra_invicta_json_v1` raw save (see the
[format note](../game-data-notes/terra_invicta_json_v1.md#loader-validation)), and prints a
short envelope summary: source path, format identifier, game version (or
`not serialized`), size in bytes, top-level keys, and the number of state types.
Normalized snapshot output is not implemented yet.

Failures print one message to stderr and no traceback.

## Exit codes

| Code | When |
| --- | --- |
| 0 | The save was loaded and validated. |
| 2 | Usage error. |
| 4 | The path cannot be read (missing, unreadable, or a directory). |
| 5 | The bytes are empty, compressed, not UTF-8 JSON, lack the documented envelope, or carry an unsupported format or game version. |
