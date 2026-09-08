# Campaign grouping without a campaign ID

The observed `terra_invicta_json_v1` envelope has no dedicated campaign-ID
field in its top-level object or `TIMetadataState` field set. A campaign must
therefore be identified by continuity evidence, not by a single asserted ID.

## Observed player identity signals

In each of five inspected saves (manual, auto, and exit saves spanning the
sampled campaign):

- `TIPlayerState` contained eight entries.
- Exactly one entry had `Value.isAI == false`.
- That entry's `Value.faction.value` resolved to exactly one
  `TIFactionState` map key.
- The resolved human-faction reference was stable across all five saves.
- `TIMetadataState.Value.playerFactionName` was also stable across all five
  saves.

The `TIPlayerState.isAI == false` faction reference is the primary player
identity signal. The metadata faction name is a human-readable corroborating
signal, not a unique identity: separate campaigns can use the same faction.

## Recommended grouping algorithm

First deduplicate byte-identical files and extract the game timestamp as
documented in [chronology and duplicate snapshots](chronology-and-deduplication.md).
For every remaining save, construct a **campaign-continuity profile**:

```text
profile = {
  game_timestamp: TITimeState.currentDateTime,
  human_faction_ref: the sole non-AI TIPlayerState.faction reference,
  player_faction_name: TIMetadataState.playerFactionName,
  scenario: TITimeState.masterMetaTemplateName + scenarioMetaTemplateName,
  world_anchors: IDs from TIFactionState, TINationState, TIRegionState,
  source_hash: SHA-256(raw bytes),
}
```

Build directed candidate links only from an earlier timestamp to a later one.
For saves in the same user-supplied directory, automatically group an ordered
run when all of the following hold:

1. exactly one non-AI player and a resolvable faction reference exist in both
   saves;
2. human-faction references match;
3. player-faction names match when both are present;
4. scenario metadata matches when both are present; and
5. the nation and region anchor-ID sets have very high overlap (use exact
   equality when available; otherwise retain the measured overlap and flag the
   link for review).

Within such a run, increasing internal game time is the chronology. This
implements the practical assumption that a save directory normally contains
continued play for the same chosen faction, while still making an independent
campaign with the same faction visibly uncertain rather than silently merging
it.

## Confidence and boundary rules

| Result | Rule | Handling |
| --- | --- | --- |
| Exact duplicate | Same SHA-256 | One snapshot, retain all paths as provenance |
| High-confidence continuation | All five grouping signals match and time increases | Same campaign chain |
| Plausible continuation | Player faction/name and time match, but an anchor is absent or changed | Same provisional chain; surface a warning |
| Campaign boundary / incompatible | Player faction, scenario, or stable world anchors conflict | Separate chains |
| Unclassified | Missing/malformed player or time state, or multiple human players | Do not auto-merge; require a caller choice |

Never use filename order, save sequence number, filesystem timestamp, or
`currentID.value` as a campaign identity. Filename numbers were observed out
of chronological order, and `currentID` has no documented campaign semantics.

## Limits

- Numeric IDs may be allocated similarly in separately started campaigns;
  matching one ID alone is not sufficient evidence.
- The anchor-overlap threshold is a project policy to be calibrated with
  additional campaign directories. It is not a game-format invariant.
- Multiplayer, modded, migrated, or damaged saves may contain zero or more
  than one non-AI player. They intentionally fall into the unclassified path.
