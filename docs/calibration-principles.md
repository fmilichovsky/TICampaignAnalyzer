# Calibration principles

How a base level, a scaling and the spread of levels in a narrator package are judged. What each level means to a
reader is in the [editorial direction](editorial-direction.md), the areas a history follows are the
[themes](../benchmarks/themes.toml), and how a share becomes a score is in
[ADR-0011](adr/0011-significance-is-judged-once-and-scaled-by-share.md). Terms are defined in
[CONTEXT.md](../CONTEXT.md).

A proposal's reason and a kind's or scaling's reason cite a principle by its name. A line marked _Avoid_ names the
fault the principle rules out. The comment beside each principle's name holds its identifier and revision, which the
code reads (`make docs`); see *Changing this page*.

This page holds the rules a calibration review judges by, not the steps of a review. A review ends in value
proposals, scoring proposals and structural findings. Where a principle's fault always calls for the same one,
the principle says so. Elsewhere the choice takes game knowledge and judgement, and a reviewer who cannot decide
raises the case to the dev instead of picking.

## Base levels

- **The ordinary instance.** <!-- principle the-ordinary-instance r1 -->
  A base level is the level of the kind's ordinary instance. Name the ordinary instance
  in game terms ("the takeover of a regional power") and judge it against the level meanings; that level is the
  base. The ordinary instance sits in the middle of what the kind involves, ranked by size: most takeovers are of
  small nations and should drop, a regional power sets the base, and the few largest rise. The shares of a kind's
  events in the samples may be looked at to see how its instances are spread (see *Fitting to the game's
  distribution*). For a scaled kind the rise and drop shares are then set around the ordinary instance, so that it
  lies between them. An unscaled kind's instances are meant to be alike, so any typical one is its ordinary
  instance; where they are not alike, *No compromise level* applies.\
  _Avoid_: a base set by the largest instance of the kind, by the smallest, by the most numerous, or by the
  midpoint of the share values, which the few largest instances decide.
- **No compromise level.** <!-- principle no-compromise-level r1 -->
  When the instances of one kind belong to different levels and nothing in the event
  tells them apart, no base level is right. The answer is a scoring proposal that gives the event something to
  tell them apart by, or a structural finding that the kind should be split. Until that lands the base stays
  where it is: the level is known to be broken and is left alone. Where what separates the instances is novelty,
  *Three sources of variation* says what to report.\
  _Avoid_: a level in between. It places both groups wrongly, and it puts events at a level whose meaning they do
  not fully meet.
- **Three sources of variation.** <!-- principle three-sources-of-variation r1 -->
  Instances of one kind differ by size, by cause and by novelty, and each has its
  own lever. Size is handled by the scaling. Cause is handled by a context rule. Novelty has no lever yet: a first
  occurrence should outrank its repeats, and the repeats should fade, but nothing can make them. Where a first
  occurrence deserves more than its repeats, for instance a must-tell list that names the first and gives the
  later ones less and less weight, that is reported as a structural finding waiting for the novelty lever. It
  changes no base level and no share.\
  _Avoid_: moving a base level to make up for size, cause or novelty, which misplaces the ordinary instance. A
  first occurrence is not campaign-defining just for being first.
- **Atomic kinds are judged alone.** <!-- principle atomic-kinds-are-judged-alone r1 -->
  An atomic kind's level is judged as if its single transition were told by
  itself, with no narrative event above it. Major then means that the lone transition is already an episode a
  reader would recall. An atomic event can reach the package uncited, and a narrative event takes at least the
  level of what it cites, so the atomic level has to be right without help from context.\
  _Avoid_: a high atomic level justified by the story the event usually belongs to. That story is the narrative
  kind's to score.
- **One judge per fact.** <!-- principle one-judge-per-fact r1 -->
  A narrative kind is a reading or a wrapper. A reading has a base and a scaling of its own
  and judges something its constituents do not, such as the combined share of several nations. A wrapper has a
  trivial base and no scaling: it retells the event it cites with something attached, such as a cause, and takes
  that event's level. A kind that is both is fixed one of two ways: stripping it to a wrapper is a value proposal;
  giving it a judgement of its own, a share its constituents do not have, is a scoring proposal.\
  _Avoid_: both at once. Only the higher of two judges is ever used, so the other declaration looks as if it
  matters and does not.
- **Evidence never outranks its reading.** <!-- principle evidence-never-outranks-its-reading r1 -->
  No constituent lands at a higher level than the reading that cites it
  reaches by its own base and share; the same level is fine. This holds for every constituent, observed or
  inferred. A reading scores at least as high as its highest constituent, so a constituent above it decides the
  reading's level, and the reading's own base and share decide nothing. To check a pair of kinds, take the events
  where one cites the other: the level the constituent reaches by its base and share is never above the level the
  reading reaches by its own. A wrapper is not an exception: it makes no judgement of its own, so there is nothing
  to outrank. Which side changes is a judgement. Most often the constituent's kind is too high and a value
  proposal lowers it; sometimes the reading is too low and a value proposal raises it; where the reading should be
  a wrapper, that is a structural finding.
- **Campaign-defining by consequence.** <!-- principle campaign-defining-by-consequence r1 -->
  An event is campaign-defining when later developments cannot be understood
  without it. It is a base level only for a kind that shakes the world whoever it happens to, such as the use of
  nuclear weapons. Every other kind has to rise to it, because the same kind of event defines one campaign and
  passes unnoticed in another.\
  _Avoid_: a campaign-defining base for a kind whose weight depends on who is involved. No number of
  campaign-defining events is a target.
- **Trivial is a role.** <!-- principle trivial-is-a-role r1 -->
  Trivial is for events that matter only as evidence for something above them, such as a
  statistic shift, and for kinds that are churn by nature, such as councilor traffic. A wrapper's trivial base is
  no judgement either: its level comes from what it cites. A small instance of a real development is not churn.
  It is still detail on demand, so it stays minor, and minor is how the history plays it down. Being cited by
  another event says nothing about a kind's level, and neither does whether the package lists it as evidence or
  as bookkeeping.\
  _Avoid_: trivial as the level for small things. A real development at trivial is lost among the evidence.

## Scalings

- **Both ways.** <!-- principle both-ways r1 -->
  A scaling raises an event as readily as it lowers one. Real entities exist on both sides of the
  ordinary instance, and the scaling has to reach them. The ends of the ladder are the exception. A share never
  drops an event below minor, so on a minor base nothing drops; the drop share still sets how wide the levels
  above are. On a campaign-defining base nothing can rise.\
  _Avoid_: a scaling on which nothing in the game can rise. It shows that the base is a ceiling and not the
  ordinary instance.
- **A share is a game quantity.** <!-- principle a-share-is-a-game-quantity r1 -->
  A rise share is stated as the smallest thing in the game whose instance still
  deserves the level above the ordinary one, for example "a nation the size of a great power". A drop share is
  stated as the largest whose instance deserves the level below. The fraction follows from that description: it
  is read from how the game distributes the quantity (see *Fitting to the game's distribution*). Nobody can say
  whether a bare fraction is right; anyone who knows the game can say whether "a great power" is, and the
  description still holds in a campaign that was never sampled. Every further cut-off a kind's events can reach is
  judged the same way: whatever in the game sits at it has to deserve the level that begins there. Further
  cut-offs follow from the distance between the rise and drop shares, so a wrong one is corrected through the
  drop share. One event of a sample campaign may be given as an example of the quantity; the share still has to
  be right for everything of that size.
- **A scaling belongs to the kind.** <!-- principle a-scaling-belongs-to-the-kind r1 -->
  Each kind's scaling is reasoned for that kind. Two kinds use the same scaling
  only when the same reason holds for both. Kinds on the same measure can still cover very different amounts of
  it: on nation power, a takeover covers one nation while a war covers every nation on both sides, so a share that
  is large for a takeover is small for a war.\
  _Avoid_: one scaling for every kind on a measure. Two scalings that happen to hold the same number are not
  thereby the same scaling.
- **Share-shaping constants.** <!-- principle share-shaping-constants r1 -->
  Some constants decide how a share is computed from the game's data: the weights
  that combine statistics into one measure, the floors that keep a share defined, the saturations, the extra weight
  of alien ships. They define what a share means. Changing one moves every share on its measure and invalidates
  every scaling reasoned in those shares, so it is a scoring proposal.\
  _Avoid_: changing one of them as part of a value proposal.

## The spread of levels

- **No density.** <!-- principle no-density r1 -->
  Each event is tested by itself against its level's meaning, as the
  [editorial direction](editorial-direction.md#no-density-at-any-level) says.\
  _Avoid_: any count or proportion of events at a level as a goal or a limit. It would be met by demoting or
  promoting whatever is at hand.
- **Smells are triggers.** <!-- principle smells-are-triggers r1 -->
  A calibration smell sends a reviewer to test the events behind it one by one. The shape
  it describes may be what really happened, and where it is a fault, the fix may be structural. The smells are:
  - **Flood**: one event type makes up most of a level in a period.
  - **Repeats**: the same type on the same concerns at major or above within a short span.
  - **Fragmentation**: several top-level events state one must-tell entry.
  - **Outranked entry**: a must-tell entry sits level with or below unlisted events on the same concerns.
  - **Flat scores**: a kind's instances all score alike, so the level cannot order them.
  - **Inverted pyramid**: a period holds more events at a level than at the level below.

  The thresholds that raise a smell are settings of the calibration report and not principles.\
  _Avoid_: a smell as the reason of a proposal, clearing smells as a goal, or a cleared smell as proof that a
  change worked.

## The rule against fitting

- **A reason of its own.** <!-- principle a-reason-of-its-own r1 -->
  A proposal stands on game intuition, common sense or what people would find meaningful
  in the real world. The sample campaigns are few and alike, so a value chosen to suit them describes them and not
  the game.\
  _Avoid_: "to fit a sample" as a reason, in any wording.
- **Samples confirm or veto.** <!-- principle samples-confirm-or-veto r1 -->
  The samples show whether a reasoned change does what its reason says, and whether
  it does harm elsewhere.\
  _Avoid_: choosing a value because of the level it gives particular events in the samples.
- **A misplaced event is a trigger.** <!-- principle a-misplaced-event-is-a-trigger r1 -->
  A clearly misplaced event is examined for why it landed where it did. An
  event is misplaced when it does not meet its level's meaning, when it meets a higher level's meaning in full, or
  when the events that state a must-tell entry all sit below the level the entry names. A must-tell list has blind
  spots: it is written from one player's view, so an event that deserves more than it got is misplaced whether or
  not a list names it. The change that follows is stated about the whole class of such events, for the reason
  found, and checked on the other instances of the class.\
  _Avoid_: a change that moves only that event. The rest of its class stays as wrong as before.
- **Fitting to the game's distribution.** <!-- principle fitting-to-the-games-distribution r1 -->
  A share may be fitted to how the game distributes a quantity: what
  nations start with, how far they move, how large mergers, fleets and habs get. This is the one permitted kind of
  fitting, because these belong to the game and not to a campaign: they would come out much the same whoever
  played. Reading how a quantity is spread is allowed, including the shares of a kind's events; the value chosen
  from it still answers to *Samples confirm or veto*. Distributions are read across the samples played with
  standard settings.
- **Thin coverage is labelled.** <!-- principle thin-coverage-is-labelled r1 -->
  A proposal that touches an event type or measure with thin coverage can still be
  made on its reason, and is marked unconfirmed by samples. The mark tells the dev that no sample could have
  vetoed it.\
  _Avoid_: holding a reasoned proposal back for thin coverage, or presenting it as confirmed.

## Where a kind's reason is recorded

- **One reason per kind and scaling.** <!-- principle one-reason-per-kind-and-scaling r1 -->
  Every kind declaration, atomic or narrative, carries the reason for its base level, and every scaling the reason
  for its shares, or the marker `unexamined`. A reason names one principle and says, in game terms, what applies
  it: under *The ordinary instance*, the instance ("the takeover of a regional power"); under *No compromise level*,
  the groups it cannot tell apart and what would tell them apart; under *A share is a game quantity*, the game
  quantity the shares stand for. It records the principle's revision it was judged under. The reason sits beside
  the value so the two change together. `unexamined` is a starting state, and so is _stale_: a reason judged under
  an earlier revision of its principle, listed for review like an unexamined one. Neither is a fault.\
  _Avoid_: restating the principle or the level ("Trivial is a role: trivial, as churn"), and issue numbers, counts
  or sample events in the reason.

## Changing this page

An agent may draft a change by pull request when a review needs a rule this page lacks; the dev approves it.

Each principle carries a marker beside its name: `<!-- principle <identifier> r<revision> -->`. Raise a principle's
revision when a reason judged under the old text could now be wrong; a clarification that changes no verdict keeps
it. The identifier never changes while the principle exists. `make docs` regenerates the code's principles from the
markers and prints the kinds and scalings a raised revision made stale; a pull request that changes this page gets
the same list as a comment. Removing a principle means re-pointing every reason that cites it, or returning it to
`unexamined`, in the same change.
