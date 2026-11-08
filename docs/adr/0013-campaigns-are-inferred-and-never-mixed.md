# Campaigns are inferred and never mixed

The save format carries no campaign ID, yet one save directory holds every campaign the player has. Saves are
grouped into campaigns by a documented continuity profile
([campaign grouping](../game-data-notes/campaign-grouping.md)).

Grouping is inference with provenance:

- every group carries the signals it was formed on;
- conflicting or missing evidence produces separate or unclassified groups, never an invented chronology;
- an analysis never mixes groups.

## Considered options

- **One directory is one campaign.** It was rejected because the game writes every campaign into the same
  directory.
- **Grouping by file name.** It was rejected because players rename saves, and the default name uses an internal
  faction nickname rather than the campaign.
