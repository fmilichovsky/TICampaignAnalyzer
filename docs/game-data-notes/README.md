# Terra Invicta game-data notes

This is an evidence log for the save formats handled by `tinarrative`. It is deliberately not a general specification of Terra Invicta saves. A claim is an **observed fact** only when it was checked against the private source saves on the stated capture date. A rule or vocabulary taken from the game's own documentation (the in-game texts or the Terra Invicta wiki) that no save carries, so that it cannot be checked against one, is labelled **published**, with its source and transcription date. Everything else is labelled a **hypothesis**.

## Supported format identifiers

| Identifier | Status | Notes |
| --- | --- | --- |
| `terra_invicta_json_v1` | Supported envelope | [Observed format and limits](terra_invicta_json_v1.md) |

Parsing is not gated on a Terra Invicta *game build*. The saves have no top-level `game_version` field. The build string lives inside the `TIGlobalValuesState` singleton: `latestSaveVersion` (observed in eight of eight private saves of two campaigns, 2026-10-16; it changed once within the older campaign) next to `campaignStartVersion` (which differed from it in the older campaign). `detect_game_version` reports `latestSaveVersion` as the snapshot's `game_version`; it is informational only and never used to accept or reject a save, because format changes between builds have been additive. New or changed structures surface through the [unknowns registry](unknowns/README.md) instead.

`require_supported_format` raises `UnsupportedSaveFormatError` for an unknown format identifier. These errors include the unsupported identifier and list the known identifiers, rather than silently selecting a parser.

## Checked-in fixture mapping

All fixtures in `tests/fixtures/io/terra_invicta_json_v1/` declare `format_assumption: "terra_invicta_json_v1"` and `format_documentation: "docs/game-data-notes/terra_invicta_json_v1.md"` in their manifest. That identifier points to [the v1 observations](terra_invicta_json_v1.md). `version_assumption` records whether the fixture exercises the envelope or a synthetic detector edge case; it is not a claim about a real game build.

Original saves remain private and are never copied into this repository. The fixture manifest is the authoritative, reviewable connection between a synthetic fixture and a format assumption.

For implementation-facing findings, start with [containers and references](containers-and-references.md), then use the [domain field map](domain-field-map.md) to choose the normalizer and diff work for a particular architectural domain.

[Snapshot-diff observations](diff-observations.md) records which ID-keyed maps and fields changed across one real interval, without preserving any campaign values.

The [state-type inventory](state-type-inventory.md) is the complete observed envelope key set and should be used for parser routing—not as a rejection list for additional future state types.

[Unknown save structures](unknowns/README.md) is the triage backlog: `unknowns/registry.json` is written by `tinarrative unknowns` and records every field, state type, shape or reference target the parser met and does not describe (names, shapes, counts and dates only). It is the only machine-written file in this directory; its README explains how an entry becomes a normalized or acknowledged field.

[Chronology and duplicate snapshots](chronology-and-deduplication.md) defines the observed ordering and byte-level deduplication behavior needed before producing a campaign sequence.

[Campaign grouping](campaign-grouping.md) records the observed campaign signals
and the identity rule that partitions a mixed directory into campaigns when no
explicit campaign identifier is serialized.

[Sources for higher-level events](higher-level-event-sources.md) records the
observed shape and lifecycle of the structures that carry wars, federations,
alien activity on Earth, the game's own notification log, combat logs and the
other evidence the reconstruction and narrative stages need but the normalizer
does not read yet.

[Nation statistics](nation-metrics.md) records what the save carries about a
nation's statistics beyond their current values (the quarterly per-capita GDP
series, the cumulative cause trackers), how the statistics move between saves
(population, GDP, value-band crossings and what explains them), and the
nuclear, space-support and military assets a nation holds.

[Space assets](space-assets.md) records how habs and ships divide between the
alien faction and the human factions from the start of a campaign to its late
game: the evidence behind the space stakes of the entity-scaled significance
score ([architecture 12](../architecture.md#12-significance)).

[Factions](factions/) holds the game's own descriptions of the seven human
factions (ideology, goal, relations). They are game text, not save
observations; the [narrator prompt](../narrator.md) condenses them into its
faction briefs.
