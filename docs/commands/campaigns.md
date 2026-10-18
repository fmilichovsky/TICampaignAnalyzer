# `tinarrative campaigns`

```
tinarrative campaigns <path>... [--format text|json]
```

Lists the campaigns that the given saves belong to, with the selector that
[`events --campaign`](events.md#campaigns) accepts. Paths are files, directories or both, and
directories are expanded exactly as `events` does. Each save is read only for its hash, game time
and campaign identity. Nothing is normalized or analyzed, so the listing is fast even for a full
save directory. A single save is enough.

## Grouping

The save format has no campaign ID ([campaign grouping](../game-data-notes/campaign-grouping.md)).
Two saves belong to the same campaign when all of these signals match:

- the faction of the only human player (`TIPlayerState` with `isAI == false`);
- the player faction name (`TIMetadataState.playerFactionName`);
- the scenario (`TITimeState.masterMetaTemplateName` and `scenarioMetaTemplateName`);
- the real-world time the campaign was started (`TIGlobalValuesState.realWorldCampaignStart`).

No other signal is compared. File names, file times and `currentID` are never used for grouping.
A missing name, scenario part or start counts as its own value, so a save without a real-world
start is never merged with one that has a start.

A save with no human player, with several, or whose human player's faction does not resolve is
**unclassified**. It forms a group of its own and is never merged into a campaign. Byte-identical
copies of such a save stay together.

Grouping is inference. Every group reports the signals it was formed on.

## Selector keys

Each group has a key built from the slug of the faction name and, when it is known, the real-world
start: `resistance-20260104-113751`. The slug is the name in lower case, without a leading "the",
with every run of other characters turned into `-`. A group without a faction name uses `unknown`.
When two groups would get the same key, the later one gets `#2`, the next `#3`, and so on.

Groups are numbered from 1. Classified campaigns come first, ordered by real-world start (unknown
last), then by their first game time, then by path. Unclassified saves follow in the same order.

`events --campaign` accepts:

- a key, or any prefix of a key that matches only one group (`protectorate`);
- the group's number in this listing (`2`);
- `latest`: the group holding the save file with the newest modification time, which is usually
  the campaign being played. This is the only place where file times are used. They do not follow
  game time and never order or group saves.

## Text output

```
2 campaigns:

1. resistance-20260104-113751
   The Resistance, scenario FullScenario/2026Scenario, started 2026-01-04 11:37:51
   5 saves, 2045-08-01T00:00:00 to 2046-10-08T00:00:00

2. protectorate-20261014-152624
   The Protectorate, scenario FullScenario/2026Scenario, started 2026-10-14 15:26:24
   3 saves, 2026-02-01T00:00:00 to 2026-03-01T00:00:00
```

The save count is the number of distinct saves, with byte-identical copies counted once. The dates
are the first and last game times. A group without a real-world start says
`grouped by faction and scenario only (no real-world start)`. An unclassified group says why, for
example `unclassified (2 human players); never grouped with another save`. Files skipped inside a
named directory are listed at the end with their path, error class and message, as in `events`.

## JSON output

`--format json` prints one object:

- `inputs` (usable saves given, after directory expansion), `duplicates`;
- `skipped`: one object per file skipped inside a named directory, with `source`, `error_class` and
  `error`;
- `campaigns`: one object per group, with `index`, `key`, `faction`, `scenario` (`master`,
  `scenario`), `started` (ISO time or `null`), `unclassified`, `inputs` (the paths in the group),
  `saves` (distinct saves), `first_date`, `last_date` and `sources` (the distinct saves' paths in
  chronological order).

`events --format json` reports the chosen group as its `campaign` member in the same form.

With `--log-level info`, the run logs the number of paths and candidate files, then the number of
groups, unclassified groups and groups without a start. Faction names and directory paths are
never logged.

## Exit codes

| Code | When |
| --- | --- |
| 0 | The listing was printed. Files skipped inside a named directory do not change it. |
| 2 | Usage error: an unknown `--format`. |
| 4 | A named path cannot be read (missing or unreadable), or a named directory holds no files or no usable save. |
| 5 | A named file is not a supported save (malformed, wrong shape, or unsupported format or game version) or has no parseable game time. |
