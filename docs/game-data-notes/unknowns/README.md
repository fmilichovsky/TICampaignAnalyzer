# Unknown save structures

`registry.json` beside this file is the triage backlog for everything the parser meets in a
save and does not describe: fields on normalized state types that are neither copied nor
acknowledged, `gamestates` keys outside the observed inventory, root members outside the
envelope, known fields with an unexpected shape, references whose target exists under an
unexpected state type, singletons with several entries, and containers that break the
pair-map shape. It is the only machine-written file in `docs/game-data-notes/`.

Every entry is an **observed fact** in the sense of the [notes README](../README.md): the scan
records what was literally serialized, dated by scan day. The only hypothesis-level text is the
optional hand-written `triage.notes`.

## Privacy rule

The registry is committed, so it holds schema-level facts only: state-type names, field
names, identifier-like member names one level deep, JSON type labels, counts and dates. It
never holds string values, numbers, map IDs, player or faction names, file names, paths or
hashes. The scanner enforces this by construction (`tinarrative.parsing.unknowns`): a member
name is kept only when it looks like an identifier, at most 32 per shape, and the registry
validator rejects any string outside `[A-Za-z0-9_$.:=-]`. A shape that still looks like it
leaked a value is a bug in the summarizer: fix the summarizer and regenerate the file, never
hand-edit the entry. Review the registry diff before committing it.

## Running a scan

```sh
# Scan a private save directory and update the committed registry.
tinarrative unknowns ~/path/to/saves --registry docs/game-data-notes/unknowns/registry.json

# The same destination through the environment.
export TINARRATIVE_UNKNOWNS_REGISTRY=docs/game-data-notes/unknowns/registry.json
tinarrative unknowns ~/path/to/saves

# Record while doing ordinary work.
tinarrative parse Save.json --record-unknowns

# Report only, no file touched.
tinarrative unknowns Save.json
```

The command page is [docs/commands/unknowns.md](../../commands/unknowns.md). Saves are private
and never committed; scanning them is opt-in, like `real_save` tests.

## Reading an entry

```json
{
  "kind": "unexpected_reference_domain",
  "state_type": "TICouncilorState",
  "field": "location",
  "detail": "TISpaceShipState",
  "shape": null,
  "max_occurrences": 1,
  "saves_seen": 6,
  "first_seen": "2026-10-13",
  "last_seen": "2026-10-13",
  "game_versions": ["not-serialized"]
}
```

| Member | Meaning |
| --- | --- |
| `kind` | One of the seven finding kinds listed in the command page. |
| `state_type` | Short state type (`PavonisInteractive.TerraInvicta.` stripped); the full key when it has no prefix; empty for an envelope key. |
| `field` | Field name, or `null` for type-, singleton- and container-level findings. |
| `detail` | Short qualifier: the expected shape, the owning state type of an unexpected reference target, or `pair_map_violation`. |
| `shape` | Union of every value seen: `types` (JSON type labels), `object_keys` and `array_item_keys` (identifier-like member names, capped), `object_keys_omitted` (a name failed the identifier test or the cap was hit), `array_item_types`. `null` where no value is involved. |
| `max_occurrences` | The largest per-save count (entities carrying the field, entries, references); re-scanning a save never inflates it. |
| `saves_seen` | Save files in which the finding appeared, summed over scans. Not deduplicated, by design: no save hashes are stored. |
| `first_seen`, `last_seen` | Scan dates. |
| `game_versions` | Serialized `game_version` values seen, or `not-serialized`. |
| `triage` | Optional, hand-written: `status` (`open`, `investigating`, `needs_evidence`), `notes`, optional `ref`. Preserved verbatim by every scan. |

Entries are sorted by `kind`, `state_type`, `field`, `detail`, so one state type's fields form
one block.

## Triage outcomes

An entry leaves the registry only when the code tables learn the structure and a scan is
re-run. Never delete entries by hand.

1. **Normalize it.** Add the field to `ENTITY_FIELDS` (and `REFERENCE_FIELDS` when it is a
   reference) or to the singleton tables in `src/tinarrative/parsing/fields.py`, add it to the
   observed table in [the domain field map](../domain-field-map.md), extend the normalizer or
   tests as needed, re-run the scan: the entry is pruned.
2. **Record it.** The field is a dated, append-only log or a cumulative counter that the
   snapshot cannot re-derive (architecture section 4.3). Add it to `RECORD_FIELDS` with a
   `RecordKind` (and a decoder in `src/tinarrative/parsing/records.py` if the kind is new), add
   the row to the field map's "Save-carried records" table, re-run the scan: the entry is pruned.
3. **Acknowledge it.** The field is understood and deliberately not normalized (a UI cache, an
   AI scratch value, a derived history, a `$id`/`$ref` graph, a vector). Add it to
   `ACKNOWLEDGED_FIELDS` with an `UnsupportedReason`, add the row to the field map's
   "deliberately not copied" table, re-run the scan: the entry is pruned.
4. **Keep it open.** Add a `triage` block with what is known and what evidence would settle it.
   The next scan keeps the block and refreshes the counts.

For an `unknown_state_type`, the equivalent of acknowledging is adding the key to the
[state-type inventory](../state-type-inventory.md) and to `KNOWN_STATE_TYPES` in
`src/tinarrative/parsing/inventory.py`, after checking its structure against real data. A
pruned entry is reported by the scan as `pruned`; git history is the record of what became
known.

## Hygiene

`tests/maintenance/test_committed_registry.py` runs in the default suite and fails when the
committed file is not canonical, when it contains an unsafe string, or when the schema now
covers an entry that is still listed, which means someone extended the tables without
re-running the scan. A new game build's additional state types appear here as
`unknown_state_type` findings rather than rejections, consistent with the inventory being an
observation and not an allowlist.
