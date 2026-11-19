# A space loss counts only when the save names who destroyed it

A ship or hab that vanished between two saves is a loss to its owner. It is credited to a destroyer only when the
save itself links that asset to that destroyer:

- **A ship** counts when its name appears in what the destroyer's `Kills` list gained against the ship's owner. A
  name that several destroyers gained against the same owner is credited to none of them.
- **A hab** counts when a destruction-log entry naming the destroyer matches it.

A loss that nothing links to a destroyer is credited to no one, and no rule credits it by looking at what else
happened in the same interval. Space losses and space campaigns are built only from credited losses and from logged
combats.

## Considered options

- **Crediting a loss by co-occurrence.** This was the old rule: a destroyer's `Kills` list grew, and the victim lost
  something in the same interval. It was rejected because neither signal shows a battle took place. A fleet also
  vanishes when it merges into another, and `Kills` also lists councilors, armies and megafauna. Together they told
  battles that never happened.
- **Counting fleets that vanished.** This was rejected because fleets are reorganised all the time. The unit of a
  loss is the ship.
- **Corroborating with the hull classes in a ship's own `kills` list.** This was rejected because a ship's record
  leaves the save when the ship is destroyed. The check would fail without a trace in exactly the heaviest fighting.
- **Keeping uncredited losses or unmatched `Kills` names at low confidence.** This was rejected because data we
  cannot explain is not used.

## Consequences

A campaign with no combat logs shows only the losses that the save links to a destroyer. Fighting the save does not
record is left out of the history rather than guessed.

Tracked in #303.
