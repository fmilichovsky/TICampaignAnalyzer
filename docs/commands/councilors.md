# `tinarrative councilors`

```
tinarrative councilors <path> [<path>...] [--campaign <selector>] [--player-only] [--output <dir>] [--config <file>]
```

Selects the notable councilors of a campaign and builds the dossier a neutral, public-perception
article about each would be written from. It is a dry run: it never contacts the network and never
calls a model. Stdout gets a one-line summary per selected councilor, and `--output` writes
`dossier.json`.

## Who is selected

From the latest save, a councilor needs at least `councilors.min_tenure_days` of employment
(365 by default) and a human faction. Alien-faction councilors, the unemployed pool and departed
councilors are never selected. Then:

- every councilor of the player's faction is selected;
- of each other human faction, the `councilors.rivals_per_faction` most prominent (2 by default).
  `--player-only` drops them.

Prominence ranks by organization tier squared (summed over the councilor's organizations), then
the skill sum, then XP, then entity ID. The player's faction is the one of the save's single human
player.

## Input

The same inputs as [`events`](events.md): one save, or several saves and directories of one
campaign (`--campaign` and the [campaign picker](events.md#campaign-picker) as there).

- **The portrait** comes from the latest save and may use everything in it, including
  councilors the other factions have not detected. `Loyalty` and `ApparentLoyalty` are never
  written.
- **The career** (faction, detention, status and organization changes) comes from the events
  between the saves. One save gives an empty career.
- **Missions** are listed for the player's councilors only, as mission and target groups with their
  counts (`councilors.missions_per_councilor` of them, the most frequent first).

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `PATH...` | | One save, or save files and directories of one campaign. |
| `--campaign SELECTOR` | | The campaign to use when the saves hold several. |
| `--player-only` | off | Select the player's councilors only. |
| `--output DIR` | | Write `dossier.json` here; without it only the summary is printed. |
| `--config FILE` | `$TINARRATIVE_CONFIG`, else built-in | Settings file; the `[councilors]` keys are in [configuration](../configuration.md). |

## Output

`dossier.json` has a header (`as_of`, `source` as the file name of the latest save, `player_faction`
and the `selection` settings) and a `councilors` list, the player's councilors first. Each entry
carries identity, traits, the seven skills, age, home region and nation, recruitment date and
tenure, organizations, prominence, career and, for the player's councilors, missions.

An organization entry names its nature: `origin` (`generated` or `real`), `category` and the
`basis` of the category. A generated organization takes its category from its template (`template`).
A real-world organization takes it from a hand-assigned catalog of the game's named organizations
(`catalog`); one the catalog does not know yet is categorized by the effects it grants (`stats`). The
categories are `research`, `security_intelligence`, `military`, `militant`, `aerospace`, `government`,
`public_interest`, `commercial`, `engineering_industry`, `technology`, `mining_resources`,
`media_influence`, `ngo`, `criminal`, `vigilante` and `other`. The raw `template` is kept for audit.

## Exit codes

| Code | When |
| --- | --- |
| 0 | The summary was printed and, with `--output`, the dossier was written. |
| 2 | Usage error: the save input errors of `events` (several campaigns without `--campaign`, fewer than two usable saves among several inputs). |
| 4 | A save cannot be read. |
| 5 | A save is not a supported save. |
| 8 | The settings file cannot be read or is not valid settings. |
| 9 | `--output` cannot be written. |

## Examples

```sh
tinarrative councilors saves/Protectorate00092.json
tinarrative councilors saves/ --campaign protectorate --player-only --output dossier/
```
