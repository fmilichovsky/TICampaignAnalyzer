# Observing the save directory

`observe_saves.py` records how Terra Invicta writes its save directory while you play. It is the logger of the
continuous-capture evidence pass (roadmap, *Continuous capture*). Its log answers how autosaves rotate, which files
combat and exit saves write, and how long a write takes. Its archive keeps every save version, so the records that
tell two lines of play apart can be compared after a reload ([the save directory](../docs/game-data-notes/save-directory.md),
points 8 to 10).

The script only reads the save directory. It never creates, renames or deletes anything there, and it refuses a log
or an archive inside it.

## Running it

It needs Python 3.11 or later and nothing else. It uses the standard library only, so copying the single file to the
gaming machine is enough. Start it **before you launch the game**, so the first write is seen, and leave the terminal
open while you play.

Windows (PowerShell):

```powershell
py scripts\observe_saves.py "$env:USERPROFILE\Documents\My Games\TerraInvicta\Saves" `
    --out "$env:USERPROFILE\ti-observe\log.jsonl" --archive "$env:USERPROFILE\ti-observe\archive"
```

If your Documents folder is redirected, for example to OneDrive, give that path instead. The `start` record logs the
folder exactly as the file system spells it.

Linux (Proton) or macOS (CrossOver): point it at the `Saves` folder inside the Wine prefix, for example
`~/.steam/steam/steamapps/compatdata/<app id>/pfx/drive_c/users/steamuser/Documents/My Games/TerraInvicta/Saves`,
with the log and archive in a private folder such as `~/ti-observe/`.

Keep the log and the archive outside both the save directory and the repository, or under the repository's ignored
`build/`.

### Arguments

| Argument | Recommended | Why |
|---|---|---|
| `DIRECTORY` | the game's `Saves` folder | Read only. |
| `--out` | `<private folder>/log.jsonl` | Appended to, so one file can hold every session. |
| `--archive` | `<private folder>/archive` | One `<sha256>.json.xz` per distinct save version. |
| `--interval` | `0.2` (default) | A full save takes a moment to write. Polling every 0.2 s catches it half written and catches temporary files that live for less than a second, which `settle_seconds` is derived from. A longer interval can miss both. |
| `--no-notes` | leave off | Only for running without a terminal, which loses the notes below. |

A full save compresses to about 1.3 MB (from about 75 MB late in a campaign) in under two seconds, on a worker
thread. A session with a few dozen autosaves needs well under 100 MB. Files that repeat a version already archived,
such as an exit save identical to a manual save, are not stored twice.

### Stopping and resuming

Press Ctrl+C (or end the process). The script finishes compressing what is queued and logs `stop`. Run the same
command again to resume: the log is appended to, and versions already in the archive are not written again.

## Notes you are expected to type

The directory cannot show which save you loaded, or that a battle has started. Type it into the script's terminal,
one line per event, and press Enter when it happens. Each line is logged as a `note` with the time it was typed.
Switch to the terminal (Alt+Tab) when needed; the game keeps running.

| When | Type | Required |
|---|---|---|
| Right before you load a save, from the menu or in game | `loaded <file name>`, for example `loaded Resistsave00075_2043-3-16` | **Yes.** It is the only record of where a reload starts a new line, and the ground truth the witness rules are checked against. |
| After a manual save | `manual <file name>` | Helps |
| When a space battle starts and when it ends | `battle start`, `battle end` | Helps: it ties the combat save to the battle |
| Before leaving the game | `exit` | Helps |
| When you change the game speed or pause for long | `speed <1-5>`, `pause`, `resume` | Helps: it explains the real-time gap between autosaves |
| Anything else unusual (a crash, a settings change, a compressed-save option) | free text | — |

Do not type anything personal: notes go to the log verbatim.

## What a session should cover

The evidence pass asks for manual saves, several autosave cycles, a space battle, an exit, and at least one reload of an
earlier save played on for several autosaves. A reload is worth the most when the abandoned attempt also ran
several autosaves, because the witness records of the two attempts can then be compared.

## The log

There is one JSON object per line. Every record has `event`, `observed` (UTC, ISO 8601) and `observed_ns`.

| `event` | Fields |
|---|---|
| `start` | `tool_version`, `interval`, `platform`, `python`, `directory` (as the file system spells it) |
| `present` | a file already there at start; the same fields as `added` |
| `added`, `changed`, `reread` | `name`, `size`, `mtime_ns`, `ctime_ns`, `inode`, `birthtime_ns` (where available), `sha256`, `game_time` (`.json` only), `archive` (`queued`, `duplicate`, `unstable`, `error`, `not_save`); `unstable` with `size_after` and `mtime_ns_after` when the file changed while it was read; `error` with the exception name when it could not be read; `gave_up` after the last retry |
| `removed` | `name` |
| `archived`, `archive_failed` | `sha256`, `compressed_size` or `error` |
| `note` | `text` |
| `stop` | `reason` |

`reread` is a file read again on the next polls because its last read failed or overlapped a write. Same `inode`,
new content means the file was rewritten in place. A `removed` followed by an `added` with the same `inode` means it
was renamed.

## Privacy

The log holds file names and a path, and the archive holds whole saves. Neither is ever committed or attached to an
issue. Only the findings go into [the save directory note](../docs/game-data-notes/save-directory.md): names, counts,
durations and dates.
