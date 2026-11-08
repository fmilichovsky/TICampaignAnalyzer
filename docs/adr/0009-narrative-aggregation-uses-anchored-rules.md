# Narrative aggregation uses anchored rules over the whole campaign

Aggregation is the first stage allowed to see more than one interval. It turns a campaign's event stream into the
narrative events a history reports: a faction taking over a nation and consolidating its hold, a war from
declaration to peace, a federation's life.

- **Anchors decide existence.** A rule emits only when its anchor evidence exists, such as an executive change, a
  war present in one save and absent in a later one, or a change in a federation's members. Time and shared
  entities decide which further events attach to an anchor, never whether a narrative event exists.
- **Windows are game days.** A window is measured in game days, never in saves, because save spacing is arbitrary.
  It counts from the earliest date an event can have had. So consecutive intervals always touch, and a long
  interval never splits one narrative event.
- **Situation reports, not snapshots.** Aggregation reads one situation report per save and never a snapshot. This
  keeps the bound of two snapshots in memory ([ADR-0012](0012-saves-are-ordered-by-game-time-and-analysed-per-interval.md)).
- **Constituents set the rest:**
  - Status is objective only when every constituent is objective and the join is by a stable entity ID.
  - Confidence is the constituents' minimum, one level lower for a heuristic join.
  - Significance is never below the most significant constituent.
  - The constituents' sources are kept, with their roles.
- **Rules are ordered.** A rule sees only the narrative events of lower orders, so rules cannot form cycles
  ([ADR-0002](0002-rule-order-enforces-exclusive-constituents-and-explainers.md) builds on this).
- **Open events extend.** A narrative event whose anchor is still present in the last save is open. A later run
  over more saves extends it rather than emitting a second one.
- **Roles, not prose.** A narrative event says who acted, on whom, who benefited and who assisted. Its attributes
  stay literal facts.

## Considered options

- **Grouping by temporal proximity and shared entities.** It was rejected for two reasons. Nobody can explain the
  groups it produces, and a quiet stretch splits one episode in two.
