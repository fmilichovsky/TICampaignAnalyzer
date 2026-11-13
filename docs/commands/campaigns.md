# `tinarrative campaigns`

<!-- generated: synopsis campaigns -->
```
tinarrative campaigns [--format {text,json}] PATH [PATH ...]
```
<!-- end generated -->

Lists the campaigns that the given saves belong to, with the selector that
[`events --campaign`](events.md#campaigns) and `narrate --campaign` accept. It reads only what it
needs to group the saves, so it is fast even for a full save directory. A single save is enough.

## Options

<!-- generated: options campaigns -->
| Option | Meaning |
| --- | --- |
| `PATH...` | Save files or directories, in any order; a directory is read one level deep. |
| `--format text\|json` | Report format (default text). |
<!-- end generated -->

Saves belong to one campaign when the human player's faction, the faction name, the scenario and
the real-world campaign start all match (see
[campaign grouping](../game-data-notes/campaign-grouping.md)). A save without exactly one human
player is listed as **unclassified**, on its own.

## Selector keys

Each campaign has a key built from its faction name and real-world start, such as
`resistance-20260104-113751`, and a number in the listing. `events --campaign` and
`narrate --campaign` accept:

- a key, or any prefix of a key that matches only one campaign (`protectorate`);
- the campaign's number in this listing (`2`);
- `latest`: the campaign holding the most recently modified save file, usually the one being played.

In a terminal, `events` and `narrate` without a matching `--campaign` show this listing and ask for
a selector or search text ([campaign picker](events.md#campaign-picker)).

## Output

```
2 campaigns:

1. resistance-20260104-113751
   The Resistance, scenario FullScenario/2026Scenario, started 2026-01-04 11:37:51
   5 saves, 2045-08-01T00:00:00 to 2046-10-08T00:00:00

2. protectorate-20261014-152624
   The Protectorate, scenario FullScenario/2026Scenario, started 2026-10-14 15:26:24
   3 saves, 2026-02-01T00:00:00 to 2026-03-01T00:00:00
```

The save count counts byte-identical copies once; the dates are the first and last game times.
Skipped files are listed at the end with their path and the reason.

`--format json` prints one object with `inputs`, `duplicates`, `skipped` and `campaigns` (one
object per campaign, with its key, number, faction, scenario, start, saves and date range). It is
built by [`grouping.py`](../../src/tinarrative/grouping.py).

## Exit codes

<!-- generated: exit-codes campaigns -->
| Code | When |
| --- | --- |
| 0 | The listing was printed. |
| 2 | Usage error. |
| 4 | A named path cannot be read, or a named directory holds no usable save. |
| 5 | A named file is not a supported save or has no game time. |
<!-- end generated -->

## Examples

```sh
tinarrative campaigns ~/saves
tinarrative campaigns ~/saves --format json
```
