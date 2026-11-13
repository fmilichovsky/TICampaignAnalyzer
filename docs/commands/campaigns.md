# `tinarrative campaigns`

<!-- generated: synopsis campaigns -->
```
tinarrative campaigns [--format {text,json}] PATH [PATH ...]
```
<!-- end generated -->

Lists the campaigns your saves belong to, with the key that `--campaign` accepts. Run it first when a save directory
holds more than one campaign, to find the one to pass to `events`, `narrate` or `councilors`. It is fast even on a
full save directory. See [saves and campaigns](README.md#saves-and-campaigns) for the selector forms.

## Examples

```sh
# Which campaigns are in my save directory?
tinarrative campaigns ~/saves
```

## Options

<!-- generated: options campaigns -->
| Option | Meaning |
| --- | --- |
| `PATH...` | Save files or directories, in any order; a directory is read one level deep. |
| `--format text\|json` | Report format (default text). |
<!-- end generated -->

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

A save without exactly one human player is listed as **unclassified**, on its own. Skipped files are listed at the end.

## Exit codes

<!-- generated: exit-codes campaigns -->
| Code | When |
| --- | --- |
| 0 | The listing was printed. |
| 2 | Usage error. |
| 4 | A named path cannot be read, or a named directory holds no usable save. |
| 5 | A named file is not a supported save or has no game time. |
<!-- end generated -->
