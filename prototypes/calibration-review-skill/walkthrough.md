# Walkthrough: `calibration-review` on the theme "Blocs and unions"

PROTOTYPE for [Prototype: a calibration review of one theme](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/581).
Throwaway. The draft skill is [SKILL.md](SKILL.md). The theme was walked by hand on `main` at `65a31c2`, across
`protectorate` and `resist-long`, up to the triage table. Nothing was filed.

Markers: **(hand)** means the agent computed something a report section should print. **(stall)** means the agent
could not go on with today's code. **(dev)** means the agent needed the dev.

The stand-in views are four scripts in [scratch/](scratch/) that read the cached calibration table
(`build/calibration/tables/*.js`, schema 3): `theme.py`, `smells.py`, `musttell.py` and `load.py`. Run them from
the repo root with `PYTHONPATH=prototypes/calibration-review-skill/scratch`.

## Step 1: the review issue

Not opened (nothing is filed here). **(stall)** The "Calibration reviews" parent does not exist yet. A Touches line
would read: types `federation.*`, `nation.merger`, `nation.expansion`, `nation.claims_declared`,
`nation.claims_changed`, `nation.release`, `nation.cession`, `nation.breakaway`; measure power; theme blocs-and-unions.

## Step 2: registry

**(stall)** There is no `scripts/calibration_registry.py`, and no item carries a Touches line yet. The agent read the
titles of the 6 open `calibration` items by hand. Related items: [Revisit scoring method of `war.arc`](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/488),
plus [Narrative events: arcs wider than one war or merger](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/573),
which is not labelled `calibration`. A search for "claims" and "federation lifecycle" found no open item.

## Step 3: headline views

None of these views exist yet.

- **Theme type list (hand).** There is no `benchmarks/themes.toml`, so the agent picked the types itself: the
  narrative kinds `federation.lifecycle`, `nation.merger`, `nation.expansion`, `nation.claims_declared`,
  `nation.release`, `nation.cession` and `nation.breakaway`, with their evidence (`federation.*`,
  `nation.unification`, `nation.independence`, `nation.claims_changed`). `war.arc` belongs to Wars, and
  `nation.diplomatic_realignment` to no theme chosen here. Both decisions are the dev's to approve.
- **Theme and tiers (hand).** Top-level means a narrative event that no other narrative event cites. The periods
  are interval years, not narrate's periods.

  | Kind | `protectorate` | `resist-long` | Base | Level decided by |
  |---|---|---|---|---|
  | `federation.lifecycle` | 16 major, all top-level | 20 major + 3 defining, all top-level | major | own power share, floored by its major evidence |
  | `nation.merger` | 18 major (13 members) | 33 major (27 members) | major | its `nation.unification` evidence; members of `nation.expansion` |
  | `nation.claims_declared` | 19 major | 74 major + 1 defining | trivial (wrapper) | cited `nation.claims_changed`, a context rule |
  | `nation.release` | none | 22 major | trivial (wrapper) | cited `nation.independence` |
  | `nation.breakaway` | 2 major | 9 major | trivial (wrapper) | cited `nation.independence` |
  | `nation.cession` | 12 major, all members | 24 major (17 members) | major | own share |

- **Smells (hand)**, at the thresholds of [Guard rails: numeric bounds from the must-tell lists](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/577):
  - Flood: `resist-long` 2043, where `nation.claims_declared` is 31 of 61 major events.
  - Repeats: `nation.claims_declared` raises it on 37 concerns. Grouped by every named nation rather than by the
    actor, so the USA alone counts 12 (hand: a role is needed). `nation.release`: Thailand ×8 in 2040-10, the EU ×5.
    `nation.breakaway`: USA ×5.
  - Flat scores: `nation.claims_declared` in `resist-long`, 10th to 90th percentile 59 to 63.
  - Inverted pyramid: raised in 9 of 12 periods of `protectorate` and 16 of 19 of `resist-long`, counted over
    every type. Not specific to the theme.
- **Must-tell (hand).** Only `resist-long` has a list, and it is the prose draft in
  `docs/game-data-notes/recollection/resist_must_tell_draft.md`, not TOML. The agent transcribed 12 entries in the
  theme with periods and concerns (`musttell.py`) and matched them by name in an event's entities or label within
  ±3 months. **(stall)** Without roles and the few-target cap, every crowd is swamped by
  `nation.diplomatic_realignment` events that list 30 to 80 partners. `protectorate` gives no verdicts.

## Step 4: the core loop

### A. Claims flood: `nation.claims_declared`

- **Events.** "Bavaria claimed regions of West Germany" (major 62), "Buryatia claimed regions of Eurasian Union",
  16 of these in 2038-10, then 30 more in 2043-03 (Cascadia, Lakota, New Afrika…). `protectorate` shows the same
  burst in 2035-06 (Bretagne, Catalonia, Wales, Padania…).
- **Judge.** The wrapper's base is trivial. Its level is its one cited `nation.claims_changed`, which the
  `claims_changed` context rule makes major for any human nation. 10 of 19 major claims in `protectorate`, and 29
  of 75 in `resist-long`, add a single region ("Bavaria claims list +1/-0: +[Munich]").
- **Why.** A nation the game has not released, which holds no regions, has its claim list redrawn whenever
  regions change hands. That is bookkeeping, not a declaration.
- **Class.** Scoring proposal on the `claims_changed` rule: the rule tells nothing apart. "England claims the
  Commonwealth" (entry 28) and "the Caliphate claims the Muslim world" (entry 16) need to stay major; Bavaria does
  not. `--base` cannot try it because the rule decides the level. Open for the scoring issue: can the save show
  reliably that a claimant holds no regions? (Unclear data is unused.)

### B. Federation evidence at major

- **Judge.** `federation.appeared`, `federation.disappeared` and `federation.members_changed` have a base of major
  and no rule. Every lifecycle cites them, so none can go below major. This is the case the principles name under
  "Evidence never outranks its reading".
- **Try.** `--base federation.appeared=minor,federation.disappeared=minor,federation.members_changed=minor`: 228
  evidence events go from major to minor, and **no lifecycle moves**, because each one's own power share keeps it at
  major.
- **Class.** Value proposal, clean. Only cited-only rows change.

### C. Small federations at major: `federation.lifecycle`

- **Events.** 8 of 16 (`protectorate`) and 16 of 23 (`resist-long`) read "members: no net change". Southern
  Africa (Lesotho + South Africa, share 0.0045), Syrian, Sudanese and Romanian federations all score major 62.
  Akhand Bharat (India + Pakistan, 0.15) scores major 74, and the grand EU federation (0.61) defining 77.
- **Why.** Summed member power orders them correctly. For a federation, unlike a war, the bloc's weight is the
  right quantity. But the shared power reference (0.01) puts the lower cut-off at a share of 0.00056, so no real
  federation falls below major.
- **Try (rejected).** `--base federation.lifecycle=minor` plus B: 32 move from major to minor and 3 from defining
  to major, and the package goes from 39 to 7. But Akhand Bharat falls to minor 49 (entry 13 worsens) and the grand
  federation to major 52. The clamp caps a rise at about +15 points.
- **Class.** Value proposal, **waiting on** the per-kind scaling engine ([Scaling per kind: cut-offs in place of
  the reference, the rate and the clamp](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/568)). Today's
  engine cannot express it: changing the shared reference would move every power kind. **(stall)**

### D. "No net change": the lifecycle's line

- A federation that formed and dissolved reads "members: no net change; [India, Pakistan] -> [India, Pakistan]
  (0 member changes)". In `protectorate`, Akhand Bharat even says "no net change … (2 member changes)".
  Formation and end are not stated.
- **Class.** Structural finding (catalog line). Entry 13's verdict stays unsettled: the event is there at major,
  but it does not say that Akhand Bharat formed.

### E. Fragmentation: Europe reunified (entry 9)

- **Judge (hand, from `cited`).** The outcome exists as one event, "European Union expanded over Albania, Austria,
  … (2027-02..2035-05)", major 69. But it is a **member cited by 12 `war.arc` events**. Each arc spans the whole
  window and carries the same "16 regions changed hands", at defining 75 to 76. The Caliphate's expansion is
  cited by 12 arcs the same way, and China's by 5.
- **Class.** Structural finding, and it is the case of
  [Narrative events: arcs wider than one war or merger](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/573):
  comment there with the shared-constituent mechanism. The deciding kind is `war.arc`, outside the theme, which
  is why SKILL.md says the seed bounds smells, not kinds. The wars are not demoted. Türkiye (entry 10) is buried
  under the same arcs.

### F. Releases around one episode: Thailand ×9 (entry 22)

- "Thailand released Aceh / Borneo / Sumatra / Indonesia…", 9 events in 2040-10, major 49 to 65, each pinned by
  its `nation.independence` (population share, base major).
- **Class.** Part of fragmentation question 3 for entry 22. The micro-states (Aceh at 50) are a value question on
  `nation.independence`'s drop share, and that waits on the engine too.

### Left alone

- `nation.merger` and `nation.cession`: mostly members of `nation.expansion`, their scores spread over 16 to 19
  points, and the top-level ones state outcomes.
- The theme is not thin in `protectorate`: the recollection's EU merger, Southern Cross, China–Taiwan and
  Caribbean Community are all present at major. So question 1 is not raised.
- Inverted pyramid: package-wide, outside the seed. The direction already expects a large move down. Noted only.

## Step 5: triage table

| # | Smell | Deciding kind | Class | Proposed change | Must-tell effect (`resist-long`) | Live question |
|---|---|---|---|---|---|---|
| A | Flood, repeats, flat scores: claims | `nation.claims_changed` (rule) | Scoring proposal | `claims_changed` tells a declaration apart from a redrawn list; new issue | 16 and 28 must keep their claim at major | — |
| B | Evidence at major under scaled readings | `federation.appeared` / `disappeared` / `members_changed` | Value proposal | Base major → minor (228 events, package unchanged) | none | — |
| C | Small federations at major | `federation.lifecycle` | Value, waiting on engine | Cut-offs on summed member power once the engine lands (#568 build) | 13 and 26 must hold | **Park or file?** |
| D | Lifecycle line "no net change" | catalog line | Structural finding | State formation and end; new issue | 13 unsettled | — |
| E | Fragmentation: 12 arcs share one expansion | `war.arc` | Structural finding | Comment on #573 (and #488) | 9 fragmented ×12, 10 buried | — |
| F | Repeats: Thailand ×9 releases | `nation.independence` | Q3, then value waiting on engine | — | 22 fragmented | **Q3** |
| G | Outranked entry 28: "Republic of New England claimed…" 62 over "England claimed…" 59 | as A | Noise, same class as A | Covered by A | 28 | **Q2** |
| H | Entry 21: India-Bangladesh merger 66 under two wars (73 to 74) and the Akhand Bharat lifecycle (73) | `war.arc`, `federation.lifecycle` | Q3 | — | 21 fragmented ×4 | **Q3** |

### The dev's answers (2026-11-23)

- **Q2, row G:** noise, the same class as A.
- **Q3, rows F and H:** structural, as cases of #573.
- **Row C:** the agent asked whether to park or file. That is no live question: the skill already settles it
  ("waiting on", recorded on the review issue). The checkpoint carries only the three live questions; a procedural
  question the agent raises there is a gap in the skill.
- Nothing from this walk is filed. The prototype tests the skill, not the theme.

## What the walk says about the skill

**It holds**: one seed, both campaigns, signs to classes, one checkpoint. Revisions folded into SKILL.md v1:

1. **Name the judge** is a step of its own. 4 of the theme's 7 narrative kinds take their level from what they
   cite. Without this step the obvious move, a lower base on `nation.claims_declared`, does nothing.
2. **The seed bounds smells, not kinds.** Entry 9's cause is `war.arc`, and the claims flood's cause is an atomic
   kind outside the theme.
3. **Waiting on** is a valid state for a value proposal the engine cannot express yet (C, F).
4. **A campaign without a list** gives views and smells, never verdicts.

**Missing report sections (hand computation)**, beyond those known from
[Prototype: kind-calibration run on the space program share](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/578):

- `decided by` for every event in the `events` view. Today it shows only in the cut-off rows.
- Fragmentation through a shared constituent: one member cited by many top-level events.
- The `smells` view filtered to the theme's types. Inverted pyramid and flood over every type are noise in a theme
  review.
- Repeats and crowd need roles: "same concerns" is the actor, or a target of a few-target event (schema 5).
- `moved` in the JSON readout has ids without labels. The agent joined them from the table.
- The theme type list, the TOML must-tell list for `resist-long` and the registry tool, as already planned.
