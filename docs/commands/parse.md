# `tinarrative parse`

```
tinarrative parse <save> [--record-unknowns] [--registry PATH]
```

Reads one save, validates it as a `terra_invicta_json_v1` raw save (see the
[format note](../game-data-notes/terra_invicta_json_v1.md#loader-validation)), normalizes it
into a `SaveSnapshot`, and prints a short summary:

- envelope: source path, format identifier, game version (or `not serialized`), size in
  bytes, top-level keys, and the number of state types;
- snapshot: the game `date` (ISO-8601 from `TITimeState.currentDateTime`, no timezone),
  `campaign day`, `player faction`, and the number of normalized `factions`, `nations`,
  `regions`, `control points`, `councilors`, `armies` (regular and megafauna), `fleets`,
  `ships`, `habs`, `technologies` (name-keyed, derived from the research singleton),
  `wars`, `federations`, and `region alien states` (the five per-region alien sub-state types together);
- `records`: how many save-carried record fields were decoded with a known value across all
  entities and how many entries they hold in total (see the
  [save-carried records](../game-data-notes/domain-field-map.md#save-carried-records) table;
  a field an entity does not carry is unknown and not counted);
- `unknown structures`: how many structures outside the parser's schema the save contains
  (undocumented fields, unknown state types, unexpected shapes or reference targets). They
  never change the snapshot; `tinarrative unknowns` lists them.

A value the save does not establish prints as `unknown (<reason>)`, where the reason is
`missing`, `unparseable`, or `unresolved_reference`; it is never replaced by a default.
The normalizer copies only the fields listed in the
[domain field map](../game-data-notes/domain-field-map.md), resolves references only to
entities present in the same save, and infers nothing about causes.

With `--record-unknowns`, those findings are also folded into the unknowns registry named by
`--registry PATH` or the `TINARRATIVE_UNKNOWNS_REGISTRY` environment variable (see the
[unknowns registry](../game-data-notes/unknowns/README.md)), and a final
`registry: <path>: N added, M updated, P pruned, T total` line is printed. `--registry`
without `--record-unknowns` writes nothing.

Failures print one message to stderr and no traceback. To see which parser decisions
led there, run with the global `--log-level debug` option (before `parse`); see the
[debugging guide](../debugging.md). The summary on stdout is unaffected.

## Exit codes

| Code | When |
| --- | --- |
| 0 | The save was loaded, validated, and normalized. |
| 2 | Usage error, including `--record-unknowns` without `--registry` or the environment variable (the summary is still printed). |
| 4 | The path cannot be read (missing, unreadable, or a directory). |
| 5 | The bytes are empty, compressed, not UTF-8 JSON, lack the documented envelope, carry an unsupported format or game version, or a normalized state collection does not follow the documented pair-map shape. |
| 7 | `--record-unknowns` was given but the registry cannot be read, is invalid, or cannot be written; the summary is still printed. |
