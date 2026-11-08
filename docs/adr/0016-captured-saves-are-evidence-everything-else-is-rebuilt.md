# Captured saves are evidence; everything else is rebuilt

The game's rotating autosaves, combat saves and exit saves sample a campaign far more densely than manual saves.
But the game overwrites them within minutes ([save directory](../game-data-notes/save-directory.md)). Continuous
capture copies every save the game writes into a store. It applies
[ADR-0003](0003-pipeline-stages-keep-the-evidence-below-them.md) to storage.

- **Two members are evidence.** One is every distinct save, kept byte for byte and addressed by the hash of its
  uncompressed bytes. The other is an append-only log of every capture. The index, the campaigns and the interval
  cache are derived from them and can be deleted and rebuilt. Only narration responses are costly to make again.
- **Capture does as little as possible**, because its one job is to win the race against the game.
  - It takes a file once the file is stable, and rejects nothing. A file that is not a supported save is marked
    when indexed, so a wrong rejection can be undone.
  - Parsing runs after pending captures.
  - File names are display hints, never a chronology.
- **Catch-up is the same pass.** Saves written while nothing was capturing join the timeline wherever their game
  time places them. A save overwritten in that time is gone, and the store does not pretend otherwise.
- **One writer, explicit narration.**
  - One process captures into a store at a time. Readers run alongside it.
  - Capture never contacts a provider. A growing campaign is narrated only when the user asks
    ([ADR-0018](0018-a-growing-campaign-is-narrated-in-sealed-installments.md)).
- **The store belongs to the user.** It lives outside the save directory, which belongs to the game, and outside the
  repository. Its logs never carry a file name or a string read from a save.

## Considered options

- **A database.** It was rejected for now: plain files suffice, and the event model assumes no persistence
  technology.
- **Analysing during capture.** It was rejected because a full parse is slow and the race is not.

Tracked in #209, #210, #211, #212 and #213.
