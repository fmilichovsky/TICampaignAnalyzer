# Significance is judged once and scaled by stake

Not every state change belongs in a campaign history. Significance lets a reader ask for anything from a concise
summary to a forensic log. It measures impact, not certainty, and is independent of confidence.

- **One place judges impact.** Analyzers, reconstruction and narrative rules never weigh an event themselves. A
  post-pass assigns significance from the event's kind and context, records the reason, and tunes no threshold to
  one campaign.
- **Evidence events rank low.** An event that is evidence for the rules that explain it is `trivial` on its own:
  a statistic shift, a band crossing, a rank change. Routine churn is `trivial` too. Leftover relation lists stay
  `minor`, so the unexplained residue is never hidden.
- **A score with fixed level bands.** Every event has a 0–100 score, and its level is the fixed band that holds the
  score, so the two never disagree. The level is the deterministic cut-off; the score orders events within it.
- **A stake is a share, on a log scale.**
  - A stake is a share of a world total in the same snapshot, never an absolute magnitude. Magnitudes grow by
    orders of magnitude over a campaign; shares stay comparable.
  - Ten score points are a tenfold share relative to a reference share, within a clamp.
  - A stake measures what the event moved, not only who acted. It is read on the interval's earlier side.
  - Only the types whose impact grows with the stake are scaled; movement and churn never are.
  - Shares add, so a war side, a federation or a faction's holdings are sums.
- **Space totals count humans only.** The alien faction holds nearly every space asset early in a campaign
  ([space assets](../game-data-notes/space-assets.md)). Counting it would make the aliens half the world from the
  start; counting humans alone would make one early station half of space. So space shares are taken over the human
  total with a saturation floor. A faction's stake weighs space more as humans build up a real presence there.
- **Battles use contested mass.** A side's mass is weighted up for alien ships. Mass beyond a multiple of the
  opponent's adds nothing, so a large fleet swatting a scout is a skirmish. The outcome never changes the stake.
- **The maximum, never a sum.** A narrative event scores the higher of its rule's base plus its own stake and the
  highest score among the events it cites. One fact is often recorded several times, so a sum would rank events
  by how often they were recorded.
- **Perspective is not impact.** The player's faction stays a concern of the narrator.

## Considered options

- **Absolute magnitudes** such as GDP or ship counts. They were rejected because late-campaign events would
  outrank every early one.
- **Summing constituent scores.** It was rejected because it rewards duplicate records.
- **Counting the alien faction in space totals.** It was rejected because humans would rank near zero until the
  late game.

Tracked in #199, #200 and #201.
