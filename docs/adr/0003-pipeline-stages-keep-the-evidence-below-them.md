# Each pipeline stage adds interpretation and keeps the evidence below it

A save is built for resuming play, not for explaining what happened, and the game keeps no event log. The analyzer
treats saves as snapshots of a changing world and reconstructs their history as a pipeline. Each stage adds
interpretation on top of the stage below and discards none of it:

``` text
save files → normalized snapshot (entities and save-carried records)
  → state diff → objective atomic events → inferred atomic events
  → narrative events → rendering (Markdown report, narrator package, LLM prose)
```

Every derived event cites the evidence beneath it. That is the save, state type, map ID and JSON path of each side
of a change, or the record entry it reads. An inferred or narrative event cites its constituents' sources, with
their roles (primary or corroborating). So every claim in the output traces back to a save, and creating a
higher-level event never loses evidence.

Rendering is downstream and replaceable. It never rediscovers what happened, and prose never becomes the
authoritative source of a fact. Given the same saves and the same code, the structured events are the same.

## Considered options

- **Telemetry or a mod that records events in the game.** It was rejected because the analyzer must work from
  ordinary saves, with no change to the game.
- **Letting each stage replace the one below**, such as keeping only narrative events once they are built. It was
  rejected because an inference whose evidence is gone cannot be audited or corrected.
