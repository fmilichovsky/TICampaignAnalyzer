# Reconstruction infers from explicit rules over one interval

Some events are not one state transition. A takeover, for example, shows up as several changes together:

- a nation's executive control point changing hands;
- its executive-change record naming a coup;
- a councilor disappearing.

Reconstruction combines that objective evidence by named rules. The evidence behind each rule is in the
[higher-level event sources](../game-data-notes/higher-level-event-sources.md).

- **One interval, objective inputs.** A rule sees one interval's objective events, with the snapshots and the diff
  as context. No rule builds on another inference.
- **Snapshot facts qualify; they never prove.** A fact read from one snapshot alone, such as a nation holding no
  regions afterwards, can only qualify evidence.
- **Ambiguity is kept.** Where several explanations fit, each candidate is emitted one confidence level lower,
  marked ambiguous, with the others as alternatives. Otherwise the event stays a conservative objective
  description.
- **No invented causality.** A cause the save records stays an attribute; none is added to make better prose.

## Considered options

- **Scoring heuristics or clustering.** It was rejected because an opaque score cannot be cited or argued with.
- **Rules that build on other inferences.** It was rejected because errors compound with no evidence beneath them.
  Joining evidence across intervals belongs to narrative aggregation
  ([ADR-0009](0009-narrative-aggregation-uses-anchored-rules.md)).
