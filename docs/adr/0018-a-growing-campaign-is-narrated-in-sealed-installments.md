# A growing campaign is narrated in sealed installments

Narrating a grown package again re-plans every chapter. The derived period may change and every request names the
chapter count, so the whole history would be told again in new words. An installment narrates only what came after
the last one and leaves the earlier prose as it was.

- **Sealing.** An installment is sealed when it is assembled, and its closing save is the seal. A sealed installment
  is never planned or sent again. The first installment fixes the request options for all later ones.
- **No reopening.** Later installments never reopen the history.
- **Continuity from sealed requests.** Continuity across a seal comes from the sealed requests, never from their
  prose ([ADR-0015](0015-chapters-are-independent-requests.md)). It includes narrative events that started before
  the seal but only became visible once later saves existed.
- **Drift is reported, never re-narrated silently.** Drift means one of three things:
  - a save that lands inside a sealed span;
  - a sealed event that no longer exists;
  - a seal left on an abandoned line ([ADR-0017](0017-reloads-split-a-campaign-into-lines.md)).

  The user chooses to unseal from an installment onward.

## Considered options

- **Re-narrating everything each time.** It was rejected because earlier prose would change under the reader, and
  the cost would grow with the campaign.
- **Appending with the earlier prose as context.** It was rejected for the reasons in ADR-0015.

Tracked in #214.
