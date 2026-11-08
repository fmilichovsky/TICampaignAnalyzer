# Save-carried records are evidence of their own

Some save fields are dated logs or cumulative counters, such as:

- a faction's resource ledger, its hab destruction log and the control points it lost;
- kill lists, milestones, and a nation's last executive change.

They fill the gaps between sparse saves with exact dates that no diff can give. So they form their own layer of
evidence, between the snapshot state and the inferred events. An event built from an entry is objective and dated
by that entry. It is never folded into an inference.

A field is a record when three things hold: its entries are dated or cumulative, they cannot be derived from the
rest of the snapshot, and the game carries them forward from save to save rather than recomputing them. Rolling
windows and running histories that the game recomputes from current state are derived history. They are not
normalized.

- A problem inside one entry, such as an unparseable date or an unresolvable reference, stays inside that entry.
  The rest of the log remains evidence.
- The diff compares a log as a multiset of entries and never assumes it only grows. The ledger, for one, is pruned.
- A later stage may date an event by a record entry rather than by the save interval, but must cite the entry.

The lifecycle of each record is in the [field map](../game-data-notes/domain-field-map.md) and the
[higher-level event sources](../game-data-notes/higher-level-event-sources.md).
