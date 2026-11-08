# Reloads split a campaign into lines, told apart by witness records

When the player loads an earlier save and plays on, the saves of the abandoned attempt keep the campaign's
identity. Ordered by game time, the two attempts interleave, and every interval between them diffs two timelines.

- **Witness records decide continuity.** Save B continues an earlier save A unless a witness record contradicts it.
  A witness is a save-carried record that the game-data notes observe to be carried forward unchanged along one
  line of play ([witness records](../game-data-notes/domain-field-map.md#witnesses-across-a-reload)). Examples are
  a log that only grows as a strict prefix, a keyed log that never loses a key, and ledger entries never
  rewritten. After a fork, the attempts' witnesses disagree.
- **Absence of evidence is not a fork.** An undetermined test counts as continuing.
- **The tree is built from content.** A save's parent is the latest earlier save it continues. A campaign without a
  reload gives the same sequence as before. A fork save that was never captured is not needed.
- **Content, never capture hints.** A capture that is earlier in game time than the newest save suggests a reload.
  The tree still ignores it: only save content decides.
- **Lines and the current line.** A line runs from the campaign's first save through its forks. In a store, the
  current line holds the most recently captured save. Saves given as paths have no capture order, so a campaign
  with several lines needs a choice, as several campaigns do.
- **Abandoned lines are kept.** Any line can be analysed or narrated as an alternate history. No narrative mentions
  a reload: it is an act of the player, not an event of the campaign.

## Considered options

- **Detecting reloads from capture order.** It was rejected because catch-up and imports reorder captures.
- **Discarding the abandoned attempt.** It was rejected because those saves are evidence, and the player may
  return to them.

Tracked in #216.
