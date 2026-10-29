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

## Observed campaign signals (2026-10-18)

The following was checked against eight private saves of two campaigns. One campaign has five saves
from 2045 to 2046 and the other has three saves from 2026. Both are on the same scenario.

- `TIGlobalValuesState.realWorldCampaignStart` is a componentized date with milliseconds. It was
  identical in every save of a campaign and different between the two campaigns. The
  two starts were nine months apart. Hypothesis: it is the real-world time the campaign was
  started.
- In each save, exactly one `TIPlayerState` entry was non-AI. Its faction resolved to a
  `TIFactionState` key, and the faction reference and `playerFactionName` were stable within each
  campaign.
- `TITimeState.masterMetaTemplateName` / `scenarioMetaTemplateName` were `FullScenario` /
  `2026Scenario` in all eight saves. The scenario confirms a campaign but does not separate these
  two.
- A start date derived from the game clock (`currentDateTime` minus `daysInCampaign`) is **not**
  usable. It gave the same day for both campaigns, and it was off by one day in one save.
- The nation and region map-key sets (295 and 363 keys) were identical within each campaign and
  different between the two. They are not used: the four signals below already separate the
  campaigns.
- File modification times did not follow game time. The latest game date of one campaign had the
  oldest file time of that campaign.

## Implemented grouping rule

`tinarrative` groups by identity. Two saves belong to the same campaign when all four signals are
equal:

```text
identity = (
  human_faction_ref:   the sole non-AI TIPlayerState.faction, resolved to a TIFactionState key,
  player_faction_name: TIMetadataState.playerFactionName,
  scenario:            TITimeState.masterMetaTemplateName + scenarioMetaTemplateName,
  started:             TIGlobalValuesState.realWorldCampaignStart,
)
```

A missing signal counts as its own value. A save without a real-world start is therefore never
merged with one that has a start. Within a group, increasing internal game time is the chronology.
Byte-identical saves are deduplicated first, as described in
[chronology and duplicate snapshots](chronology-and-deduplication.md).

| Result | Rule | Handling |
| --- | --- | --- |
| Exact duplicate | Same SHA-256 | One snapshot, retain all paths as provenance |
| Same campaign | All four signals equal | One group |
| Separate campaigns | Any signal differs | Separate groups; `events` requires a choice |
| Unclassified | No non-AI player, several, or an unresolvable faction | A group of its own; never merged |

The rule that requires all four signals to be equal is a project policy, not a game-format
invariant. It is a **hypothesis** that `realWorldCampaignStart` is unique per started campaign
beyond the two campaigns observed. Two campaigns started in the same second with the same faction
and scenario would be merged.

Never use filename order, save sequence number, filesystem timestamp, or `currentID.value` as a
campaign identity. Filename numbers were observed out of chronological order, and `currentID` has
no documented campaign semantics. The filesystem time is read only to resolve
`events --campaign latest`.

## Limits

- Numeric IDs may be allocated similarly in separately started campaigns;
  matching one ID alone is not sufficient evidence.
- A campaign reloaded from an earlier save and played differently keeps all four signals
  (observed 2026-10-29: `campaigns` put both attempts of one reload into one group). Its branches
  interleave by game time. Continuous capture makes this common, since it keeps the abandoned
  attempt's autosaves too. The architecture's lines
  ([Mode D](../architecture.md#lines-design)) split such a group with the
  [witness records](domain-field-map.md#witnesses-across-a-reload).
- Multiplayer, modded, migrated, or damaged saves may contain zero or more
  than one non-AI player. They intentionally fall into the unclassified path.
