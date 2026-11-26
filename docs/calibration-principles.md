# Calibration principles

How a base level, a scaling and the spread of levels in a narrator package are judged. What each level means to a
reader is in the [editorial direction](editorial-direction.md), the areas a history follows are the
[themes](../benchmarks/themes.toml), and how a share becomes a score is in
[ADR-0011](adr/0011-significance-is-judged-once-and-scaled-by-share.md). Terms are defined in
[CONTEXT.md](../CONTEXT.md).

Each principle has a name, so a proposal's reason and a kind's reason line can cite it.

## Base levels

- **The ordinary instance.** A base level is the level of the kind's ordinary instance: for a scaled kind the one
  whose share lies between its drop share and its rise share, for an unscaled kind the one seen most often. The
  scaling moves an event both ways from its base, so a base set at the largest or the smallest instance misjudges
  most of the others.
- **No compromise level.** When the instances of one kind belong to more than one level and nothing in the event
  separates them, no base level is right. A level in between misplaces both groups, and the higher group's level
  handed to the lower one is the weak entry the direction rules out. That is a scoring proposal or a structural
  finding, never a value.
- **Three sources of variation.** Instances of one kind differ by size, by cause and by novelty. Size belongs in
  the scaling and cause in a context rule. Novelty has no lever yet: a first outranks its repeats and the repeats
  fade, but a first is not campaign-defining by rule. Each source has its own judge because a base level bent to
  absorb one of them misplaces the ordinary instance.
- **Atomic kinds are judged alone.** The level meanings apply to an atomic kind as if its single transition were
  told by itself, so major means the lone transition is already an episode a reader would recall. An atomic event
  can reach the package with no reading above it, and a reading takes at least the level of what it cites, so the
  level has to be true without any help from context.
- **Evidence never outranks its reading.** Where a narrative kind reads an atomic kind and carries a scaling, the
  atomic kind sits below the reading's base. A narrative event scores at least as high as the highest event it
  cites, so evidence placed higher pins every reading at its own level and the reading's share decides nothing.
- **One judge per fact.** Either the reading has a base and a scaling and its evidence sits below it, or it is a
  wrapper with a trivial base and no scaling and the cited event decides. Never both: of two judges only the higher
  is ever heard, and the other is a declaration that looks live and is not.
- **No uncited major.** An atomic kind at major or above that no narrative rule cites is a finding. The history
  tells developments, so an episode worth recalling that no rule reads is either a missing rule or a level set too
  high.
- **Campaign-defining by consequence.** An event is campaign-defining when later developments cannot be understood
  without it. It is a base level only for what shakes the world whoever it happens to, such as the use of nuclear
  weapons. Everything else has to rise to it, by its share or by novelty, because the same kind of event defines
  one campaign and passes unnoticed in another. No count of campaign-defining events is a target.
- **Trivial is a role.** Evidence and churn are trivial; nothing is trivial for being small. A small instance of a
  real development is still detail on demand, and at trivial it would be lost among the evidence.

## Scalings

- **Both ways.** A share raises as readily as it lowers. A scaling on which no real entity can rise is a fault: it
  shows that the base is a ceiling and not the ordinary instance.
- **A share is a game quantity.** A rise share is stated as the smallest entity whose instance still deserves the
  level above the ordinary one, and a drop share as the largest whose instance deserves the level below. A bare
  fraction cannot be argued with; a named quantity can be checked against the game and holds in a campaign nobody
  has sampled. A named case illustrates a share and is never its reason.
- **A scaling belongs to the kind.** It does not belong to the measure, and two kinds share one only when the same
  reason holds for both. Kinds on one measure sit far apart, a sum of nations against a single nation, and two
  equal numbers may be a coincidence.
- **Share-shaping constants.** The weights, floors and saturations that turn holdings into a share define what a
  share means. They change only by scoring proposal, since moving one moves every share on its measure and
  restates every scaling that was reasoned in those shares.

## The spread of levels

- **No density.** No count or proportion of events at a level is right or wrong, so the test stays per event. A
  bound would be met by demoting whatever is at hand, and a quiet stretch and a crowded one would both be told
  wrongly.
- **Smells are triggers.** A calibration smell sends a reviewer to apply the per-event test to the events behind
  it. It is never the reason of a proposal and never a target, and a smell that clears is no measure of success.
  A smell describes a shape and not an event: the shape may be what happened, and its fix may be structural. The
  smells are:
  - **Flood**: one event type makes up most of a level in a period.
  - **Repeats**: the same type on the same concerns at major or above within a short span.
  - **Fragmentation**: several top-level events state one must-tell entry.
  - **Outranked entry**: a must-tell entry sits level with or below unlisted events on the same concerns.
  - **Flat scores**: a kind's instances all score alike, so the level cannot order them.
  - **Inverted pyramid**: a period holds more events at a level than at the level below.

  The thresholds that raise a smell are settings of the calibration report and not principles. They decide when a
  review looks and describe no healthy package.

## The rule against fitting

- **A reason of its own.** A proposal stands on game intuition, common sense or what people would find meaningful
  in the real world. "To fit a sample" is never a reason: the sample campaigns are few and alike, and a value fitted
  to them describes them and not the game.
- **Samples confirm or veto.** They show whether a reasoned change does what its reason says, and they can show it
  doing harm. They never motivate a value.
- **A misplaced event is a trigger.** A clearly misplaced event is examined for why it landed where it did. The
  change that follows is stated about the class of events, for the reason found, and checked on the other
  instances. A change that moves the one event leaves the rest of its class as wrong as before.
- **Fitting to the game's distribution.** A share may be fitted to how the game distributes a quantity: what
  nations start with, how far they move, how large mergers, fleets and habs get. These belong to the game and not
  to a campaign, so they are read across the samples played with standard settings.
- **Thin coverage is labelled.** A proposal that touches an event type or measure with thin coverage can still be
  made on its reason, and is marked unconfirmed by samples. The reason carries a proposal; the mark tells the dev
  that no sample could have vetoed it.

## Where a kind's reason is recorded

- **One reason line per kind.** Every kind declaration, atomic or narrative, carries one line naming the principle
  its base level applies, or the marker `unexamined`. The reason sits beside the value so the two change together,
  and the marker lets a review list what nobody has judged. The line holds the reason only.

## Changing this page

An agent may draft a change by pull request when a review needs a rule this page lacks; the dev approves it.
