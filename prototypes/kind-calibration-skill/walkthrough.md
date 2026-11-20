# Walkthrough: `kind-calibration` on the space program share (PROTOTYPE, throwaway)

For [Prototype: kind-calibration run on the space program share](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/578).
The draft skill is [SKILL.md](SKILL.md). Walked by hand on 2026-11-20 at `a164df0` plus this branch's draft share,
on `protectorate` and `resist-long` (`protectorate-short` is a leading slice, so the table leaves it out). Nothing was
filed.

Each friction point is marked:

- **HAND**: the agent computes by hand, so a report section is missing;
- **STALL**: the skill gives no next move;
- **DEV**: only the dev can answer;
- **SHAPE**: the skill's own shape is wrong.

## Entry: `calibration-review` with the registry-item seed

| Review step | What happened | Mark |
|---|---|---|
| 1. Open the review issue | Skipped (prototype). It would name the seed [Entity significance: space program share](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/361), the commit and `#types=nation.space_program_growth` | |
| 2. Read the direction and principles | Neither `docs/editorial-direction.md` nor `docs/calibration-principles.md` exists yet. Read the resolutions of the editorial stance and principles tickets instead | expected, build piece |
| 3. Registry tool | `scripts/calibration_registry.py` does not exist. Ran `gh issue list --label calibration` by hand. The seed item has no Touches line, since it predates the convention | HAND, expected |
| 4. Scope: sample profiles and coverage | No profiles. Counted by hand: 47 instances in `protectorate`, 121 in `resist-long`. Coverage is not thin | HAND |
| 5. Report views | `period`, `theme`, `must-tell` and `tiers` are not built. Only `--type nation.space_program_growth` works: 139 minor and 29 major, with no instances listed | HAND, expected |
| 6. Per sign | **A registry seed has no sign.** The item itself makes the claim: "growth by a leading space power outranks growth by a minor one, and the top-N rule is a band-aid". It also arrives already classified as a scoring proposal, so steps 6.2 to 6.4 have nothing to do | SHAPE |

Hand-off: kind = `nation.space_program_growth`. Sign = the seed item's claim plus one must-tell match: `resist` entry 5,
"China becomes a space power", is minor 37 today, found in the recollection draft by eye (HAND: no `must-tell`
view). Reason, written before any try: *A nation's launch capacity growing is connective material; it is an episode
only when the nation is, or becomes, one of the powers that dominate access to space.*

## `kind-calibration`

### 1. The ordinary instance

`calibrate report` has no instance list, so I parsed `build/calibration/tables/*.js` with a script. **HAND**: the
`events` view.

168 instances. A typical one is a mid-size nation adding tens of dekatons of boost or a few mission control, such as
Poland's boost going 20.9 to 38.5 in `protectorate` 2029-12, or Taiwan's going 46.9 to 83.5 in `resist` 2033-01.

### 2. Base level and reason line

Minor fits the ordinary instance. Kinds have no `reason=` field yet (build piece). Candidate line: *Base: the ordinary
instance (a mid-size nation adding launch capacity) is connective material.*

**SHAPE**: for a scaled kind, step 2 depends on step 3. The principles define the ordinary instance of a scaled kind
as the one between its rise and drop shares, so the base cannot be judged before the scaling exists. Choosing the
measure has to come first.

### 3. Scaling

The kind has no share, and nothing it reads orders the instances, so this is a scoring question (as the item already
said). I followed the skill's "draft share" branch on this branch. It took 48 lines in 4 files:

- `Measure.BOOST` and `Measure.MISSION_CONTROL`;
- `MeasureSpec` entries, both at 0.01 (unexamined);
- `SaveShares` fields and a share function summing region fields per nation;
- `DraftShare("space-program", issue=361, readings=(boost, mission control of the actor))`.

The rebuild took 84 s. The golden calibration table test fails, as expected; the add-draft PR runs
`pytest --update-goldens`, and the skill does not say so (STALL for an agent that runs `make check`).

What the draft readout gives:

- level counts, 136 minor and 32 major at its own base;
- 29 rows **ruled** (`entered_top` decides);
- the 5 rows nearest each cut-off, as **ids only** (`draft:space-program:…/nation:3965@…`).

**HAND**: names, the full list and the share percentiles, all joined from the table JSON by script. These are the
`distribution` and `events` views, plus draft rows having no label.

The top of the sorted list, at reference 0.01 (rise at 0.178):

| Share (max) | Campaign | Interval | Event | Draft level | Today |
|---|---|---|---|---|---|
| 0.211 boost | resist | 2029-08 | USA: boost unchanged, mission control 7 → 10 | major | minor |
| 0.179 boost | resist | 2027-12 | **China**: boost 67 → 125, mission control 4 → 52 | major | minor |
| 0.178 boost | prot | 2028-09 | USA: boost unchanged, mission control 7 → 28 | major | minor |
| 0.139 mc | resist | 2045-08 | Caliphate: boost 1,198 → 1,557 | minor 48 | minor |
| 0.087 mc | resist | 2027-12 | **EU**: boost 24 → 258, mission control 4 → 30 | minor 46 | minor |
| 0.075 boost | resist | 2040-10 | Singapore: boost 0 → 562 (territory) | major 71, ruled | major |

Three problems no number fixes; each is **DEV**:

1. **Held or moved?** The draft reads the share the nation **held** before the interval. That is the default of
   every reading today, the same as a takeover's power. So the USA's three mission control points are major and the
   EU's tenfold boost is minor. The seed item says "the nation's share of world boost"; it does not say held, after
   or grown.
2. **"Among the measures that moved."** The item takes the higher share among the measures that moved. A
   `DraftShare` takes the max over every reading, so the USA's unchanged boost share wins. Expressible with a custom
   selector, but the agent writes it as code, and the skill does not say that this is allowed in an add-draft PR.
3. **Territorial growth.** Singapore, Borneo, Brunei and Indonesia going from 0 to hundreds of boost in 2040-10 is
   the Pan-Asian Combine absorbing regions, not a space program. `boost_territory_share` is on the event, but no
   reading can use it to discount the share. Scoring or structural?

**STALL: the item's change cannot be tried.** The item replaces the `entered_top` rule with the share. The
calibration state can switch a base level but cannot switch a rule off, so the 29 ruled rows start at major and
rise further: at reference 0.004, one goes campaign-defining; at 0.002, nine do. The skill cannot show what the
proposal itself would do. [Proposals: what each tier must show](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/541)
gives context rules no draft mechanism. This is a draft share that *retires* a rule, a third case the decisions do
not cover.

**HAND**: the tooling speaks references; the skill speaks rise shares. Translating ×17.8 by hand goes away with
the engine change.

The rise share as a game quantity, provisional: *the smallest nation whose growth is an episode holds about 7% of
world boost or mission control*. China 2027 qualifies; the EU 2027 qualifies only on a share after growth. This
waits on problem 1.

### 4. Every instance, every campaign

Not reached honestly. With 168 instances, reading each one costs about as much as all the steps before it. And
until held-or-moved is settled, every verdict would be redone. The must-tell check (China 2027-12: minor → major at
0.01) was matched by eye (**HAND**).

**SHAPE**: "every instance read" is the wrong bar at this size. The step should read the movers, the instances
nearest each share, and every must-tell candidate. Everything else is a count.

### 5. The proposal

The item already exists, so "draft the scoring-proposal issue" has nothing to do (**SHAPE**). The real outcome:

- a comment on [Entity significance: space program share](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/361)
  with the reason, the three DEV questions and the draft's numbers;
- the add-draft PR, which needs no go;
- a stop. Graduation needs the dev's go, and the go needs the three answers.

No evidence block is possible: the markdown output is not built.

## What the walk says about the skill

1. **Entry needs a third branch: an existing proposal issue.** A registry seed hands over a claim, not a sign, and
   often an item already classified. The review's per-sign loop and the skill's "draft the issue" step both assume
   a fresh sign.
2. **Reorder the steps for scaled kinds**: instances and what separates them, then the measure, then the base level
   and the rise and drop shares together, then the check, then the proposal.
3. **The scoring branch ends in a question to the dev, usually before any number.** Held, moved or after is a
   question of what the share *means*. The skill should make "what quantity, exactly" the first output of a scoring
   question, before any draft.
4. **A draft share is code, and the skill should own that**: the measure, the share function, a custom selector,
   golden updates. It is allowed without a go because no real score changes.
5. **Missing tooling, in the order it hurt**:
   1. instance list with names (`events` view), including for draft rows;
   2. share distribution per measure for a draft;
   3. switching a context rule off in the calibration state;
   4. must-tell matching;
   5. the evidence block;
   6. the registry tool.

   Items 1, 2, 4, 5 and 6 are already build pieces. Item 3 is new.
6. **Smell note, for the theme prototype**: this kind has only two scores, 37 and 62, yet flat scores would not be
   raised, because 10th to 90th percentile spans 25 points. A kind whose level is all rule and no share slips
   through.

## Settled with the dev (2026-11-20)

- **No rule switch; drafts for straightforward candidates only.** First settled as a new build piece (a context-rule
  switch in the calibration state), then withdrawn the same day. #361 was a poor test case for drafts because it
  already carried design questions. A change that retires or reshapes a context rule, or whose quantity is still
  open, is implemented in full on the dev's go and calibrated after it lands. Item 3 of the missing tooling above
  is dropped.
- **Steps reordered** as in point 2 above, with step 4 reading the movers, the events nearest each share and the
  must-tell candidates. [SKILL.md](SKILL.md) is now v2.
- **An existing item gets a comment and the add-draft PR**, never a new issue, then a stop for the dev.
- **Held or moved is #361's own question**, recorded there with the other two. This ticket takes only the lesson: a
  scoring question writes down what quantity, exactly, before any number.
