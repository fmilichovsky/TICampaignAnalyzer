# The save directory and its save modes

This note supports continuous capture ([architecture, Mode D](../architecture.md#continuous-capture-design)).
Capture needs to know which files the game writes, when it writes them and how long each one survives.

## Evidence

Observed on 2026-10-29 with `scripts/observe_saves.py` ([usage](../../scripts/observe_saves.md)) on Windows. There
were two logger sessions of 34 and 12 minutes, the default 0.2 s poll, and the player's notes as ground truth. Over
the two sessions the game wrote 10 autosaves, 1 manual save, 1 combat save and 2 exit saves. The play covered the
Protectorate campaign continued from its newest manual save, then a reload of an earlier Protectorate manual save
played on for three autosaves, then a switch to the Resist campaign with one space battle. Each distinct save
version was archived, so the witness records could be compared afterwards ([witnesses](#witnesses-across-a-reload)).

Earlier observations, recorded in other notes:

- Manual saves, `Autosave.json` and `Exitsave.json` all occur. All are uncompressed JSON of the
  `terra_invicta_json_v1` envelope ([format](terra_invicta_json_v1.md)).
- An `Exitsave.json` was byte-identical to the manual save of the same date. An `Autosave.json` of the same game time
  was not ([chronology](chronology-and-deduplication.md)).

## Observed facts

1. **Location.** `Saves` inside `My Games\TerraInvicta` inside the user's Documents folder, spelled with that case.
   On the observed machine, Documents was redirected to OneDrive and had a localized name (`OneDrive\Dokumenty`). A
   literal `%USERPROFILE%\Documents` path does not find it. The folder also held `PlayerOptions.TIProfile` and
   `steam_autocloud.vdf`, so Steam Cloud syncs it.
2. **Manual saves.** The default name is `<nickname>save<NNNNN>_<Y-M-D>.json`. The nickname is the faction's
   council name (`Appease` for the Protectorate, `Resist` for the Resistance). The `Protectorate000NN` files were
   renamed by the player. `<NNNNN>` is one counter per install, shared by every campaign and only ever going up
   (confirmed by the player; the 34 numbered files rise in the order they were created). It is a write order, not a
   game-time order. *Hypothesis:* it restarts when the save directory is wiped. Each new manual save is a new file.
   Saving over an existing manual save keeps that file's name and number: one file named `…_2028-9-16` held the
   state of 2028-09-23, created 4 minutes before it was last modified.
3. **Autosaves.** There are **three** slots: `Autosave.json` (newest), `Autosave2.json` and `Autosave3.json`.
   Rotation **renames**: at each autosave the file ID moves from `Autosave` to `Autosave2` and from `Autosave2` to
   `Autosave3`, the old `Autosave3` is replaced, and a new `Autosave.json` is created. The rename and the creation
   fell in the same 0.2 s poll; once, `Autosave.json` was missing for one poll in between. The game-time cycle in
   2028 was twice a month, on the 1st at 00:00 and the 16th at 12:00 (twelve autosaves seen, none skipped). In
   2046 a load on 02-22 was followed by an autosave on 03-16 at 00:00, with no autosave on 03-01. *Hypothesis:* the
   cycle becomes monthly late in the game. In real time, autosaves came 4 min 22 s to 7 min 11 s apart in normal
   play, and **53 s** and 76 s apart while time ran at high speed. A version stays in some slot for three cycles.
4. **Combat saves.** `CombatAutosave.json`, one file, rewritten in place (same file ID). It was written once for the
   one battle, finished about 11 s before the player noted the battle start. Its game time is the battle's moment,
   not a cycle date (21:53:44). It does not rotate, so the next battle replaces it. *Hypothesis (from play):*
   consecutive combat saves are at least 10 s apart, because the player must play out or auto-resolve a battle and
   let time run before the next one.
5. **Exit saves.** `Exitsave.json`, rewritten in place (same file ID) on every exit. Written 47 s after a manual
   save with no time run, it was byte-identical to that save. Written after the autosave of the same game time,
   it differed from it (see the ledger rule in [witnesses](#witnesses-across-a-reload)).
6. **Writes.** The game writes the final file directly; no other file name appeared, even for one poll. It first
   creates or truncates the file to **0 bytes and leaves it empty for 2.1–3.5 s**, then writes it in one pass in
   0.9–1.6 s, at 49–59 MB/s. The whole write took 3.1–3.3 s for 53–54 MB saves and 4.7–5.0 s for 79–80 MB
   saves. While the data is being written, size and modification time changed at every poll. The header with
   `gameTimeString` is present from the first chunk, so a readable header does not mean a complete file. The
   previous content of an exit or combat save is gone as soon as its rewrite starts.
7. **Compression.** All 14 writes were uncompressed JSON. The game's settings were not searched for a compression
   option.
8. **Loading.** Loading a save writes no save file. Loading rewrote `PlayerOptions.TIProfile` (twice, by replace)
   and nothing else. After a reload the rotation simply continues: the first autosave of the new attempt pushed the
   abandoned attempt's two newest autosaves into `Autosave2` and `Autosave3`. The rotation, the combat save and the
   exit save are **shared by all campaigns**. After switching campaigns, `Autosave.json` held a 2046 Resist save
   while `Autosave2.json` held a 2028 Protectorate one. A slot name says nothing about campaign, line or order.
9. **Witnesses across a reload.** See [witnesses](#witnesses-across-a-reload).
10. **Modification times.** Within the sessions, modification times followed the order of the writes, and rotation
    renames kept them. Creation times do not identify a file: when the new `Autosave.json` is created, Windows hands
    it the creation time of the file that just left that name. All autosave, exit and two manual-save files carried
    creation times from one minute a week earlier. Three manual saves had creation times *later* than their
    modification times, and all three had modification times in whole seconds. So something outside the game
    re-creates files with their old modification time; cloud sync is the likely cause. Their modification times
    still followed the original write order.

Also present: a `Quicksave.json`, created years before and last modified during the Protectorate campaign, so it is
rewritten in place. When the quicksave is written was not observed.

## Witnesses across a reload

The records that tell two lines of play apart are listed, with their contradiction rules, in the
[field map](domain-field-map.md#witnesses-across-a-reload). They were checked on the archived saves of both
sessions. The [campaign grouping](campaign-grouping.md) rule kept the saves of both Protectorate attempts in one
campaign, as the lines design expects.
