# The diff and the analyzers stay literal

The diff records what changed and never why: the entity, the field, the value before and after, and evidence for
each side. Reordering a list is not a change. Analyzers turn one interval's diff into objective atomic events under
these rules:

- **The diff is the evidence.** Snapshots supply context only, such as an entity's name or which nation a control
  point belongs to. An analyzer never re-derives a fact from them.
- **Ownership is not control.** A nation's list of control points says which points belong to it. Only a control
  point's own controller says who controls it; reading a faction's hold on a nation is reconstruction.
- **Wording follows the field.**
  - The words *destroyed*, *destruction* and *refit* appear only in event types whose primary source is the field
    that literally says so.
  - A vanished fleet, army or hab is reported as absent or unresolved, never as lost in battle.
  - No analyzer names a purge, coup, annexation, defection, declared or won war, or peace.
  - A statistic band carries the game's own label, never one of ours
    ([nation statistics](../game-data-notes/nation-metrics.md#value-bands)).
- **No literal change is dropped.** Each mirrored reference list has one owning analyzer, so no change is reported
  twice. A list member that no event explains is reported as a generic field change.
- **Emission thresholds live with the analyzer**, so no analyzer depends on the narrative stage.

Atomic events are the base every inference cites. Any interpretation that slipped in here could not be told apart
from fact further down.
