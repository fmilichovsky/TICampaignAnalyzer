# Significance is judged once and scaled by share

Not every state change belongs in a campaign history. Significance lets a reader ask for anything from a concise
summary to a forensic log. It measures impact, not certainty, and is independent of confidence. What each level
means to a reader is in the [editorial direction](../editorial-direction.md); how a base level and a scaling are
judged to deliver it is in the [calibration principles](../calibration-principles.md).

- **One place judges impact.** Analyzers, reconstruction and narrative rules never weigh an event themselves. A
  post-pass assigns significance from the event's kind and context, records the reason, and tunes no threshold to
  one campaign.
- **Evidence events rank low.** An event that is evidence for the rules that explain it is `trivial` on its own:
  a statistic shift, a band crossing, a rank change. Routine churn is `trivial` too. Leftover relation lists stay
  `minor`, so the unexplained residue is never hidden.
- **A score with fixed level bands.** Every event has a 0–100 score, and its level is the fixed band that holds the
  score, so the two never disagree. The level is the deterministic cut-off; the score orders events within it.
- **A share, read on a log scale.**
  - A share is a fraction of a world total in the same snapshot, never an absolute magnitude. Magnitudes grow by
    orders of magnitude over a campaign; shares stay comparable.
  - Each scaled kind has a scaling: the share at which its event rises a level above its starting level and,
    unless it keeps the default width, the share at which it drops one. Further levels are as wide, and the score
    runs evenly in log share across each band. Kinds share a scaling only when the same reason holds for both.
  - A share never moves an event below minor: size is never a reason to drop out of the story.
  - A measure of what the event moved, not only who acted. It is read on the interval's earlier side.
  - Only the types whose impact grows with the share are scaled; movement and churn never are.
  - Shares add, so a war side, a federation or a faction's holdings are sums.
- **Space totals count humans only.** The alien faction holds nearly every space asset early in a campaign
  ([space assets](../game-data-notes/space-assets.md)). Counting it would make the aliens half the world from the
  start; counting humans alone would make one early station half of space. So space shares are taken over the human
  total with a floor, which only keeps a share defined. The floor and the saturation, the holdings at which space
  counts fully in a faction's share, are separate: a faction's share weighs space more as humans build up a real
  presence there.
- **Battles use contested mass.** A side's mass is weighted up for alien ships. Mass beyond a multiple of the
  opponent's adds nothing, so a large fleet swatting a scout is a skirmish. The outcome never changes the share.
- **A nuclear arc uses its nuclear share.** An armament, buildup or disarmament scales by the warheads it moved, net,
  over the world's warheads. The world total is taken at the larger of the arc's two ends, not on the earlier side, so
  it always holds the moved warheads and a buildup from a near-empty world is a share of at most one. A single
  warhead shift is evidence, so a great power's token buildup does not inherit the power share of the shift it
  cites.
- **The maximum, never a sum.** A narrative event scores the higher of its rule's base plus its own share and the
  highest score among the events it cites. One fact is often recorded several times, so a sum would rank events
  by how often they were recorded.
- **Shares are computed once per save, and one path scores every event.** Two scoring paths drifted apart whenever
  one was fixed; the tiers differ only in where an event's entities are read from. Only a narrative event is lifted
  by the events it cites: an atomic event cites evidence to find its entities, not to inherit its rank.
- **Perspective is not impact.** The player's faction stays a concern of the narrator.

## Considered options

- **Absolute magnitudes** such as GDP or ship counts. They were rejected because late-campaign events would
  outrank every early one.
- **Summing constituent scores.** It was rejected because it rewards duplicate records.
- **Counting the alien faction in space totals.** It was rejected because humans would rank near zero until the
  late game.
- **One reference per measure, a fixed rate and a clamp.** It was rejected because every kind moved alike, while
  the kinds of one measure sit orders of magnitude apart: a war's sides against one nation.
- **A share per level.** It was rejected because it ties a scaling to the base level, so a base could not change
  without rewriting it.

Tracked in #199, #200, #201, #360 and #568.
