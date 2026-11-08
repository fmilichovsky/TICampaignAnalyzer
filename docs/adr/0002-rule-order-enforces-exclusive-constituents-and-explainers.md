Superseded by ADR-0019

# Rule order enforces exclusive constituents and explainers

A narrative rule sees only the narrative events of lower orders. That one visibility rule now also carries two
guarantees that rules used to keep by hand:

- **Exclusive constituents.** A kind may declare what its events cite as their own. Rules of a higher order get
  the events those constituents name hidden from citation, while still reading them for context. The aggregation
  step raises if an event of another kind cites one. Events of the same kind may share them.
- **Explainers.** A rule declares the kinds whose events explain away its own, such as a takeover explaining an
  unrest band shift. The aggregation step raises if an explainer's order is not lower than the rule's.

So a rule with exclusive constituents runs on an order below every rule that must avoid them. It does so even when
it reads nothing of a lower order itself, as the merger does. Under the old design, rules of the merger's own order
each predicted what it would take, and their predictions drifted from what it cited. A second guarantee is what an
explainer of the same order lacked: it was never seen, and nothing said so.

## Considered options

- **A check only, with each rule keeping its own filter.** It was rejected because the per-rule predictions are the
  duplication this replaces; the check stays as a backstop.
- **The builder silently drops an exclusive constituent** from another event's citations. It was rejected because
  it hides the code bug that cited it.
- **One invariant for every narrative event: each event is cited at most once.** It was rejected because some
  overlap is legitimate. One relation change belongs to both nations' realignments, and takeovers of one period
  share councilor events.
- **Explainers declared on the kind.** It was rejected because explaining is a rule's judgement, not part of what an
  event type means.

Tracked in #344.
