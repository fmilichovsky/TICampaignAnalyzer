# Campaign settings

What a `terra_invicta_json_v1` save records about the game settings its campaign was started with, as the benchmark
sample profile reads them. Observed on 2026-11-26 in every save of the committed sample campaigns: the Protectorate
campaign (34 saves, builds 1.0.53b to 1.0.65) and the Resist campaign (63 saves, builds RC13a to 1.0.32).

## Where each setting is

| Setting | Read from | Observed |
| --- | --- | --- |
| Player faction | the sole non-AI `TIPlayerState.faction`, resolved to a `TIFactionState` key, and that faction's `templateName` | `AppeaseCouncil` (Protectorate), `ResistCouncil` (Resist); `playerFactionName` holds the player's renamed display name, so the template name is read instead |
| Difficulty | `TIMetadataState.difficulty` | a preset name: `Normal` (Protectorate), `Veteran` (Resist). `TIGlobalValuesState.difficulty` and `startDifficulty` held a number (2 and 3) agreeing with it |
| Custom difficulty | `TIMetadataState.customDifficulty` | `false` in both; `TIGlobalValuesState.scenarioCustomizations.customDifficulty` agreed |
| Scenario | `TITimeState.masterMetaTemplateName` / `scenarioMetaTemplateName` | `FullScenario` / `2026Scenario` in both |
| Faction set | `TIMetadataState.selectedFactionsForScenario` | the same eight council template names in both, `AlienCouncil` included |
| Mods | `TIMetadataState.playedWithMods`, and `TIGlobalValuesState.moddingUsedAnytime` | `false` in both; `TIGlobalValuesState.moddingActive` was `false` too |
| Alien progression speed | `TIMetadataState.alienProgressionSpeed` | the string `100%` in both |
| Research speed | `TIMetadataState.researchSpeedMultiplier` | the string `100%` in both |

Every setting above was identical in all saves of a campaign; only `latestSaveVersion` changed, with the game build.

`TIMetadataState` holds the settings as display strings (`100%`, `125`). `TIGlobalValuesState.scenarioCustomizations`
holds the same settings as numbers (`alienProgressionSpeed: 1.0`), next to settings the metadata does not show
(mining, hab and ship construction rates per player kind, all 1.0 in both campaigns; `randomizeMap`, `false`, in
the Protectorate saves only).
The difficulty presets differ in more than their name: the Veteran campaign had
`missionControlBonusAI` `20` and `controlPointMaintenanceFreebieBonusAI` `50` where the Normal campaign had `0` and
`0`, with `customDifficulty` `false` in both. These values are therefore part of a preset, not a custom modifier,
and only `customDifficulty` marks custom modifiers. Hypothesis: `customDifficulty` turns `true` whenever a modifier
departs from its preset; no save with custom difficulty was available to check it.

## Absent fields

- `TIMetadataState.requiredDLC` was absent from every Resist save and an empty list in every Protectorate save.
- Every field in the table above was present in every save of both campaigns.
