# `tinarrative save diff`

```
tinarrative save diff <before> <after> [--format text|json]
```

Reads two saves, normalizes each exactly as [`save parse`](parse.md) does, and prints every
literal difference between the two `SaveSnapshot`s. The report is objective: it says what
differs and where each value came from, and infers nothing about causes. An entity that is
missing from one save is described as absent from that snapshot, never as destroyed, created,
purged or annexed; see the
[snapshot-diff observations](../game-data-notes/diff-observations.md) for the project rules
behind that wording.

`save diff` is the evidence layer only: it runs no analyzers, assigns no significance and
reconstructs nothing. The analyzed view of the same two saves (analyzer results, significance,
inferred events and, with `--changes`, these same literal changes) is
[`events`](events.md) given both saves.

The text report prints:

- `before` and `after`: the paths as given, each with the snapshot's game `date` and
  `game_version` (or `not serialized`);
- `changes: N` followed by one count per domain;
- `changes:` with one line per change, sorted by domain, then entity in natural ID order
  (`nation:9` before `nation:10`, name-keyed technologies after numeric IDs), then field.

Entities are matched across the two saves by their domain-qualified ID (numeric map ID, or
template name for technologies). For a matched entity every field present on either side is
compared; the two campaign singletons are compared as well, under the pseudo-domains
`campaign` (date, campaign day and quarter, player faction name, difficulty, mods, scenario,
scenario faction list) and `research` (the `TIGlobalResearchState` fields). The `TIGlobalValuesState`
singleton is an ordinary entity of the `global values` domain, matched by its map ID, so its
fields and records are compared like any other entity's. `game_version`, the
raw envelope metadata and the derived `timestamp` are not compared.

## Change kinds

| Kind | Meaning | Text form |
| --- | --- | --- |
| `value` | Both sides are known and compared as one value: scalar, `null`, resolved reference, or any structure not covered below. Equality is strict (`1` and `1.0`, or `true` and `1`, differ). | `nation:20 GDP: 1000.0 -> 1200.0` |
| `membership` | Both sides are lists of references or lists of names. They are compared as multisets: the same members in another order is not a change; duplicates count. | `nation:20 allies: +nation:22 -nation:21` |
| `map` | Both sides are objects. The detail names the keys added, removed and changed; the whole objects stay in the evidence. A componentized date is one map, so a timer change reads `changed month`. Faction `shipDesigns` is normalized to an object keyed by design `dataName`, so a design reads as an added, removed or changed key. | `ship:130 armor: changed Nose` |
| `unknown` | At least one side is `unknown`: the field is absent in that save, unparseable, or a reference whose ID does not exist there. Nothing is inferred from the known side. | `councilor:100 location: region:40 -> unknown (unresolved_reference, raw={...})` |
| `appeared` | The entity is present only in the later save. No per-field changes are reported for it. | `fleet:121: present only in the after snapshot` |
| `disappeared` | The entity is present only in the earlier save. | `control point:12: absent from the after snapshot` |
| `records` | Both sides are known save-carried record sets of one entity and field (see below). `before` and `after` are the entry counts; the detail lists the entries added, removed and, for keyed records, changed. The text form shows counts only, because record entries carry campaign content (ledger labels, destroyed-asset names). | `faction:15 Transactions: +240 entries`, `faction:15 factionHate: ~1 entries` |

Lists that are not reference or name lists (numeric lists such as `researchWeights`, lists
of objects such as `techProgress`) are one `value`; a reorder of such a list is a change.
A reference list with one stale ID is `unknown (unresolved_reference)` as a whole, because the
normalizer could not resolve it; its raw IDs stay visible. Values and references print as
`domain:key`, `unknown (<reason>)`, or compact JSON. The text report never prints display names;
`tinarrative events` names entities as `Name (domain:key)`.

### Save-carried records

The dated logs and cumulative counters listed in the field map's
[save-carried records](../game-data-notes/domain-field-map.md#save-carried-records) table
(`Transactions`, `HabDestructionLog`, `CombatLogs`, `lostControlPoints`, `lastExecutiveChange`, ...) are
compared per owning entity and field, under the owner's domain. A log (ledger, destruction log,
combat log, milestones) is compared as a multiset of entries, index aside: entries only in the later save are
`added`; entries only in the earlier save are `removed` and reported literally (observed for some
`Transactions` labels, which the game prunes per label; entries are never rewritten). The notification log
(`notificationSummaryQueue`) is a multiset too, but an entry is identified by template, date and summary:
an entry whose subject, outcome or faction lists differ is `changed` (`~`), because the game was observed to
rewrite the subject of kept entries. A keyed record (pair maps and label maps) is compared by key, so a changed
value is reported against its key (`~`). A single-value record is compared like an ordinary
field: a counter is a `value` change (`faction:15 abductions: 0 -> 1`), `intelSharingFactions`
a `membership` change, `dateOfNewGovernment` a `value` change. A record set that is `unknown`
on one side (the field is absent or has an undocumented shape in that save) is an `unknown`
change whose known side is the entry count. An entity present on one side only reports no record
changes, like its fields.

## Evidence

Every change carries the before and after value and a location on each side: the save path,
the short state type, the map ID and the RFC 6901 path of the entity's serialized `Value`
object. For an appeared or disappeared entity the absent side has only the save path. The
campaign singletons have no recorded location yet, so their changes carry the save path only;
the research fields carry the `TIGlobalResearchState` location. A `records` change carries the
record set's location, whose path ends in `/Value/<field>`; each entry in the detail keeps its
`index` (and a ledger entry its `label`), which addresses it inside that field.

With `--format json` the report is the serialized `StateDiff`: `before`, `after`,
`before_date`, `after_date`, and `changes`, each with `domain`, `entity_id`, `field` (`null`
for appeared/disappeared), `kind`, `before`, `after`, `detail` (`added`/`removed` members,
`added`/`removed`/`changed` keys, or for `records` the `added`/`removed` entries and
`changed` `{before, after}` entry pairs), `description`, `before_location` and
`after_location`.
A reference serializes as `{"ref": "domain:key", "state_type": ..., "confidence": ...}` plus
`"name"` when the save gives the entity a display name.
Unknown values serialize as `{"unknown": "<reason>"}` with the raw value when there is one.

The output is deterministic: the same two saves always give byte-identical reports. The
chronological order of the two saves is not checked; the report always describes the
transition from the first argument to the second, so a diff can run backwards in game time
(`events`, by contrast, always orders saves by game time).

Failures print one message to stderr naming the save that failed and no traceback. To see
how the two saves were normalized and the per-collection and record change counts, run with the global
`--log-level debug` option (before `save`); see the [debugging guide](../debugging.md).

## Exit codes

| Code | When |
| --- | --- |
| 0 | Both saves were loaded, normalized and compared. |
| 2 | Usage error (a save path missing, an unknown `--format`, or an unknown option such as `--min-significance` or `--inferred`). |
| 4 | A save path cannot be read (missing, unreadable, or a directory). |
| 5 | A save is empty, not UTF-8 JSON, lacks the documented envelope, carries an unsupported format, or a state collection does not follow the documented pair-map shape. |
