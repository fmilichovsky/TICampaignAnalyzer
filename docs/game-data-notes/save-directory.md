# The save directory and its save modes

This note supports continuous capture ([architecture, Mode D](../architecture.md#continuous-capture-design)).
Capture needs to know which files the game writes, when it writes them and how long each one survives. Most of what
follows is a **hypothesis** taken from the description of the game's behaviour in the capture design. It has not been
checked against a watched save directory. The evidence pass on the roadmap (*Continuous capture*) turns each point
into an observation or corrects it. Until then, no code may depend on any of it beyond what the observed facts
support.

## Observed facts

These are recorded in other notes and repeated here only for orientation:

- Manual saves, `Autosave.json` and `Exitsave.json` all occur, and all are uncompressed JSON of the
  `terra_invicta_json_v1` envelope ([format](terra_invicta_json_v1.md)).
- An `Exitsave.json` was byte-identical to the manual save of the same date. An `Autosave.json` of the same game time
  was not ([chronology](chronology-and-deduplication.md)).
- Manual-save names of the Appease, Protectorate and Resist campaigns have the form
  `<Faction>save<NNNNN>_<Y-M-D>.json`, sometimes without `save`. Their sequence numbers are not a chronological order
  ([chronology](chronology-and-deduplication.md), [campaign grouping](campaign-grouping.md)).

## Hypotheses to check

1. **Location.** The saves are written to `Documents/My Games/TerraInvicta/Saves` under the user's profile on
   Windows. The folder's exact name and case, and the Proton and CrossOver locations on other systems, are not
   recorded.
2. **Manual saves.** The player names them; the default name holds the faction, an ordinal and the game date. The
   design's example, `Resistsave-00076-2030-06-28`, does not match the observed form above, so the default may differ
   between builds.
3. **Autosaves.** The game writes one at the start of every mission assignment cycle. The cycle runs 7 days early on,
   then 14, then 4 weeks late in the game. Four or five files rotate: `Autosave.json`, then `Autosave2.json` …
   `Autosave4.json`. `Autosave.json` is always the most recent. Not known: whether rotation renames the files or
   rewrites them in place, whether the count can be configured, and whether an autosave can be switched off.
4. **Combat saves.** A `CombatSave` is written right before every space battle the player takes part in. Its exact
   file name, and whether a battle with several engagements writes more than one, are not recorded.
5. **Exit saves.** `Exitsave.json` is written when the player leaves the game, and is rewritten on every exit.
6. **Writes.** Not known: how long a write of a full save takes, whether the game writes to a temporary name and
   renames it or writes the final file directly (that is, whether a partly written save is ever visible), and whether
   the modification time follows the write.
7. **Compression.** Not known whether a game setting writes compressed saves. The loader rejects them today.
8. **Loading.** Not known whether loading a save writes anything (an autosave on load, a rewritten exit save), or
   whether the next autosaves after a reload overwrite the abandoned attempt's autosaves in rotation order.
   Reloading an earlier save and playing on is the [campaign grouping](campaign-grouping.md) reload limit, which the
   design's lines ([architecture, Mode D](../architecture.md#lines-design)) resolve.
9. **Witnesses across a fork.** The records observed to be carried forward unchanged between consecutive manual saves
   (strict-prefix logs, keyed logs that never lose a key, ledger entries never rewritten; see the
   [field map](domain-field-map.md)) keep that property between consecutive autosaves, and disagree between two saves
   played on from the same earlier save. Neither has been checked: the field-map observations cover manual saves of
   one line only.
10. **Modification times.** Within one directory the game's writes leave modification times in the order the saves
    were written. The [campaign grouping](campaign-grouping.md) note saw modification times not follow game time,
    which a reload or a copy would also explain.

## What the evidence pass records

A read-only logger, `scripts/observe_saves.py` ([usage](../../scripts/observe_saves.md)), polls the directory while
a campaign is played. Per change it records the base file name, size, modification, change and birth times, inode,
SHA-256 and the game time from the save's header, and it marks a read that overlapped a write. It records no save
value beyond that game time. Every distinct save version it read whole is kept in a private archive, so the witness
records of point 9 can be compared afterwards, including on autosaves the game has since overwritten. The player's
notes (which save was loaded, battles, exits) are logged alongside as the ground truth for reloads. From the log and
the archive the pass records here, with the capture date:

- the files each save mode writes, and how rotation moves an autosave between names;
- the gap between consecutive autosaves in game time and in real time at the game's speeds, which sets the poll
  interval;
- whether a partly written file is visible and for how long, which sets `settle_seconds`;
- whether the folder location in point 1 holds;
- across at least one reload played on for several autosaves: which files the load and the following saves write,
  whether every witness record of point 9 disagrees between the two attempts, and which do not;
- whether modification times within the directory follow the order of the writes (point 10).
