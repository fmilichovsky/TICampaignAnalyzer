# How the current base levels, context rules, stakes and references were chosen

Research for #537 (part of the map #531). It answers one question: what reasoning set today's base levels, context
rules, stakes and references, where is that reasoning written down, and where is there none.

Vocabulary is [CONTEXT.md](../../CONTEXT.md)'s. Every claim names its source. Counts are from
`tinarrative benchmark calibrate report` at the code's references on the committed sample campaigns (Protectorate
and Resist; 27,361 events), run on 2026-11-17 at `0d7e85d`. This file lives on a research branch and is not meant
to be merged: it cites issues and counts, which [CONTRIBUTING.md](../../CONTRIBUTING.md) keeps out of the docs.

## Summary

- The levels were set in **three passes**, each with a different kind of reasoning: a per-type table with a written
  reason per group (#70, October), bare level literals in the specs of the narrative rules (#102, #163, #191 to
  #195), and stakes added on top with the level kept wherever possible (#196 to #200, #359, #360).
- The **written reasons of the first pass no longer exist in the tree.** They were comments in the `BASE` table of
  `narrative/significance.py` and were dropped when the table became kind declarations (#384 to #394, #413 to #415).
  They survive only in git history (`b290dbd:src/tinarrative/narrative/significance.py`).
- **Most references were never calibrated.** Power, population and organization started at 0.01 "to start" and
  stayed. Only hab, battle and faction were chosen against target scores.
- **37 atomic kinds have a base level nobody chose**: they were never named in the table, took its default
  (`minor`) and kept it when they became kinds.

## 1. Rules of thumb actually applied

### Levels

1. **Evidence ranks low.** An event that only feeds the rule that explains it is `trivial`: a statistic shift, a
   band crossing, a rank change, a per-capita GDP trend. Source: ADR-0011 ("Evidence events rank low"); #190
   ("the evidence other rules cite, not a development in itself"); #360 (the warhead shift became evidence so a
   token buildup by a great power does not inherit the power share of the shift it cites).
2. **Routine churn is trivial, routine movement is minor.** Recruit-pool councilors, organization churn, log
   pruning, refit dates and mirror lists are `trivial`; orbit, docking and army redeployment are `minor`. Source:
   #70 (measured: every one of 52 absent and 60 new councilors in an interval had no faction); the old table's
   comments.
3. **Unexplained residue stays minor, never trivial.** A leftover relation or membership list that no explaining
   event claimed stays visible. Source: ADR-0011; old table ("so the unexplained residue is never hidden;
   promoting one is reconstruction work").
4. **An unclassified type is minor.** Source: `Significance.MINOR`'s docstring ("the default for an unclassified
   type"); the old `DEFAULT`.
5. **One fact is not counted twice.** A record that corroborates an event, or an inferred aggregate of events
   that are already major, ranks below them: `control_point.loss_recorded`, `nation.territory_gained` and
   `_lost`. The same reasoning gives the maximum over cited events instead of a sum. Source: old table comments;
   ADR-0011 ("The maximum, never a sum").
6. **A precursor or a capability is minor; the outcome is the event.** Hostile claims, the nuclear program flag,
   policy flags, unrest attempts, a ledger charge. Source: old table comments; ADR-0010 for the ledger.
7. **Major is "what a history reports".** Changes of political control and asset ownership, wars and federations
   appearing and ending, redrawn borders, and the inferred readings of each. Source: #70's list; old table
   comments; `Significance.MAJOR`'s docstring.
8. **Campaign defining is for campaign-wide firsts, nuclear use, climate stages and the birth or end of a
   nation**, and it stays rare. Source: the comment kept in `kinds/campaign.py`; old table; PR #120 (a test that
   `campaign_defining` stays rare in the milestone list: 9 of 219 entries).
9. **Rarity raises a level.** Megafauna "are rare", first space defences "appear only late", a population drop
   beyond territory because "routine decline is far slower". The always-major band statistics (democracy,
   education, military tech) follow the same logic: after the margin filter their crossings fall to 0 or 1 per
   interval. Source: the context rules' docstrings in `significance.py`; #191.
10. **Cause goes in a context rule, size goes in a stake.** Source: #349 ("The nuked population collapse stays a
    named context rule. It judges the cause, not the size"); #359 kept the band-shift rules beside the new stake.
11. **A wrapper takes its level from what it cites.** `nation.release`, `nation.breakaway` and
    `nation.claims_declared` have a `trivial` base on purpose. Source: `kinds/nations.py` ("Trivial: the
    independence or claims change they cite sets their level"); PR #433.
12. **Curated tiers weigh reach, real-world weight and concreteness.** Source: `narrative/milestones.py`
    docstring; PR #120. This is the only place where each entry carries its own one-line rationale.
13. **Perspective is not impact.** The player's faction never moves a level. Source: ADR-0011.

### Stakes

14. **A stake only where impact grows with it; movement and churn never.** Source: ADR-0011.
15. **Shares, not magnitudes; shares add.** Source: ADR-0011; #197.
16. **A stake measures what the event moved, not only who acted.** Territory moved, the nation whose government
    fell, every belligerent. Source: ADR-0011. PR #433 applied it in reverse once: release and breakaway use the
    new nation's power share instead of the specified population share "so GDP and military power count too".
17. **A stake replaces a band-aid and should reproduce it at first.** The organization stake had to give the split
    the tier-3 rule gave (132 major, 201 minor on five Protectorate saves); stakes replaced the top-N GDP promotion
    and the large-arsenal threshold. Source: #198 and PR #314; #349; #360.
18. **When a stake is added, rebase so only a large instance reaches major.** `hab.destroyed`,
    `hab.faction_changed` and `faction.combat_recorded` went major to minor with their stakes;
    `organization.assigned_councilor_changed` was put at major to fall from there. Source: #200; PR #314.
19. **No stake where attribution is unsettled.** `faction.battle_outcome` is unscaled. Source: `TODO(#303)` in
    `kinds/space.py`; #200.

### References and scale

20. **Bases are band midpoints so that adding the score changed nothing.** 12, 37, 62, 87. Source: #196.
21. **A reference is the share that keeps the base level.** Ten points per tenfold share. Source: ADR-0011.
22. **A reference is chosen against target scores of named cases** where it was chosen at all: a tier-3 hab early
    reaches major, a tier-1 hab late is trivial, "a single battle never reaches campaign-defining", moving about
    16 warheads reaches campaign defining. Source: #200 (calibration targets); #360.
23. **A structural reference where one exists.** Faction is 1/7, an even split among the human factions. Source:
    `narrative/measures.py`.
24. **Settings change shares; the registry calibrates the scale.** No reference is a setting. Source: #447, #458.
25. **No threshold tuned to one campaign; every level-changing PR lists the changed events for a hand review.**
    Source: ADR-0011; #349 (user story 24); PRs #433, #444, #445.

### What drove the changes

26. **Crowding of the narrator package.** Nearly every re-tiering was triggered by a measured flood, not by a
    principle: 97 takeovers at major, 72 on nations with one to three control points (#166); 209 of 380 narrative
    events were takeovers and 59 % of the narrative characters (dev comment on #199); routine technologies ranked
    with fusion (PR #120); unrest crossings 74 to 14 after the rest-value filter (#191).

## 2. Choices made with no stated reason

| Choice | Value | What the sources say |
| --- | --- | --- |
| Score clamp | −20 / +15 | Introduced in #196 as numbers only. No source explains the asymmetry. Effect (inferred, not stated): a base can cross one band either way, never two. |
| Band edges | four bands of 25 points | #196 fixes them; nothing says why equal widths. |
| Slope | 10 points per tenfold share | ADR-0011 states it; no alternative was weighed. |
| Power, population, organization references | 0.01 | #198: "0.01 each to start, calibrated here". PR #314: "left at 0.01". The note in `nation-metrics.md` labels the reasoning a hypothesis. |
| Fleet and nuclear references | 0.01 | Same starting value. #360 only checks the consequence for nuclear. |
| Hab and battle references | 0.015, 0.0033 | Fitted to #200's targets. The combat data behind 0.0033 exists in one campaign only (Resist), which sits badly with rule 25. |
| Power weights | 1/3 each | #197 gives the values only. |
| `w_space` | 0.5 | #200 gives the value only. |
| `tier_exponent` | 2 | One line: "one tier 3 outweighs three tier 1". |
| `HAB_FLOOR`, `HAB_SATURATION`, `FLEET_SATURATION` | 25, 400, 1,000 kt | #200 gives the observed holdings (Σ tier² 2 to 259 in Protectorate, about 1,400 in Resist) but not how the values follow from them. |
| `ALIEN_MASS_WEIGHT`, `CONTEST_RATIO` | 2, 2 | Direction is reasoned (aliens outclass humans ton for ton; a fleet swatting a scout is a skirmish); the value 2 is not. |
| Bases of narrative kinds | mostly major | Written as bare literals in the rule specs: takeover and wave (#163), economic trajectory (#192), buildup, navy, space defences, ranking (#193), nuclear arcs (#195), space rules (#102). |
| `faction.fleet_buildup`, `nation.space_program_growth` at minor | minor | No reason found. |
| A councilor leaving with a faction is major, joining with one is minor | rule | #70 lists the first; the second is unstated. |
| `UPHEAVAL_CAUSES` | Coup, RegimeChange, Independence, Enthrall | #70 lists them; other causes are minor by omission. |
| Dropped nuclear bonus | none | Reasoned (#447: never fired on the samples, warheads already count in strength), but escalation risk now has no place at all. |

Two findings on the references that the PRs flagged and left open:

- **Rising a level on power takes about a 20 % share, which no nation holds** (largest 14 to 16 %). So a power
  stake only ever lowers. PR #433: no takeover is campaign defining any more. PR #444: the top economies dropped a
  level too, "against the issue's expectation"; "left for a separate decision".
- **The typical scaled atomic event is lowered** (median scale −8 to −13). `nation-metrics.md` records it and
  keeps 0.01 anyway.

## 3. Event types whose base level or missing stake looks unexamined

Counts are trivial / minor / major / campaign defining on the two sample campaigns.

**Never named, minor by default (37 kinds).** The ones with volume:

| Kind | Count | Note |
| --- | --- | --- |
| `organization.faction_orbit_changed` | 2,175 minor | Second most frequent type; its siblings `organization.appeared` and `.disappeared` are trivial. |
| `region.xenoforming_changed` | 430 minor | The other three alien region kinds are major. |
| `ship.appeared` / `.disappeared`, `fleet.appeared` / `.disappeared` | 151 / 52 / 71 / 43 minor | Presence, unscaled; `faction.fleet_buildup` scales the ships it cites. |
| `campaign.global_value_changed` | 94 minor | One level for every global value. |
| `hab.core_completed_changed`, `hab.tier_changed` | 87, 79 minor | A tier change moves a hab's own stake and is unscaled. |
| `army.strength_changed` | 80 minor | |
| `notification.*` | about 1,400 minor | By design ("never ranked", `significance.py`), but nobody checked the design against the types the saves hold. |

The rest: `control_point.nation_changed`, `.appeared`, `.disappeared`, `councilor.status_changed`,
`army.type_changed`, `.deployment_type_changed`, `.home_region_changed`, `nation.capital_changed`,
`nation.breakaway_parent_changed`, `fleet.parent_fleet_changed`, `fleet.in_combat_changed`, `hab.type_changed`,
`hab.in_combat_changed`, `hab.under_assault_changed`, `hab.under_bombardment_changed`,
`technology.finished_changed`, `war.attacker_changed`, `war.defender_changed`, `war.last_fighting_changed`, the
four `campaign.global_values_*` / `global_milestone_changed` kinds and the four notification queue kinds.

**Major with no stake, next to a scaled sibling.**

| Kind | Count | Sibling |
| --- | --- | --- |
| `hab.established` | 126 major | `hab.appeared` and `faction.first_hab_on_body` scale by hab share. |
| `hab.disappeared`, `faction.hab_destruction_recorded` | 21, 27 major | `hab.destroyed` was rebased to minor and scaled (2 / 19 / 0 / 0). The evidence now outranks the reading. |
| `faction.battle_outcome` | 21 major | `faction.combat_recorded` is scaled (0 / 5 / 1 / 0). Waits on #303. |
| `councilor.disappeared` with a faction | 37 major | `councilor.faction_changed` scales by the faction left. |
| `army.faction_changed` | 45 major | No army measure exists. |
| `federation.members_changed`, `.appeared`, `.disappeared`, `.renamed` | 46, 6, 3, 1 major | `federation.lifecycle` scales by members. |
| `war.appeared`, `.disappeared` | 6, 5 major | `war.arc` scales by its sides. |
| `campaign.narrative_event_triggered` | 88 major | "A once-per-campaign narrative event" each, but 88 of them at one level. |
| `councilor.detaining_faction_changed`, `nation.renamed`, `region.crashdown_changed`, `.alien_facility_changed` | 8, 4, 10, 5 major | |

**Narrative kinds with no stake.** `world.ranking_changed` (30, all major), `faction.space_campaign` (15, all
major), `nation.space_defences_established`, `nation.population_collapse` (a collapse in a micro-state is major),
`nation.space_program_growth` (waits on #361), `technology.milestone` and `campaign.first_milestone` (curated, by
design).

**Stakes that do nothing.**

- `nation.statistic_shifted`: trivial base with a nation stake (278 / 1 / 0 / 0). A leftover from when the warhead
  shift was major (#360).
- `nation.release`, `nation.breakaway`, `nation.claims_declared`: trivial base, so the stake cannot matter; all 5
  sample events get their level from what they cite (PR #433 says so).
- `nation.relation_changed`: the belligerents stake reads only `wars` relations; the samples hold none (654 minor).
- `councilor.faction_changed`: 27 events, a share was found for 6.

**Stakes that cannot move their kind.** With the references as they are, `war.arc`, `federation.lifecycle`,
`nation.cession`, `nation.expansion`, `faction.takeover_wave` and `faction.colonisation_wave` never fall below
major on the samples and reach campaign defining once each at most. `faction.takeover` is 59 minor and 211 major:
still the largest block of major narrative events. Only 20 events of 27,361 are campaign defining.

**Never seen in the samples (59 kinds)**, so no readout can judge them. Those with a high base:
`nation.appeared` and `nation.disappeared` (campaign defining, scaled), `campaign.nuclear_strikes_changed`,
`campaign.sea_level_rise_triggered`, `region.landing_changed`, `nation.federation_changed`,
`fleet.faction_changed`, `war.alliance_changed`, `army.destroyed_changed`, and the narrative kinds
`nation.population_collapse`, `nation.nuclear_buildup`, `nation.education_shift`, `nation.miltech_shift`,
`nation.breakaway`, `nation.space_defences_established`.

**Dev feedback not yet in the code.** #221: the first megafauna is major and the first alien landing is campaign
defining, each fading with repetition. Today every megafauna army is major, `region.landing_changed` is a flat
major, and nothing knows "first". #239 asks for significance per space body. #485 asks to try a base level before
editing it, which is the lever most of this section needs.

## 4. Open questions for the dev

1. **Should a stake be able to raise a level?** Today the power, population and organization stakes almost only
   lower. Is 0.01 a deliberate "only the top of the world keeps its level" or an uncalibrated start?
2. **Is the clamp's asymmetry (−20 / +15) intended**, and is "at most one level either way" the rule it encodes?
3. **What is campaign defining for?** 20 events in two campaigns. Is that the target, or should a great-power
   takeover or a world war reach it?
4. **Is `faction.takeover` at 211 major acceptable** given the wave, or is the base, the reference or the
   wave's member gate the lever?
5. **Should evidence ever outrank its reading?** `hab.disappeared` major against `hab.destroyed` minor.
6. **Does a kind with a scaled narrative reading need its own stake**, or should its base drop to minor so the
   reading decides (federation, war and hab evidence)?
7. **Are the 37 default-minor kinds minor on purpose?** In particular `organization.faction_orbit_changed`.
8. **Where should a kind's reason live?** The old table had a comment per group; kinds have none. A principles doc
   can state the rules of thumb, but the per-kind reason needs a home too (the kind, the catalog line, or nowhere).
9. **Is "first of its kind" a context rule, a stake or a narrative rule?** #221 needs an answer, and so does the
   repetition decay.
10. **Which measures may be fitted to one campaign?** Battle is fitted to Resist alone because only it has combat
    logs.
11. **Are the share-shaping constants in scope for the framework** (power weights, `w_space`, floors, saturations,
    alien weight)? The calibration dashboard put them out of scope because they need a re-extraction.
12. **How should a kind the samples never show be reviewed?** 59 kinds, including the two campaign-defining nation
    kinds.

## Sources

- [ADR-0011](../adr/0011-significance-is-judged-once-and-scaled-by-stake.md), [ADR-0010](../adr/0010-the-faction-ledger-is-bounded-corroboration.md).
- `src/tinarrative/narrative/measures.py`, `significance.py`, `milestones.py`, `prominence.py`;
  `src/tinarrative/analyzers/politics/bands.py`; `src/tinarrative/kinds/`; `src/tinarrative/config.py`.
- `b290dbd:src/tinarrative/narrative/significance.py` (the per-type table with its comments) and
  `94c1e7c^:docs/architecture.md` §12 (the design text before it became ADR-0011).
- [nation-metrics.md](../game-data-notes/nation-metrics.md) ("Scaled atomic events", "Scaled nation narrative
  events"), [space-assets.md](../game-data-notes/space-assets.md).
- Issues #70, #102, #130, #163, #166, #190 to #201, #221, #239, #303, #349 to #362, #446 to #449, #458 to #466,
  #485, #518 to #521. PRs #120, #202, #252, #306, #314, #433, #437, #444, #445, #468.
- The PR threads hold no tiering feedback from the dev beyond benchmark requests; the feedback found is in the
  issue bodies and comments cited above.
