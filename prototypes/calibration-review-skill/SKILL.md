---
name: calibration-review
description: Review base levels, scalings and the spread of the narrator package against the sample campaigns, from one seed (a theme, a calibration item, or a newly admitted sample). Use when the dev asks for a calibration review; not for ordinary scoring or code work.
---

<!-- PROTOTYPE v1 for https://github.com/fmilichovsky/TICampaignAnalyzer/issues/581, revised after the walkthrough
(walkthrough.md) on the theme "Blocs and unions". Throwaway; not the real skill. Commands marked (build) do not
exist yet. -->

# Calibration review

Judge whether the narrator package, for one **seed**, states what the editorial direction asks, and turn each
**smell** into a value proposal, a scoring proposal, a structural finding, or a reason to leave it alone. The dev
starts every review. Nothing merges and nothing is filed before the triage checkpoint.

Read first, every run, in this order: `docs/editorial-direction.md` (what each level means), then
`docs/calibration-principles.md` (how a level and a scaling are judged). `benchmarks/themes.toml`, ADR-0011 and
`CONTEXT.md` for lookup only.

## Seed and scope

Exactly one seed:

| Seed | Signs come from | Ends in |
|---|---|---|
| **Theme** | The theme's event types and its must-tell entries | Proposals and findings |
| **Calibration item** | The item's claim; its class is usually given | Proposals and findings |
| **Sample** | A newly admitted campaign against the others | A survey: themes and items to review next, each with its smell |

- The scope is **every reviewable campaign** (no `prefix_of` in `samples.json`). A campaign without a must-tell
  list still counts: it gives views and smells, and no verdicts.
- The seed bounds the **smells**, not the kinds. A smell inside the seed whose level is decided by a kind outside
  the theme's list (a cited atomic kind, a war arc holding the theme's outcome) is followed to that deciding kind.
- A smell outside the seed is noted on the review issue as examined and left alone, or commented on an existing
  item. Never chased.

## Steps

### 1. Open the review issue

Sub-issue of "Calibration reviews", label `calibration`: seed, campaigns, commit, `--state` hash of the code's
state, and a Touches line. Done when the issue exists; it is your claim.

### 2. Registry

```sh
python scripts/calibration_registry.py --theme <theme>     # (build)
```

Lists open and recently closed `calibration` items and open reviews whose Touches line overlaps. Done when every
item is either named on the review issue as related or ruled unrelated. An overlapping open review: stop and ask.

### 3. Headline views

```sh
tinarrative benchmark calibrate report --theme <theme> --view period,theme,tiers,must-tell,smells   # (build)
```

Read `smells` first; it lists every raised calibration smell with its numbers and threshold. Then `theme` and
`must-tell` for the verdicts, fragmentation and crowd. Done when every raised smell is copied to the review issue
as a row: smell, where, kinds involved.

### 4. Per smell, the core loop

1. **Read the events** behind it: `--view events --type <type> --theme <theme>` (build).
2. **Name the judge.** For each event, what decided its level: its own share, a context rule, or a cited event
   (the `decided by` column). A wrapper or a reading pinned by its evidence is judged at the deciding kind; a
   change to the visible kind's base would move nothing.
3. **Write why** they landed where they did, about the class of events.
4. **Classify**, against what the instances deserve under the direction's level meanings:
   - **Value proposal**: the deciding kind's measure orders the instances correctly; only a base level or a share
     sits wrong.
   - **Scoring proposal**: nothing the deciding kind reads tells the instances apart, or it reads the wrong
     quantity, or a context rule decides them.
   - **Structural finding**: what exists to be scored is wrong (a catalog line, a narrative rule, missing content).
   - **Left alone**: it fits the direction; write the reason.
5. **Try** a value question with `--base` or `--state`; for a scaled kind hand it to `kind-calibration` with the
   smell and the reason. A context-rule kind cannot be tried: that is a scoring proposal. A change the engine cannot
   express yet is recorded as **waiting on** its build issue, not tried around.
6. Record rejected tries on the review issue with their reasons.

Done when every smell row has a class, a deciding kind and a reason.

### 5. Triage checkpoint

Once, before anything is filed. A table: smell, deciding kind, class, proposed change, must-tell verdicts it would
change, and any of the three live questions it raises:

1. a thin theme: playstyle, or a fault?
2. a crowd event matching no entry: a blind spot of the list (`pending`), or noise to push down?
3. an episode stated by many events: acceptable as told, or a structural finding?

Only these three are asked; everything else in the table is the agent's call under this skill. Asked in chat when
the dev is present; otherwise posted on the review issue, and only what does not depend on an answer is filed.
Done when every live question has the dev's answer or is posted.

### 6. File

As settled in [Proposals: what each tier must show](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/541):
value proposals as PRs with the generated evidence block
(`calibrate report --state '<hash>' --format markdown`, build), scoring proposals as issues, findings one per
issue, comments on existing items. Link each from the review issue with what was examined and left alone.

## Stops

The agent never merges, edits `docs/editorial-direction.md`, turns a `pending` must-tell entry into `added`,
graduates a draft share or writes context-rule code without the dev's go, or changes
`docs/calibration-principles.md` except by draft PR. An unclear must-tell candidate is recorded as verdict
unsettled, and the review carries on.
