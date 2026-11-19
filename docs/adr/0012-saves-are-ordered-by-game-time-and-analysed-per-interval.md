# Saves are ordered by game time and analysed per interval

Saves arrive in any order, under any name. A campaign's saves are ordered by their game time:

- a save without a game time is rejected rather than placed by its name;
- byte-identical saves are one save with several paths.

Each consecutive pair is analysed as one interval: diff, analyzers, significance and reconstruction, keyed by the
later save. At most two snapshots are held at a time. Event IDs are qualified by their interval before the
streams merge ([chronology](../game-data-notes/chronology-and-deduplication.md)). Joining evidence across
intervals is the job of narrative aggregation ([ADR-0009](0009-narrative-aggregation-uses-anchored-rules.md)).

## Considered options

- **One diff of the first and last save.** It was rejected because it hides every intermediate state. A nation
  that changed hands and changed back shows no change at all.
- **Holding every snapshot.** It was rejected because memory would grow with the campaign. Situation reports carry
  what rules spanning several intervals need.
- **Ordering by file name or modification time.** It was rejected because players name saves and the game rotates
  its autosaves.
