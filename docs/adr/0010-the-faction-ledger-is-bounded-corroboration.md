# The faction ledger is bounded corroboration

Each faction's `Transactions` ledger records charges whose labels include mission and operation names. It is the
only dated trace of councilor actions. But it is weak evidence in four ways:

- an entry names no target;
- some labels are hashed;
- each label's list is pruned;
- a charge is made when the mission is assigned, up to weeks before it resolves.

The details are in the `Transactions` section of the
[higher-level event sources](../game-data-notes/higher-level-event-sources.md). So the ledger may attribute an action
to a faction and narrow its date only where a visible effect already exists, under these bounds:

1. Only a documented allow-list of councilor-mission and asset labels produces events; space operations are left
   out. Each label is checked against a visible effect.
2. Entries are read by date from the later snapshot inside the window, never from their presence in the diff.
3. A transaction event is `minor`. It is cited only as corroboration of an effect that is already evidenced,
   within a window from the entry date up to the assignment-to-outcome bound, and never after the effect. It may
   narrow a span's start but never sets its end.
4. A faction is credited with the action only when exactly one faction's ledger carries the label in the window
   and that faction is the visible beneficiary. Otherwise the event lists candidates and credits nobody.
5. The event is dated by the entry only in that single-candidate case.
6. A narrative event resting on ledger evidence alone is capped at medium confidence. One charge may corroborate
   events in several nations and identifies none of them.
7. `Unrest` entries are checked against the faction's unrest attempts before either is trusted.

A councilor's current mission field is never used. It shows the assignment at save time, not what happened.

## Considered options

- **The ledger as primary evidence.** It was rejected because an entry has no target and precedes its outcome.
- **The councilor mission field.** It was rejected because it is a snapshot of an intention, and the next save may
  already show another one.
