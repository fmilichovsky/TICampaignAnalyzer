# Shares per kind on each stake measure

Research for [Shares per kind on each stake measure](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/567),
part of [Map: agent calibration framework for event kinds and significance](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/531).
It answers one question: on the sample campaigns, how are the shares spread for each scaled event kind, and which
kinds that share a stake measure sit in different places on it. It feeds
[Scaling per kind: cut-offs in place of the reference, the rate and the clamp](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/568).
Facts only: it proposes no cut-off and no engine design.

Vocabulary is [CONTEXT.md](../../CONTEXT.md)'s. This file lives on a research branch and is not meant to be merged:
it cites issues and counts, which [CONTRIBUTING.md](../../CONTRIBUTING.md) keeps out of the docs.

## Where the numbers come from

- Taken on 2026-11-18 at commit `d7c4e6e`, at the code's references, base levels and clamp (no `--reference`, no
  `--base`).
- The calibration table was built with `tinarrative benchmark calibrate report --format json` (extracted
  2026-11-18T13:47:11Z, schema 3). The report's JSON holds level counts and the events nearest each cut-off, not
  every event's share, so the shares were read from the cached table itself (`tables/<campaign>.js`: one row per
  event with its base, its measure and share, its score and its level) with a throwaway script that is not
  committed.
- The table holds two sample campaigns. `protectorate-short` is a leading slice of `protectorate` and the extraction
  skips it.

| Sample campaign | Saves | Events | Not narrative | Narrative | Events of scaled kinds | With a share |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `protectorate` | 25, 2026-02-13 to 2035-06-16 | 34,561 | 33,475 | 1,086 | 6,694 | 5,708 |
| `resist-long` | 63, 2026-08-01 to 2046-10-08 | 70,491 | 68,650 | 1,841 | 13,648 | 10,716 |

- 49 kinds declare a stake: 26 narrative kinds and 23 others. No draft stake is declared.
- The largest share one entity holds (section 5) is not in the table. A second throwaway script loaded every save
  of each sample campaign and read the shares as the significance pass does (`Stakes.shares`), so it is known at the
  25 and 63 saves and not between them.
- Percentiles are nearest rank: the smallest share with at least that percentage of the kind's events at or below
  it. Every percentile is therefore the share of a real event. Shares are fractions of 1 to three significant
  digits; one below 0.0001 is written with an exponent, as 4.26e-05.
- Everything is per sample campaign. Nothing is pooled across the two.

### What today's scaling means in shares

Read from `narrative/measures.py`, `narrative/significance.py` and `model/events.py`:

- A level's base is its band's midpoint: 12, 37, 62 and 87. The stake adds `round(10 × log10(share ÷ reference))`
  points, clamped to −20 and +15.
- From a midpoint, 13 points cross a band edge. So every kind on a measure, whatever its base level, rises a level at
  a share of the reference × 17.8 and falls a level at the reference ÷ 17.8. Between the two lies a factor of 316,
  which is 2.5 tenfolds: the width of one level.
- The two cut-offs per measure are in section 5. On nation power, population, organization, fleet and nuclear share
  (reference 0.01) they are 0.000562 and 0.178.

## Summary

The findings that matter most for the engine decision:

1. **The shared reference lowers and almost never raises.** In `protectorate` the stake lowers 1,584 events and
   raises 5, of 5,708 with a share. In `resist-long` it lowers 3,272 and raises 74, of 10,716. 57 of those 74 are two
   kinds: `faction.combat_recorded` (30) and `war.arc` (27).
2. **On nation power the reference sits 7 to 14 times above the median nation, and the rise cut-off above the
   largest one.** The median nation holds 0.0011 to 0.0014 in `protectorate` and 0.0007 to 0.0013 in `resist-long`,
   against a reference of 0.01. The largest nation holds 0.131 to 0.161 in `protectorate`, so in none of its 25 saves
   could a kind that takes one nation rise. In `resist-long` a nation holds 0.178 or more in 20 of 63 saves, all from
   2039 on. Of the events on the `nation` stake, 426 of 1,842 and 739 of 2,865 sit at or below the fall cut-off and 0
   and 4 at or above the rise cut-off.
3. **A stake that sums nations is a different population from a stake of one nation, as expected.** The median
   `war.arc` share is 0.112 and 0.141, which is 64 and 74 times its siblings' median. No war arc lies below the
   reference, so none can fall, and its median is within a factor of 1.6 of the rise cut-off: 1 of 11 arcs and 27 of
   64 rise to campaign defining. `federation.lifecycle` is 5 and 45 times its siblings, `faction.takeover_wave` 16
   and 11 times.
4. **Kinds differ in width as much as in position.** The one-nation kinds with over 300 events in each campaign span
   3.0 to 4.2 tenfolds from their smallest to their largest share and 1.4 to 2.1 between their 10th and 90th
   percentile, against 2.5 for a level. `war.arc` spans 1.0 and 1.5 tenfolds, `organization.assigned_councilor_changed`
   1.4 and 1.5, `hab.destroyed` 1.0 and 1.1. One rate serves both.
5. **On organization and faction nothing can rise today, and on population and hab almost nothing.** The largest
   organization holds 0.0083, below the reference itself, so the organization stake only lowers (714 of 1,616 and
   1,808 of 3,836 events). The faction rise cut-off is 2.54, more than a whole share. The largest region holds 0.0318
   of population against a rise cut-off of 0.178, so only a sum of regions can rise, and one event does, in
   `resist-long`. A human-held hab never passes 0.068 against 0.267; the three hab events that rise are the alien
   faction's, in 2026 and 2027.
6. **Several stakes move nothing.** `nation.relation_changed` has no share on any of its 3,764 events. The three
   trivial wrappers (`nation.release`, `nation.breakaway`, `nation.claims_declared`) take their level from a cited
   event on all 127 events. `nation.statistic_shifted` rises on 3 of 1,202. `councilor.faction_changed` finds a share
   on 17 of 79 events and moves none. Five scaled kinds have no event.
7. **The clamp changes no level.** `calibrate report --clamp off` moves 0 events. 113 and 278 events sit at the clamp;
   only their scores are held.
8. **The two campaigns agree where a kind takes one nation and has volume, and not elsewhere.** The medians of the
   eight one-nation kinds with over 70 events in each campaign differ by a factor of 1.3 at most between the
   campaigns. `federation.lifecycle` differs by 9.9, `faction.combat_recorded` by 5.8, `faction.first_hab_on_body` by
   4.2.
9. **Coverage.** Four kinds are thin and five are not shown. No measure is thin by the rule, but `protectorate`
   shows 6 fleet, 17 battle, 7 faction and 2 nuclear events with a share, all 30 raised combats are in `resist-long`,
   and everything after June 2035 is `resist-long` alone.

## 1. Shares per kind

One row per scaled kind and sample campaign: its stake, its base level, its events, the events for which no share
was found, and the percentiles of the share. A row with 0 events is a kind the campaign does not show.

| Kind | Stake | Base | Campaign | Events | No share | Min | P10 | P25 | P50 | P75 | P90 | Max |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Nation power** (`power`, reference 0.01) | | | | | | | | | | | | |
| `nation.cohesion_shift` | `actor` | minor | protectorate | 73 | 0 | 4.26e-05 | 0.00022 | 0.000496 | 0.00101 | 0.00252 | 0.00741 | 0.16 |
| `nation.cohesion_shift` | `actor` | minor | resist-long | 92 | 0 | 5.45e-05 | 0.000204 | 0.000363 | 0.000821 | 0.00181 | 0.00467 | 0.021 |
| `nation.demobilization` | `actor` | major | protectorate | 1 | 0 | 0.0765 | 0.0765 | 0.0765 | 0.0765 | 0.0765 | 0.0765 | 0.0765 |
| `nation.demobilization` | `actor` | major | resist-long | 3 | 0 | 0.0767 | 0.0767 | 0.0767 | 0.113 | 0.115 | 0.115 | 0.115 |
| `nation.diplomatic_realignment` | `actor` | major | protectorate | 104 | 0 | 2.82e-05 | 0.000386 | 0.00065 | 0.00178 | 0.00722 | 0.0196 | 0.136 |
| `nation.diplomatic_realignment` | `actor` | major | resist-long | 202 | 0 | 5.07e-05 | 0.000293 | 0.000515 | 0.00191 | 0.00822 | 0.0211 | 0.259 |
| `nation.economic_trajectory` | `actor` | major | protectorate | 4 | 0 | 0.000294 | 0.000294 | 0.000294 | 0.000761 | 0.000837 | 0.0195 | 0.0195 |
| `nation.economic_trajectory` | `actor` | major | resist-long | 20 | 0 | 4.47e-05 | 0.000224 | 0.000394 | 0.000681 | 0.00972 | 0.136 | 0.259 |
| `nation.education_shift` | `actor` | minor | protectorate | 0 | | | | | | | | |
| `nation.education_shift` | `actor` | minor | resist-long | 0 | | | | | | | | |
| `nation.government_shift` | `actor` | minor | protectorate | 15 | 0 | 3.93e-05 | 4.00e-05 | 0.000191 | 0.00124 | 0.00439 | 0.12 | 0.161 |
| `nation.government_shift` | `actor` | minor | resist-long | 15 | 0 | 5.04e-05 | 5.45e-05 | 0.000202 | 0.000551 | 0.00156 | 0.00292 | 0.01 |
| `nation.inequality_shift` | `actor` | minor | protectorate | 9 | 0 | 0.000386 | 0.000386 | 0.00174 | 0.00235 | 0.0107 | 0.0725 | 0.0725 |
| `nation.inequality_shift` | `actor` | minor | resist-long | 14 | 0 | 0.000195 | 0.0002 | 0.00031 | 0.000638 | 0.0367 | 0.0768 | 0.111 |
| `nation.military_buildup` | `actor` | major | protectorate | 1 | 0 | 0.0348 | 0.0348 | 0.0348 | 0.0348 | 0.0348 | 0.0348 | 0.0348 |
| `nation.military_buildup` | `actor` | major | resist-long | 3 | 0 | 0.0119 | 0.0119 | 0.0119 | 0.0701 | 0.122 | 0.122 | 0.122 |
| `nation.miltech_shift` | `actor` | minor | protectorate | 2 | 0 | 0.000285 | 0.000285 | 0.000285 | 0.000285 | 0.000472 | 0.000472 | 0.000472 |
| `nation.miltech_shift` | `actor` | minor | resist-long | 8 | 0 | 5.04e-05 | 5.04e-05 | 0.000105 | 0.000307 | 0.00049 | 0.0399 | 0.0399 |
| `nation.navy_established` | `actor` | major | protectorate | 4 | 0 | 0.00646 | 0.00646 | 0.00646 | 0.0105 | 0.0183 | 0.0348 | 0.0348 |
| `nation.navy_established` | `actor` | major | resist-long | 6 | 0 | 0.00998 | 0.00998 | 0.012 | 0.0122 | 0.0184 | 0.0399 | 0.0399 |
| `nation.unrest_shift` | `actor` | minor | protectorate | 108 | 0 | 3.89e-05 | 0.000269 | 0.000437 | 0.00142 | 0.00898 | 0.022 | 0.16 |
| `nation.unrest_shift` | `actor` | minor | resist-long | 99 | 0 | 3.82e-05 | 0.000247 | 0.000563 | 0.00152 | 0.00615 | 0.0201 | 0.158 |
| `nation.relation_changed` | `belligerents` | minor | protectorate | 950 | 950 | – | – | – | – | – | – | – |
| `nation.relation_changed` | `belligerents` | minor | resist-long | 2814 | 2814 | – | – | – | – | – | – | – |
| `control_point.controller_changed` | `control_point` | major | protectorate | 936 | 0 | 2.73e-05 | 0.000225 | 0.000432 | 0.000798 | 0.00246 | 0.00553 | 0.0348 |
| `control_point.controller_changed` | `control_point` | major | resist-long | 1062 | 0 | 2.93e-05 | 0.000181 | 0.000371 | 0.000769 | 0.00246 | 0.00649 | 0.0266 |
| `nation.breakaway` | `independent_nation` | trivial | protectorate | 1 | 0 | 0.00646 | 0.00646 | 0.00646 | 0.00646 | 0.00646 | 0.00646 | 0.00646 |
| `nation.breakaway` | `independent_nation` | trivial | resist-long | 9 | 0 | 0.00161 | 0.00161 | 0.00376 | 0.0159 | 0.0368 | 0.185 | 0.185 |
| `nation.release` | `independent_nation` | trivial | protectorate | 0 | | | | | | | | |
| `nation.release` | `independent_nation` | trivial | resist-long | 23 | 0 | 0.000449 | 0.000614 | 0.00123 | 0.00228 | 0.00462 | 0.00949 | 0.0199 |
| `federation.lifecycle` | `members` | major | protectorate | 12 | 0 | 0.00114 | 0.00185 | 0.00206 | 0.00874 | 0.0985 | 0.16 | 0.163 |
| `federation.lifecycle` | `members` | major | resist-long | 23 | 0 | 0.00452 | 0.00898 | 0.0124 | 0.0866 | 0.131 | 0.183 | 0.611 |
| `faction.nation_control_changed` | `nation` | major | protectorate | 1121 | 0 | 2.84e-05 | 0.000309 | 0.000577 | 0.00155 | 0.00541 | 0.014 | 0.159 |
| `faction.nation_control_changed` | `nation` | major | resist-long | 1613 | 0 | 3.22e-05 | 0.000251 | 0.000491 | 0.00132 | 0.00403 | 0.0138 | 0.16 |
| `nation.appeared` | `nation` | campaign_defining | protectorate | 0 | | | | | | | | |
| `nation.appeared` | `nation` | campaign_defining | resist-long | 0 | | | | | | | | |
| `nation.claims_changed` | `nation` | minor | protectorate | 19 | 12 | 0.000169 | 0.000169 | 0.00122 | 0.00433 | 0.00469 | 0.00646 | 0.00646 |
| `nation.claims_changed` | `nation` | minor | resist-long | 79 | 57 | 0.00012 | 0.000273 | 0.00205 | 0.00538 | 0.0359 | 0.123 | 0.185 |
| `nation.disappeared` | `nation` | campaign_defining | protectorate | 0 | | | | | | | | |
| `nation.disappeared` | `nation` | campaign_defining | resist-long | 0 | | | | | | | | |
| `nation.executive_change_recorded` | `nation` | minor | protectorate | 331 | 0 | 4.32e-05 | 0.000301 | 0.00057 | 0.00163 | 0.00541 | 0.014 | 0.159 |
| `nation.executive_change_recorded` | `nation` | minor | resist-long | 411 | 0 | 3.22e-05 | 0.0002 | 0.000449 | 0.00126 | 0.00423 | 0.0134 | 0.159 |
| `nation.federation_changed` | `nation` | major | protectorate | 0 | | | | | | | | |
| `nation.federation_changed` | `nation` | major | resist-long | 0 | | | | | | | | |
| `nation.statistic_shifted` | `nation` | trivial | protectorate | 383 | 0 | 1.56e-05 | 0.000284 | 0.000747 | 0.00234 | 0.00919 | 0.0334 | 0.159 |
| `nation.statistic_shifted` | `nation` | trivial | resist-long | 819 | 0 | 1.24e-05 | 0.000348 | 0.000896 | 0.00266 | 0.0109 | 0.0319 | 0.202 |
| `faction.takeover` | `targets` | major | protectorate | 338 | 0 | 4.32e-05 | 0.00031 | 0.000595 | 0.0017 | 0.00621 | 0.0145 | 0.159 |
| `faction.takeover` | `targets` | major | resist-long | 360 | 0 | 3.22e-05 | 0.00016 | 0.000454 | 0.00132 | 0.00452 | 0.0146 | 0.157 |
| `faction.takeover_wave` | `targets` | major | protectorate | 43 | 0 | 0.00228 | 0.0106 | 0.0153 | 0.0273 | 0.0468 | 0.106 | 0.209 |
| `faction.takeover_wave` | `targets` | major | resist-long | 47 | 0 | 0.000644 | 0.00167 | 0.0052 | 0.0209 | 0.0678 | 0.158 | 0.259 |
| `nation.merger` | `targets` | major | protectorate | 16 | 0 | 0.000109 | 0.000395 | 0.000606 | 0.00105 | 0.00768 | 0.0303 | 0.153 |
| `nation.merger` | `targets` | major | resist-long | 35 | 0 | 0.00011 | 0.000893 | 0.00192 | 0.00612 | 0.0212 | 0.0369 | 0.16 |
| `war.arc` | `war_sides` | major | protectorate | 11 | 0 | 0.0233 | 0.0366 | 0.0409 | 0.112 | 0.137 | 0.139 | 0.218 |
| `war.arc` | `war_sides` | major | resist-long | 64 | 0 | 0.017 | 0.0485 | 0.0806 | 0.141 | 0.243 | 0.276 | 0.495 |
| **Population** (`population`, reference 0.01) | | | | | | | | | | | | |
| `nation.cession` | `regions` | major | protectorate | 11 | 0 | 0.000448 | 0.000709 | 0.00105 | 0.00252 | 0.00643 | 0.00874 | 0.0168 |
| `nation.cession` | `regions` | major | resist-long | 33 | 0 | 4.27e-05 | 0.000145 | 0.000395 | 0.00106 | 0.00286 | 0.00847 | 0.0174 |
| `nation.claims_declared` | `regions` | trivial | protectorate | 15 | 0 | 5.37e-05 | 0.000374 | 0.00119 | 0.00296 | 0.00529 | 0.0267 | 0.0325 |
| `nation.claims_declared` | `regions` | trivial | resist-long | 79 | 0 | 2.98e-05 | 0.000136 | 0.000292 | 0.00255 | 0.011 | 0.0662 | 0.176 |
| `nation.expansion` | `regions` | major | protectorate | 4 | 0 | 0.00165 | 0.00165 | 0.00165 | 0.0165 | 0.0492 | 0.0795 | 0.0795 |
| `nation.expansion` | `regions` | major | resist-long | 9 | 0 | 0.000356 | 0.000356 | 0.0165 | 0.0538 | 0.0897 | 0.235 | 0.235 |
| `nation.annexation` | `territory` | major | protectorate | 4 | 0 | 0.000429 | 0.000429 | 0.000429 | 0.000722 | 0.00101 | 0.00226 | 0.00226 |
| `nation.annexation` | `territory` | major | resist-long | 35 | 0 | 0.000179 | 0.000342 | 0.000692 | 0.00131 | 0.00447 | 0.00706 | 0.0226 |
| `nation.independence` | `territory` | major | protectorate | 1 | 0 | 0.00744 | 0.00744 | 0.00744 | 0.00744 | 0.00744 | 0.00744 | 0.00744 |
| `nation.independence` | `territory` | major | resist-long | 32 | 0 | 5.90e-05 | 0.000658 | 0.00136 | 0.00335 | 0.00793 | 0.0169 | 0.0522 |
| `nation.territory_gained` | `territory` | minor | protectorate | 24 | 0 | 4.84e-05 | 0.000287 | 0.000641 | 0.00276 | 0.0097 | 0.0257 | 0.165 |
| `nation.territory_gained` | `territory` | minor | resist-long | 111 | 0 | 5.90e-06 | 0.000629 | 0.00105 | 0.00335 | 0.00821 | 0.021 | 0.162 |
| `nation.territory_lost` | `territory` | minor | protectorate | 45 | 0 | 6.24e-06 | 0.000269 | 0.000632 | 0.00154 | 0.00409 | 0.00874 | 0.165 |
| `nation.territory_lost` | `territory` | minor | resist-long | 170 | 0 | 5.90e-06 | 0.000246 | 0.000663 | 0.00193 | 0.00457 | 0.0112 | 0.162 |
| `nation.unification` | `territory` | major | protectorate | 16 | 0 | 4.84e-05 | 5.82e-05 | 0.000332 | 0.00137 | 0.00562 | 0.0343 | 0.165 |
| `nation.unification` | `territory` | major | resist-long | 35 | 0 | 5.90e-06 | 0.000629 | 0.00144 | 0.00713 | 0.0159 | 0.0335 | 0.162 |
| `region.nation_changed` | `territory` | major | protectorate | 114 | 0 | 6.24e-06 | 0.000139 | 0.000448 | 0.00145 | 0.00392 | 0.00687 | 0.0191 |
| `region.nation_changed` | `territory` | major | resist-long | 383 | 0 | 4.83e-06 | 0.000193 | 0.0006 | 0.00139 | 0.00359 | 0.00651 | 0.0216 |
| **Organization** (`organization`, reference 0.01) | | | | | | | | | | | | |
| `organization.assigned_councilor_changed` | `organization` | major | protectorate | 1616 | 0 | 0.000301 | 0.000331 | 0.000375 | 0.000705 | 0.00189 | 0.00298 | 0.00829 |
| `organization.assigned_councilor_changed` | `organization` | major | resist-long | 3836 | 0 | 0.000278 | 0.000298 | 0.000317 | 0.000793 | 0.00139 | 0.00285 | 0.00794 |
| **Hab** (`hab`, reference 0.015) | | | | | | | | | | | | |
| `faction.colonisation_wave` | `colony` | major | protectorate | 15 | 0 | 0.00457 | 0.00529 | 0.00794 | 0.0152 | 0.04 | 0.13 | 0.32 |
| `faction.colonisation_wave` | `colony` | major | resist-long | 51 | 0 | 0.00139 | 0.0018 | 0.00405 | 0.00873 | 0.0181 | 0.0604 | 0.36 |
| `faction.first_hab_on_body` | `hab` | major | protectorate | 82 | 0 | 0.00228 | 0.00265 | 0.00386 | 0.00943 | 0.04 | 0.04 | 0.36 |
| `faction.first_hab_on_body` | `hab` | major | resist-long | 212 | 0 | 0.000696 | 0.00089 | 0.00187 | 0.00223 | 0.00741 | 0.0351 | 0.2 |
| `hab.appeared` | `hab` | minor | protectorate | 184 | 0 | 0.00206 | 0.00228 | 0.00358 | 0.00943 | 0.027 | 0.04 | 0.153 |
| `hab.appeared` | `hab` | minor | resist-long | 375 | 0 | 0.000696 | 0.000885 | 0.00223 | 0.0054 | 0.0107 | 0.0183 | 0.16 |
| `hab.destroyed` | `hab` | minor | protectorate | 21 | 0 | 0.00228 | 0.00265 | 0.00358 | 0.00386 | 0.0143 | 0.0172 | 0.023 |
| `hab.destroyed` | `hab` | minor | resist-long | 114 | 0 | 0.000713 | 0.000872 | 0.00116 | 0.00641 | 0.00749 | 0.00785 | 0.0099 |
| `hab.faction_changed` | `hab` | minor | protectorate | 4 | 0 | 0.00228 | 0.00228 | 0.00228 | 0.00228 | 0.00228 | 0.00265 | 0.00265 |
| `hab.faction_changed` | `hab` | minor | resist-long | 26 | 0 | 0.000893 | 0.00135 | 0.00248 | 0.00356 | 0.00356 | 0.0111 | 0.0142 |
| **Fleet** (`fleet`, reference 0.01) | | | | | | | | | | | | |
| `fleet.faction_changed` | `fleet` | major | protectorate | 0 | | | | | | | | |
| `fleet.faction_changed` | `fleet` | major | resist-long | 0 | | | | | | | | |
| `faction.fleet_buildup` | `new_ships` | minor | protectorate | 6 | 0 | 0.0106 | 0.0106 | 0.0115 | 0.0164 | 0.0518 | 0.0604 | 0.0604 |
| `faction.fleet_buildup` | `new_ships` | minor | resist-long | 86 | 0 | 0.00289 | 0.00868 | 0.0178 | 0.0331 | 0.0517 | 0.102 | 0.274 |
| **Battle** (`battle`, reference 0.0033) | | | | | | | | | | | | |
| `faction.combat_recorded` | `combat` | minor | protectorate | 18 | 1 | 0.00325 | 0.00325 | 0.00343 | 0.00459 | 0.0122 | 0.0492 | 0.0567 |
| `faction.combat_recorded` | `combat` | minor | resist-long | 174 | 22 | 0 | 0.00245 | 0.00678 | 0.0268 | 0.0449 | 0.0734 | 0.178 |
| **Faction** (`faction`, reference 0.143) | | | | | | | | | | | | |
| `councilor.faction_changed` | `left_faction` | major | protectorate | 30 | 23 | 0.0368 | 0.0368 | 0.0583 | 0.0618 | 0.0751 | 0.195 | 0.195 |
| `councilor.faction_changed` | `left_faction` | major | resist-long | 49 | 39 | 0.0332 | 0.0332 | 0.0747 | 0.0797 | 0.104 | 0.109 | 0.142 |
| **Nuclear share** (`nuclear`, reference 0.01) | | | | | | | | | | | | |
| `nation.nuclear_armament` | `nuclear_arc` | major | protectorate | 1 | 0 | 0.025 | 0.025 | 0.025 | 0.025 | 0.025 | 0.025 | 0.025 |
| `nation.nuclear_armament` | `nuclear_arc` | major | resist-long | 9 | 0 | 0.0164 | 0.0164 | 0.0167 | 0.0208 | 0.0351 | 0.0408 | 0.0408 |
| `nation.nuclear_buildup` | `nuclear_arc` | major | protectorate | 0 | | | | | | | | |
| `nation.nuclear_buildup` | `nuclear_arc` | major | resist-long | 3 | 0 | 0.0164 | 0.0164 | 0.0164 | 0.0222 | 0.117 | 0.117 | 0.117 |
| `nation.nuclear_disarmament` | `nuclear_arc` | major | protectorate | 1 | 0 | 0.435 | 0.435 | 0.435 | 0.435 | 0.435 | 0.435 | 0.435 |
| `nation.nuclear_disarmament` | `nuclear_arc` | major | resist-long | 5 | 0 | 0.0167 | 0.0167 | 0.0182 | 0.0328 | 0.0328 | 0.389 | 0.389 |

Events without a share:

- `nation.relation_changed`: all 950 and 2,814. The `belligerents` stake reads a share only for a war relation, and
  no event of the kind is one in either campaign. Its context rule leaves every event at minor.
- `nation.claims_changed`: 12 of 19 and 57 of 79. No power share was found for the claiming nation on either side
  of the interval.
- `councilor.faction_changed`: 23 of 30 and 39 of 49. The stake is the faction the councilor leaves; the rows read
  without a share are recruits, with no faction before.
- `faction.combat_recorded`: 1 of 18 and 22 of 174. The code measures no contested mass when the record does not
  say enough; the rows read are one-sided records against a hab. Three more events in `resist-long` have a share of
  exactly 0.

## 2. Levels today, and what the stake moves

- **Starts at** is the level before the stake: the level a context rule decided where the kind has one (marked
  `rule`), else the base level.
- **Lowered**, **Raised** and **Unmoved** compare the level of the event's own score, its start moved by its stake,
  with where it started.
- **Set by a cited event** counts the narrative events whose level today is above their own score's level, because
  a narrative event scores at least as high as the highest event it cites. It does not apply to other kinds.
- **Level today** is the level the table holds. T, m, M and CD are trivial, minor, major and campaign defining.

| Kind | Base | Campaign | Events | Starts at | Lowered | Raised | Unmoved | Set by a cited event | Level today |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `nation.cohesion_shift` | minor | protectorate | 73 | m 34 M 39 (rule) | 21 | 0 | 52 | 0 | T 16 m 23 M 34 |
| `nation.cohesion_shift` | minor | resist-long | 92 | m 18 M 74 (rule) | 32 | 0 | 60 | 0 | T 5 m 40 M 47 |
| `nation.demobilization` | major | protectorate | 1 | M 1 | 0 | 0 | 1 | 0 | M 1 |
| `nation.demobilization` | major | resist-long | 3 | M 3 | 0 | 0 | 3 | 0 | M 3 |
| `nation.diplomatic_realignment` | major | protectorate | 104 | M 104 | 20 | 0 | 84 | 5 | m 15 M 89 |
| `nation.diplomatic_realignment` | major | resist-long | 202 | M 202 | 54 | 1 | 147 | 6 | m 48 M 153 CD 1 |
| `nation.economic_trajectory` | major | protectorate | 4 | M 4 | 1 | 0 | 3 | 0 | m 1 M 3 |
| `nation.economic_trajectory` | major | resist-long | 20 | M 20 | 8 | 1 | 11 | 0 | m 8 M 11 CD 1 |
| `nation.government_shift` | minor | protectorate | 15 | M 15 (rule) | 6 | 0 | 9 | 0 | m 6 M 9 |
| `nation.government_shift` | minor | resist-long | 15 | M 15 (rule) | 8 | 0 | 7 | 0 | m 8 M 7 |
| `nation.inequality_shift` | minor | protectorate | 9 | m 9 (rule) | 1 | 0 | 8 | 0 | T 1 m 8 |
| `nation.inequality_shift` | minor | resist-long | 14 | m 12 M 2 (rule) | 6 | 0 | 8 | 0 | T 4 m 10 |
| `nation.military_buildup` | major | protectorate | 1 | M 1 | 0 | 0 | 1 | 0 | M 1 |
| `nation.military_buildup` | major | resist-long | 3 | M 3 | 0 | 0 | 3 | 0 | M 3 |
| `nation.miltech_shift` | minor | protectorate | 2 | M 2 (rule) | 2 | 0 | 0 | 0 | m 2 |
| `nation.miltech_shift` | minor | resist-long | 8 | M 8 (rule) | 6 | 0 | 2 | 0 | m 6 M 2 |
| `nation.navy_established` | major | protectorate | 4 | M 4 | 0 | 0 | 4 | 0 | M 4 |
| `nation.navy_established` | major | resist-long | 6 | M 6 | 0 | 0 | 6 | 0 | M 6 |
| `nation.unrest_shift` | minor | protectorate | 108 | m 79 M 29 (rule) | 38 | 0 | 70 | 0 | T 25 m 67 M 16 |
| `nation.unrest_shift` | minor | resist-long | 99 | m 65 M 34 (rule) | 24 | 0 | 75 | 0 | T 12 m 65 M 22 |
| `nation.relation_changed` | minor | protectorate | 950 | m 950 (rule) | 0 | 0 | 950 | n/a | m 950 |
| `nation.relation_changed` | minor | resist-long | 2814 | m 2814 (rule) | 0 | 0 | 2814 | n/a | m 2814 |
| `control_point.controller_changed` | major | protectorate | 936 | M 936 | 298 | 0 | 638 | n/a | m 298 M 638 |
| `control_point.controller_changed` | major | resist-long | 1062 | M 1062 | 409 | 0 | 653 | n/a | m 409 M 653 |
| `nation.breakaway` | trivial | protectorate | 1 | T 1 | 0 | 0 | 1 | 1 | M 1 |
| `nation.breakaway` | trivial | resist-long | 9 | T 9 | 0 | 1 | 8 | 9 | M 9 |
| `nation.release` | trivial | resist-long | 23 | T 23 | 0 | 0 | 23 | 23 | m 1 M 22 |
| `federation.lifecycle` | major | protectorate | 12 | M 12 | 0 | 0 | 12 | 0 | M 12 |
| `federation.lifecycle` | major | resist-long | 23 | M 23 | 0 | 3 | 20 | 0 | M 20 CD 3 |
| `faction.nation_control_changed` | major | protectorate | 1121 | M 1121 | 270 | 0 | 851 | n/a | m 270 M 851 |
| `faction.nation_control_changed` | major | resist-long | 1613 | M 1613 | 464 | 0 | 1149 | n/a | m 464 M 1149 |
| `nation.claims_changed` | minor | protectorate | 19 | m 1 M 18 (rule) | 1 | 0 | 18 | n/a | m 2 M 17 |
| `nation.claims_changed` | minor | resist-long | 79 | M 79 (rule) | 4 | 1 | 74 | n/a | m 4 M 74 CD 1 |
| `nation.executive_change_recorded` | minor | protectorate | 331 | m 295 M 36 (rule) | 81 | 0 | 250 | n/a | T 79 m 218 M 34 |
| `nation.executive_change_recorded` | minor | resist-long | 411 | m 336 M 75 (rule) | 127 | 0 | 284 | n/a | T 112 m 239 M 60 |
| `nation.statistic_shifted` | trivial | protectorate | 383 | T 383 | 0 | 0 | 383 | n/a | T 383 |
| `nation.statistic_shifted` | trivial | resist-long | 819 | T 819 | 0 | 3 | 816 | n/a | T 816 m 3 |
| `faction.takeover` | major | protectorate | 338 | M 338 | 78 | 0 | 260 | 13 | m 65 M 273 |
| `faction.takeover` | major | resist-long | 360 | M 360 | 108 | 0 | 252 | 13 | m 95 M 265 |
| `faction.takeover_wave` | major | protectorate | 43 | M 43 | 0 | 1 | 42 | 0 | M 42 CD 1 |
| `faction.takeover_wave` | major | resist-long | 47 | M 47 | 0 | 2 | 45 | 0 | M 45 CD 2 |
| `nation.merger` | major | protectorate | 16 | M 16 | 2 | 0 | 14 | 0 | m 2 M 14 |
| `nation.merger` | major | resist-long | 35 | M 35 | 2 | 0 | 33 | 0 | m 2 M 33 |
| `war.arc` | major | protectorate | 11 | M 11 | 0 | 1 | 10 | 0 | M 10 CD 1 |
| `war.arc` | major | resist-long | 64 | M 64 | 0 | 27 | 37 | 3 | M 34 CD 30 |
| `nation.cession` | major | protectorate | 11 | M 11 | 1 | 0 | 10 | 0 | m 1 M 10 |
| `nation.cession` | major | resist-long | 33 | M 33 | 9 | 0 | 24 | 0 | m 9 M 24 |
| `nation.claims_declared` | trivial | protectorate | 15 | T 15 | 0 | 0 | 15 | 15 | m 1 M 14 |
| `nation.claims_declared` | trivial | resist-long | 79 | T 79 | 0 | 0 | 79 | 79 | m 4 M 74 CD 1 |
| `nation.expansion` | major | protectorate | 4 | M 4 | 0 | 0 | 4 | 0 | M 4 |
| `nation.expansion` | major | resist-long | 9 | M 9 | 1 | 1 | 7 | 0 | m 1 M 7 CD 1 |
| `nation.annexation` | major | protectorate | 4 | M 4 | 1 | 0 | 3 | n/a | m 1 M 3 |
| `nation.annexation` | major | resist-long | 35 | M 35 | 6 | 0 | 29 | n/a | m 6 M 29 |
| `nation.independence` | major | protectorate | 1 | M 1 | 0 | 0 | 1 | n/a | M 1 |
| `nation.independence` | major | resist-long | 32 | M 32 | 1 | 0 | 31 | n/a | m 1 M 31 |
| `nation.territory_gained` | minor | protectorate | 24 | m 24 | 4 | 0 | 20 | n/a | T 4 m 20 |
| `nation.territory_gained` | minor | resist-long | 111 | m 111 | 10 | 0 | 101 | n/a | T 10 m 101 |
| `nation.territory_lost` | minor | protectorate | 45 | m 45 | 10 | 0 | 35 | n/a | T 10 m 35 |
| `nation.territory_lost` | minor | resist-long | 170 | m 170 | 33 | 0 | 137 | n/a | T 33 m 137 |
| `nation.unification` | major | protectorate | 16 | M 16 | 4 | 0 | 12 | n/a | m 4 M 12 |
| `nation.unification` | major | resist-long | 35 | M 35 | 3 | 0 | 32 | n/a | m 3 M 32 |
| `region.nation_changed` | major | protectorate | 114 | M 114 | 31 | 0 | 83 | n/a | m 31 M 83 |
| `region.nation_changed` | major | resist-long | 383 | M 383 | 93 | 0 | 290 | n/a | m 93 M 290 |
| `organization.assigned_councilor_changed` | major | protectorate | 1616 | M 1616 | 714 | 0 | 902 | n/a | m 714 M 902 |
| `organization.assigned_councilor_changed` | major | resist-long | 3836 | M 3836 | 1808 | 0 | 2028 | n/a | m 1808 M 2028 |
| `faction.colonisation_wave` | major | protectorate | 15 | M 15 | 0 | 1 | 14 | 0 | M 14 CD 1 |
| `faction.colonisation_wave` | major | resist-long | 51 | M 51 | 0 | 1 | 50 | 0 | M 50 CD 1 |
| `faction.first_hab_on_body` | major | protectorate | 82 | M 82 | 0 | 1 | 81 | n/a | M 81 CD 1 |
| `faction.first_hab_on_body` | major | resist-long | 212 | M 212 | 13 | 0 | 199 | n/a | m 13 M 199 |
| `hab.appeared` | minor | protectorate | 184 | m 184 | 0 | 0 | 184 | n/a | m 184 |
| `hab.appeared` | minor | resist-long | 375 | m 375 | 30 | 0 | 345 | n/a | T 30 m 345 |
| `hab.destroyed` | minor | protectorate | 21 | m 21 | 0 | 0 | 21 | n/a | m 21 |
| `hab.destroyed` | minor | resist-long | 114 | m 114 | 10 | 0 | 104 | n/a | T 10 m 104 |
| `hab.faction_changed` | minor | protectorate | 4 | m 4 | 0 | 0 | 4 | n/a | m 4 |
| `hab.faction_changed` | minor | resist-long | 26 | m 26 | 0 | 0 | 26 | n/a | m 26 |
| `faction.fleet_buildup` | minor | protectorate | 6 | m 6 | 0 | 0 | 6 | 0 | m 6 |
| `faction.fleet_buildup` | minor | resist-long | 86 | m 86 | 0 | 2 | 84 | 0 | m 84 M 2 |
| `faction.combat_recorded` | minor | protectorate | 18 | m 18 | 0 | 0 | 18 | n/a | m 18 |
| `faction.combat_recorded` | minor | resist-long | 174 | m 174 | 3 | 30 | 141 | n/a | T 3 m 141 M 30 |
| `councilor.faction_changed` | major | protectorate | 30 | M 30 | 0 | 0 | 30 | n/a | M 30 |
| `councilor.faction_changed` | major | resist-long | 49 | M 49 | 0 | 0 | 49 | n/a | M 49 |
| `nation.nuclear_armament` | major | protectorate | 1 | M 1 | 0 | 0 | 1 | 0 | M 1 |
| `nation.nuclear_armament` | major | resist-long | 9 | M 9 | 0 | 0 | 9 | 0 | M 9 |
| `nation.nuclear_buildup` | major | resist-long | 3 | M 3 | 0 | 0 | 3 | 0 | M 3 |
| `nation.nuclear_disarmament` | major | protectorate | 1 | M 1 | 0 | 1 | 0 | 0 | CD 1 |
| `nation.nuclear_disarmament` | major | resist-long | 5 | M 5 | 0 | 1 | 4 | 0 | M 4 CD 1 |

Per measure and campaign:

| Measure | `protectorate`: lowered | raised | `resist-long`: lowered | raised |
| --- | ---: | ---: | ---: | ---: |
| power | 819 | 2 | 1,252 | 39 |
| population | 51 | 0 | 156 | 1 |
| organization | 714 | 0 | 1,808 | 0 |
| hab | 0 | 2 | 53 | 1 |
| fleet | 0 | 0 | 0 | 2 |
| battle | 0 | 0 | 3 | 30 |
| faction | 0 | 0 | 0 | 0 |
| nuclear | 0 | 1 | 0 | 1 |
| all | 1,584 | 5 | 3,272 | 74 |

- Kinds that only fall, in both campaigns, with over 100 events in each: `control_point.controller_changed` (298 of
  936, 409 of 1,062), `faction.nation_control_changed` (270 of 1,121, 464 of 1,613), `faction.takeover` (78 of 338,
  108 of 360), `nation.executive_change_recorded` (81 of 331, 127 of 411), `region.nation_changed` (31 of 114, 93 of
  383) and `organization.assigned_councilor_changed` (714 of 1,616, 1,808 of 3,836).
- Kinds that only rise: `war.arc` (1 of 11, 27 of 64), `federation.lifecycle` (0 of 12, 3 of 23),
  `faction.takeover_wave` (1 of 43, 2 of 47), `faction.colonisation_wave` (1 of 15, 1 of 51),
  `faction.fleet_buildup` (0 of 6, 2 of 86), `nation.nuclear_disarmament` (1 of 1, 1 of 5),
  `nation.statistic_shifted` (0 of 383, 3 of 819, from trivial to minor) and `nation.breakaway` (0 of 1, 1 of 9,
  where a cited event sets the level anyway).
- Kinds that move both ways: `faction.combat_recorded` in `resist-long` (3 lowered, 30 raised),
  `nation.diplomatic_realignment` (54 lowered, 1 raised), `nation.economic_trajectory` (8 and 1),
  `nation.claims_changed` (4 and 1) and `nation.expansion` (1 and 1), each in `resist-long` only.
- The six band-shift kinds start at the level their context rule decides, and the stake then lowers 68 of 207 events
  in `protectorate` and 76 of 228 in `resist-long`. It raises none.

## 3. Span against the width of a level

- **Tenfolds** is `log10(largest ÷ smallest)` over the kind's shares above 0, from the minimum to the maximum and
  from the 10th to the 90th percentile. One level is 2.5 tenfolds wide today.
- **Below the reference** counts the events the stake pulls down at all.
- The next three columns place the events against today's two cut-offs. An event at or below the fall cut-off is
  lowered unless its start is trivial; one at or above the rise cut-off is raised unless its start is campaign
  defining.
- **Max ÷ rise cut-off** below 1 means no event of the kind in that campaign can rise.
- **At clamp** counts the events whose stake is held at −20 or +15 points.

| Kind | Campaign | With a share | Tenfolds min–max | Tenfolds P10–P90 | Below the reference | At or below the fall cut-off | Between | At or above the rise cut-off | Max ÷ rise cut-off | At clamp −20 | At clamp +15 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `nation.cohesion_shift` | protectorate | 73 | 3.6 | 1.5 | 67 (92 %) | 21 | 52 | 0 | 0.90 | 1 | 0 |
| `nation.cohesion_shift` | resist-long | 92 | 2.6 | 1.4 | 88 (96 %) | 32 | 60 | 0 | 0.12 | 1 | 0 |
| `nation.demobilization` | protectorate | 1 | 0.0 | 0.0 | 0 (0 %) | 0 | 1 | 0 | 0.43 | 0 | 0 |
| `nation.demobilization` | resist-long | 3 | 0.2 | 0.2 | 0 (0 %) | 0 | 3 | 0 | 0.65 | 0 | 0 |
| `nation.diplomatic_realignment` | protectorate | 104 | 3.7 | 1.7 | 84 (81 %) | 20 | 84 | 0 | 0.76 | 3 | 0 |
| `nation.diplomatic_realignment` | resist-long | 202 | 3.7 | 1.9 | 156 (77 %) | 54 | 147 | 1 | 1.46 | 3 | 0 |
| `nation.economic_trajectory` | protectorate | 4 | 1.8 | 1.8 | 3 (75 %) | 1 | 3 | 0 | 0.11 | 0 | 0 |
| `nation.economic_trajectory` | resist-long | 20 | 3.8 | 2.8 | 15 (75 %) | 8 | 11 | 1 | 1.45 | 1 | 0 |
| `nation.government_shift` | protectorate | 15 | 3.6 | 3.5 | 12 (80 %) | 6 | 9 | 0 | 0.90 | 3 | 0 |
| `nation.government_shift` | resist-long | 15 | 2.3 | 1.7 | 14 (93 %) | 8 | 7 | 0 | 0.06 | 2 | 0 |
| `nation.inequality_shift` | protectorate | 9 | 2.3 | 2.3 | 6 (67 %) | 1 | 8 | 0 | 0.41 | 0 | 0 |
| `nation.inequality_shift` | resist-long | 14 | 2.8 | 2.6 | 10 (71 %) | 6 | 8 | 0 | 0.63 | 0 | 0 |
| `nation.military_buildup` | protectorate | 1 | 0.0 | 0.0 | 0 (0 %) | 0 | 1 | 0 | 0.20 | 0 | 0 |
| `nation.military_buildup` | resist-long | 3 | 1.0 | 1.0 | 0 (0 %) | 0 | 3 | 0 | 0.69 | 0 | 0 |
| `nation.miltech_shift` | protectorate | 2 | 0.2 | 0.2 | 2 (100 %) | 2 | 0 | 0 | 0.00 | 0 | 0 |
| `nation.miltech_shift` | resist-long | 8 | 2.9 | 2.9 | 6 (75 %) | 6 | 2 | 0 | 0.22 | 2 | 0 |
| `nation.navy_established` | protectorate | 4 | 0.7 | 0.7 | 1 (25 %) | 0 | 4 | 0 | 0.20 | 0 | 0 |
| `nation.navy_established` | resist-long | 6 | 0.6 | 0.6 | 1 (17 %) | 0 | 6 | 0 | 0.22 | 0 | 0 |
| `nation.unrest_shift` | protectorate | 108 | 3.6 | 1.9 | 85 (79 %) | 38 | 70 | 0 | 0.90 | 4 | 0 |
| `nation.unrest_shift` | resist-long | 99 | 3.6 | 1.9 | 80 (81 %) | 24 | 75 | 0 | 0.89 | 5 | 0 |
| `control_point.controller_changed` | protectorate | 936 | 3.1 | 1.4 | 885 (95 %) | 298 | 638 | 0 | 0.20 | 24 | 0 |
| `control_point.controller_changed` | resist-long | 1062 | 3.0 | 1.6 | 998 (94 %) | 409 | 653 | 0 | 0.15 | 58 | 0 |
| `nation.breakaway` | protectorate | 1 | 0.0 | 0.0 | 1 (100 %) | 0 | 1 | 0 | 0.04 | 0 | 0 |
| `nation.breakaway` | resist-long | 9 | 2.1 | 2.1 | 3 (33 %) | 0 | 8 | 1 | 1.04 | 0 | 0 |
| `nation.release` | resist-long | 23 | 1.6 | 1.2 | 21 (91 %) | 2 | 21 | 0 | 0.11 | 0 | 0 |
| `federation.lifecycle` | protectorate | 12 | 2.2 | 1.9 | 6 (50 %) | 0 | 12 | 0 | 0.92 | 0 | 0 |
| `federation.lifecycle` | resist-long | 23 | 2.1 | 1.3 | 5 (22 %) | 0 | 20 | 3 | 3.44 | 0 | 1 |
| `faction.nation_control_changed` | protectorate | 1121 | 3.7 | 1.7 | 950 (85 %) | 270 | 851 | 0 | 0.90 | 27 | 0 |
| `faction.nation_control_changed` | resist-long | 1613 | 3.7 | 1.7 | 1381 (86 %) | 464 | 1149 | 0 | 0.90 | 80 | 0 |
| `nation.claims_changed` | protectorate | 7 | 1.6 | 1.6 | 7 (100 %) | 1 | 6 | 0 | 0.04 | 0 | 0 |
| `nation.claims_changed` | resist-long | 22 | 3.2 | 2.7 | 14 (64 %) | 4 | 17 | 1 | 1.04 | 0 | 0 |
| `nation.executive_change_recorded` | protectorate | 331 | 3.6 | 1.7 | 278 (84 %) | 81 | 250 | 0 | 0.89 | 8 | 0 |
| `nation.executive_change_recorded` | resist-long | 411 | 3.7 | 1.8 | 349 (85 %) | 127 | 284 | 0 | 0.89 | 25 | 0 |
| `nation.statistic_shifted` | protectorate | 383 | 4.0 | 2.1 | 296 (77 %) | 74 | 309 | 0 | 0.89 | 16 | 0 |
| `nation.statistic_shifted` | resist-long | 819 | 4.2 | 2.0 | 591 (72 %) | 144 | 672 | 3 | 1.14 | 16 | 0 |
| `faction.takeover` | protectorate | 338 | 3.6 | 1.7 | 281 (83 %) | 78 | 260 | 0 | 0.89 | 7 | 0 |
| `faction.takeover` | resist-long | 360 | 3.7 | 2.0 | 299 (83 %) | 108 | 252 | 0 | 0.89 | 22 | 0 |
| `faction.takeover_wave` | protectorate | 43 | 2.0 | 1.0 | 4 (9 %) | 0 | 42 | 1 | 1.18 | 0 | 0 |
| `faction.takeover_wave` | resist-long | 47 | 2.6 | 2.0 | 15 (32 %) | 0 | 45 | 2 | 1.46 | 0 | 0 |
| `nation.merger` | protectorate | 16 | 3.1 | 1.9 | 13 (81 %) | 2 | 14 | 0 | 0.86 | 1 | 0 |
| `nation.merger` | resist-long | 35 | 3.2 | 1.6 | 21 (60 %) | 2 | 33 | 0 | 0.90 | 1 | 0 |
| `war.arc` | protectorate | 11 | 1.0 | 0.6 | 0 (0 %) | 0 | 10 | 1 | 1.23 | 0 | 0 |
| `war.arc` | resist-long | 64 | 1.5 | 0.8 | 0 (0 %) | 0 | 37 | 27 | 2.78 | 0 | 4 |
| `nation.cession` | protectorate | 11 | 1.6 | 1.1 | 10 (91 %) | 1 | 10 | 0 | 0.09 | 0 | 0 |
| `nation.cession` | resist-long | 33 | 2.6 | 1.8 | 30 (91 %) | 9 | 24 | 0 | 0.10 | 3 | 0 |
| `nation.claims_declared` | protectorate | 15 | 2.8 | 1.9 | 13 (87 %) | 2 | 13 | 0 | 0.18 | 1 | 0 |
| `nation.claims_declared` | resist-long | 79 | 3.8 | 2.7 | 58 (73 %) | 24 | 55 | 0 | 0.99 | 4 | 0 |
| `nation.expansion` | protectorate | 4 | 1.7 | 1.7 | 1 (25 %) | 0 | 4 | 0 | 0.45 | 0 | 0 |
| `nation.expansion` | resist-long | 9 | 2.8 | 2.8 | 2 (22 %) | 1 | 7 | 1 | 1.32 | 0 | 0 |
| `nation.annexation` | protectorate | 4 | 0.7 | 0.7 | 4 (100 %) | 1 | 3 | 0 | 0.01 | 0 | 0 |
| `nation.annexation` | resist-long | 35 | 2.1 | 1.3 | 32 (91 %) | 6 | 29 | 0 | 0.13 | 0 | 0 |
| `nation.independence` | protectorate | 1 | 0.0 | 0.0 | 1 (100 %) | 0 | 1 | 0 | 0.04 | 0 | 0 |
| `nation.independence` | resist-long | 32 | 2.9 | 1.4 | 25 (78 %) | 1 | 31 | 0 | 0.29 | 1 | 0 |
| `nation.territory_gained` | protectorate | 24 | 3.5 | 2.0 | 18 (75 %) | 4 | 20 | 0 | 0.93 | 2 | 0 |
| `nation.territory_gained` | resist-long | 111 | 4.4 | 1.5 | 86 (77 %) | 10 | 101 | 0 | 0.91 | 4 | 0 |
| `nation.territory_lost` | protectorate | 45 | 4.4 | 1.5 | 41 (91 %) | 10 | 35 | 0 | 0.93 | 4 | 0 |
| `nation.territory_lost` | resist-long | 170 | 4.4 | 1.7 | 150 (88 %) | 33 | 137 | 0 | 0.91 | 9 | 0 |
| `nation.unification` | protectorate | 16 | 3.5 | 2.8 | 13 (81 %) | 4 | 12 | 0 | 0.93 | 2 | 0 |
| `nation.unification` | resist-long | 35 | 4.4 | 1.7 | 24 (69 %) | 3 | 32 | 0 | 0.91 | 1 | 0 |
| `region.nation_changed` | protectorate | 114 | 3.5 | 1.7 | 107 (94 %) | 31 | 83 | 0 | 0.11 | 9 | 0 |
| `region.nation_changed` | resist-long | 383 | 3.7 | 1.5 | 364 (95 %) | 93 | 290 | 0 | 0.12 | 23 | 0 |
| `organization.assigned_councilor_changed` | protectorate | 1616 | 1.4 | 1.0 | 1616 (100 %) | 714 | 902 | 0 | 0.05 | 0 | 0 |
| `organization.assigned_councilor_changed` | resist-long | 3836 | 1.5 | 1.0 | 3836 (100 %) | 1808 | 2028 | 0 | 0.04 | 0 | 0 |
| `faction.colonisation_wave` | protectorate | 15 | 1.8 | 1.4 | 7 (47 %) | 0 | 14 | 1 | 1.20 | 0 | 0 |
| `faction.colonisation_wave` | resist-long | 51 | 2.4 | 1.5 | 37 (73 %) | 0 | 50 | 1 | 1.35 | 0 | 0 |
| `faction.first_hab_on_body` | protectorate | 82 | 2.2 | 1.2 | 53 (65 %) | 0 | 81 | 1 | 1.35 | 0 | 0 |
| `faction.first_hab_on_body` | resist-long | 212 | 2.5 | 1.6 | 170 (80 %) | 13 | 199 | 0 | 0.75 | 0 | 0 |
| `hab.appeared` | protectorate | 184 | 1.9 | 1.2 | 106 (58 %) | 0 | 184 | 0 | 0.57 | 0 | 0 |
| `hab.appeared` | resist-long | 375 | 2.4 | 1.3 | 287 (77 %) | 30 | 345 | 0 | 0.60 | 0 | 0 |
| `hab.destroyed` | protectorate | 21 | 1.0 | 0.8 | 17 (81 %) | 0 | 21 | 0 | 0.09 | 0 | 0 |
| `hab.destroyed` | resist-long | 114 | 1.1 | 1.0 | 114 (100 %) | 10 | 104 | 0 | 0.04 | 0 | 0 |
| `hab.faction_changed` | protectorate | 4 | 0.1 | 0.1 | 4 (100 %) | 0 | 4 | 0 | 0.01 | 0 | 0 |
| `hab.faction_changed` | resist-long | 26 | 1.2 | 0.9 | 26 (100 %) | 0 | 26 | 0 | 0.05 | 0 | 0 |
| `faction.fleet_buildup` | protectorate | 6 | 0.8 | 0.8 | 0 (0 %) | 0 | 6 | 0 | 0.34 | 0 | 0 |
| `faction.fleet_buildup` | resist-long | 86 | 2.0 | 1.1 | 12 (14 %) | 0 | 84 | 2 | 1.54 | 0 | 0 |
| `faction.combat_recorded` | protectorate | 17 | 1.2 | 1.2 | 4 (24 %) | 0 | 17 | 0 | 0.97 | 0 | 0 |
| `faction.combat_recorded` | resist-long | 152 | 2.3 | 1.4 | 22 (14 %) | 3 | 119 | 30 | 3.03 | 3 | 8 |
| `councilor.faction_changed` | protectorate | 7 | 0.7 | 0.7 | 6 (86 %) | 0 | 7 | 0 | 0.08 | 0 | 0 |
| `councilor.faction_changed` | resist-long | 10 | 0.6 | 0.5 | 10 (100 %) | 0 | 10 | 0 | 0.06 | 0 | 0 |
| `nation.nuclear_armament` | protectorate | 1 | 0.0 | 0.0 | 0 (0 %) | 0 | 1 | 0 | 0.14 | 0 | 0 |
| `nation.nuclear_armament` | resist-long | 9 | 0.4 | 0.4 | 0 (0 %) | 0 | 9 | 0 | 0.23 | 0 | 0 |
| `nation.nuclear_buildup` | resist-long | 3 | 0.9 | 0.9 | 0 (0 %) | 0 | 3 | 0 | 0.66 | 0 | 0 |
| `nation.nuclear_disarmament` | protectorate | 1 | 0.0 | 0.0 | 0 (0 %) | 0 | 0 | 1 | 2.44 | 0 | 1 |
| `nation.nuclear_disarmament` | resist-long | 5 | 1.4 | 1.4 | 0 (0 %) | 0 | 4 | 1 | 2.19 | 0 | 1 |

- Wider than a level from minimum to maximum, in both campaigns: `faction.nation_control_changed`,
  `faction.takeover`, `nation.executive_change_recorded`, `nation.statistic_shifted`,
  `control_point.controller_changed`, `nation.unrest_shift`, `nation.diplomatic_realignment`,
  `nation.cohesion_shift`, `nation.merger`, `region.nation_changed`, `nation.territory_gained`,
  `nation.territory_lost`, `nation.unification` and `nation.claims_declared`. Between the 10th and 90th percentile
  only `nation.government_shift` (3.5, `protectorate`), `nation.unification` (2.8, `protectorate`),
  `nation.economic_trajectory`, `nation.inequality_shift`, `nation.miltech_shift`, `nation.claims_changed`,
  `nation.claims_declared` and `nation.expansion` (2.6 to 2.9, `resist-long`) pass 2.5, each on 8 to 79 events.
- Narrower than 1.5 tenfolds from minimum to maximum, in both campaigns, with 10 or more events in each:
  `war.arc`, `organization.assigned_councilor_changed`, `hab.destroyed`.
- A kind whose largest share is below the rise cut-off in both campaigns cannot rise on the samples. That holds for
  29 of the 43 kinds that show a share. The 14 that pass it in at least one campaign are `war.arc`,
  `federation.lifecycle`, `faction.takeover_wave`, `nation.diplomatic_realignment`, `nation.economic_trajectory`,
  `nation.breakaway`, `nation.claims_changed`, `nation.statistic_shifted`, `nation.expansion`,
  `faction.colonisation_wave`, `faction.first_hab_on_body`, `faction.fleet_buildup`, `faction.combat_recorded` and
  `nation.nuclear_disarmament`.
- The clamp: 112 events sit at −20 and 1 at +15 in `protectorate`, 264 and 14 in `resist-long`. Replaying the table
  with `--clamp off` moves no event to another level in either campaign.

## 4. Kinds side by side on each measure

### By kind

The ordinary share of a kind is its median in one campaign. **Siblings** are the other kinds on the same measure
that show a share in that campaign, and a kind is compared with the median of their medians. The comparison is
marked `**` beyond a factor of three. On nation power most siblings take one nation, so that is what the middle
stands for.

| Measure | Kind | Stake | Campaign | With a share | Median | Siblings' median of medians | Ratio |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| power | `nation.cohesion_shift` | `actor` | protectorate | 73 | 0.00101 | 0.00206 | ÷2.04 |
| power | `nation.demobilization` | `actor` | protectorate | 1 | 0.0765 | 0.00174 | ×43.90 ** |
| power | `nation.diplomatic_realignment` | `actor` | protectorate | 104 | 0.00178 | 0.00202 | ÷1.14 |
| power | `nation.economic_trajectory` | `actor` | protectorate | 4 | 0.000761 | 0.00206 | ÷2.71 |
| power | `nation.government_shift` | `actor` | protectorate | 15 | 0.00124 | 0.00206 | ÷1.66 |
| power | `nation.inequality_shift` | `actor` | protectorate | 9 | 0.00235 | 0.00174 | ×1.35 |
| power | `nation.military_buildup` | `actor` | protectorate | 1 | 0.0348 | 0.00174 | ×19.98 ** |
| power | `nation.miltech_shift` | `actor` | protectorate | 2 | 0.000285 | 0.00206 | ÷7.24 ** |
| power | `nation.navy_established` | `actor` | protectorate | 4 | 0.0105 | 0.00174 | ×6.00 ** |
| power | `nation.unrest_shift` | `actor` | protectorate | 108 | 0.00142 | 0.00206 | ÷1.45 |
| power | `control_point.controller_changed` | `control_point` | protectorate | 936 | 0.000798 | 0.00206 | ÷2.59 |
| power | `nation.breakaway` | `independent_nation` | protectorate | 1 | 0.00646 | 0.00174 | ×3.70 ** |
| power | `federation.lifecycle` | `members` | protectorate | 12 | 0.00874 | 0.00174 | ×5.01 ** |
| power | `faction.nation_control_changed` | `nation` | protectorate | 1121 | 0.00155 | 0.00206 | ÷1.33 |
| power | `nation.claims_changed` | `nation` | protectorate | 7 | 0.00433 | 0.00174 | ×2.49 |
| power | `nation.executive_change_recorded` | `nation` | protectorate | 331 | 0.00163 | 0.00206 | ÷1.27 |
| power | `nation.statistic_shifted` | `nation` | protectorate | 383 | 0.00234 | 0.00174 | ×1.34 |
| power | `faction.takeover` | `targets` | protectorate | 338 | 0.0017 | 0.00206 | ÷1.21 |
| power | `faction.takeover_wave` | `targets` | protectorate | 43 | 0.0273 | 0.00174 | ×15.69 ** |
| power | `nation.merger` | `targets` | protectorate | 16 | 0.00105 | 0.00206 | ÷1.96 |
| power | `war.arc` | `war_sides` | protectorate | 11 | 0.112 | 0.00174 | ×64.21 ** |
| power | `nation.cohesion_shift` | `actor` | resist-long | 92 | 0.000821 | 0.00228 | ÷2.78 |
| power | `nation.demobilization` | `actor` | resist-long | 3 | 0.113 | 0.00191 | ×59.06 ** |
| power | `nation.diplomatic_realignment` | `actor` | resist-long | 202 | 0.00191 | 0.00228 | ÷1.19 |
| power | `nation.economic_trajectory` | `actor` | resist-long | 20 | 0.000681 | 0.00228 | ÷3.34 ** |
| power | `nation.government_shift` | `actor` | resist-long | 15 | 0.000551 | 0.00228 | ÷4.13 ** |
| power | `nation.inequality_shift` | `actor` | resist-long | 14 | 0.000638 | 0.00228 | ÷3.57 ** |
| power | `nation.military_buildup` | `actor` | resist-long | 3 | 0.0701 | 0.00191 | ×36.78 ** |
| power | `nation.miltech_shift` | `actor` | resist-long | 8 | 0.000307 | 0.00228 | ÷7.42 ** |
| power | `nation.navy_established` | `actor` | resist-long | 6 | 0.0122 | 0.00191 | ×6.40 ** |
| power | `nation.unrest_shift` | `actor` | resist-long | 99 | 0.00152 | 0.00228 | ÷1.50 |
| power | `control_point.controller_changed` | `control_point` | resist-long | 1062 | 0.000769 | 0.00228 | ÷2.96 |
| power | `nation.breakaway` | `independent_nation` | resist-long | 9 | 0.0159 | 0.00191 | ×8.31 ** |
| power | `nation.release` | `independent_nation` | resist-long | 23 | 0.00228 | 0.00191 | ×1.19 |
| power | `federation.lifecycle` | `members` | resist-long | 23 | 0.0866 | 0.00191 | ×45.40 ** |
| power | `faction.nation_control_changed` | `nation` | resist-long | 1613 | 0.00132 | 0.00228 | ÷1.73 |
| power | `nation.claims_changed` | `nation` | resist-long | 22 | 0.00538 | 0.00191 | ×2.82 |
| power | `nation.executive_change_recorded` | `nation` | resist-long | 411 | 0.00126 | 0.00228 | ÷1.80 |
| power | `nation.statistic_shifted` | `nation` | resist-long | 819 | 0.00266 | 0.00191 | ×1.39 |
| power | `faction.takeover` | `targets` | resist-long | 360 | 0.00132 | 0.00228 | ÷1.73 |
| power | `faction.takeover_wave` | `targets` | resist-long | 47 | 0.0209 | 0.00191 | ×10.96 ** |
| power | `nation.merger` | `targets` | resist-long | 35 | 0.00612 | 0.00191 | ×3.21 ** |
| power | `war.arc` | `war_sides` | resist-long | 64 | 0.141 | 0.00191 | ×73.85 ** |
| population | `nation.cession` | `regions` | protectorate | 11 | 0.00252 | 0.00215 | ×1.17 |
| population | `nation.claims_declared` | `regions` | protectorate | 15 | 0.00296 | 0.00203 | ×1.46 |
| population | `nation.expansion` | `regions` | protectorate | 4 | 0.0165 | 0.00203 | ×8.12 ** |
| population | `nation.annexation` | `territory` | protectorate | 4 | 0.000722 | 0.00264 | ÷3.65 ** |
| population | `nation.independence` | `territory` | protectorate | 1 | 0.00744 | 0.00203 | ×3.66 ** |
| population | `nation.territory_gained` | `territory` | protectorate | 24 | 0.00276 | 0.00203 | ×1.36 |
| population | `nation.territory_lost` | `territory` | protectorate | 45 | 0.00154 | 0.00264 | ÷1.71 |
| population | `nation.unification` | `territory` | protectorate | 16 | 0.00137 | 0.00264 | ÷1.92 |
| population | `region.nation_changed` | `territory` | protectorate | 114 | 0.00145 | 0.00264 | ÷1.82 |
| population | `nation.cession` | `regions` | resist-long | 33 | 0.00106 | 0.00295 | ÷2.77 |
| population | `nation.claims_declared` | `regions` | resist-long | 79 | 0.00255 | 0.00264 | ÷1.04 |
| population | `nation.expansion` | `regions` | resist-long | 9 | 0.0538 | 0.00224 | ×24.07 ** |
| population | `nation.annexation` | `territory` | resist-long | 35 | 0.00131 | 0.00295 | ÷2.25 |
| population | `nation.independence` | `territory` | resist-long | 32 | 0.00335 | 0.00224 | ×1.50 |
| population | `nation.territory_gained` | `territory` | resist-long | 111 | 0.00335 | 0.00224 | ×1.50 |
| population | `nation.territory_lost` | `territory` | resist-long | 170 | 0.00193 | 0.00295 | ÷1.53 |
| population | `nation.unification` | `territory` | resist-long | 35 | 0.00713 | 0.00224 | ×3.19 ** |
| population | `region.nation_changed` | `territory` | resist-long | 383 | 0.00139 | 0.00295 | ÷2.12 |
| organization | `organization.assigned_councilor_changed` | `organization` | protectorate | 1616 | 0.000705 | – | – |
| organization | `organization.assigned_councilor_changed` | `organization` | resist-long | 3836 | 0.000793 | – | – |
| hab | `faction.colonisation_wave` | `colony` | protectorate | 15 | 0.0152 | 0.00665 | ×2.28 |
| hab | `faction.first_hab_on_body` | `hab` | protectorate | 82 | 0.00943 | 0.00665 | ×1.42 |
| hab | `hab.appeared` | `hab` | protectorate | 184 | 0.00943 | 0.00665 | ×1.42 |
| hab | `hab.destroyed` | `hab` | protectorate | 21 | 0.00386 | 0.00943 | ÷2.44 |
| hab | `hab.faction_changed` | `hab` | protectorate | 4 | 0.00228 | 0.00943 | ÷4.13 ** |
| hab | `faction.colonisation_wave` | `colony` | resist-long | 51 | 0.00873 | 0.00448 | ×1.95 |
| hab | `faction.first_hab_on_body` | `hab` | resist-long | 212 | 0.00223 | 0.00591 | ÷2.65 |
| hab | `hab.appeared` | `hab` | resist-long | 375 | 0.0054 | 0.00499 | ×1.08 |
| hab | `hab.destroyed` | `hab` | resist-long | 114 | 0.00641 | 0.00448 | ×1.43 |
| hab | `hab.faction_changed` | `hab` | resist-long | 26 | 0.00356 | 0.00591 | ÷1.66 |
| fleet | `faction.fleet_buildup` | `new_ships` | protectorate | 6 | 0.0164 | – | – |
| fleet | `faction.fleet_buildup` | `new_ships` | resist-long | 86 | 0.0331 | – | – |
| battle | `faction.combat_recorded` | `combat` | protectorate | 17 | 0.00459 | – | – |
| battle | `faction.combat_recorded` | `combat` | resist-long | 152 | 0.0268 | – | – |
| faction | `councilor.faction_changed` | `left_faction` | protectorate | 7 | 0.0618 | – | – |
| faction | `councilor.faction_changed` | `left_faction` | resist-long | 10 | 0.0797 | – | – |
| nuclear | `nation.nuclear_armament` | `nuclear_arc` | protectorate | 1 | 0.025 | 0.435 | ÷17.39 ** |
| nuclear | `nation.nuclear_disarmament` | `nuclear_arc` | protectorate | 1 | 0.435 | 0.025 | ×17.39 ** |
| nuclear | `nation.nuclear_armament` | `nuclear_arc` | resist-long | 9 | 0.0208 | 0.0275 | ÷1.32 |
| nuclear | `nation.nuclear_buildup` | `nuclear_arc` | resist-long | 3 | 0.0222 | 0.0268 | ÷1.21 |
| nuclear | `nation.nuclear_disarmament` | `nuclear_arc` | resist-long | 5 | 0.0328 | 0.0215 | ×1.52 |

### The kinds beyond a factor of three

| Measure | Kind | Stake | protectorate: ratio (events with a share) | resist-long: ratio (events with a share) | Beyond three in |
| --- | --- | --- | ---: | ---: | --- |
| power | `nation.demobilization` | `actor` | ×43.9 (1) | ×59.1 (3) | both |
| power | `nation.economic_trajectory` | `actor` | ÷2.7 (4) | ÷3.3 (20) | resist-long |
| power | `nation.government_shift` | `actor` | ÷1.7 (15) | ÷4.1 (15) | resist-long |
| power | `nation.inequality_shift` | `actor` | ×1.3 (9) | ÷3.6 (14) | resist-long |
| power | `nation.military_buildup` | `actor` | ×20.0 (1) | ×36.8 (3) | both |
| power | `nation.miltech_shift` | `actor` | ÷7.2 (2) | ÷7.4 (8) | both |
| power | `nation.navy_established` | `actor` | ×6.0 (4) | ×6.4 (6) | both |
| power | `nation.breakaway` | `independent_nation` | ×3.7 (1) | ×8.3 (9) | both |
| power | `federation.lifecycle` | `members` | ×5.0 (12) | ×45.4 (23) | both |
| power | `faction.takeover_wave` | `targets` | ×15.7 (43) | ×11.0 (47) | both |
| power | `nation.merger` | `targets` | ÷2.0 (16) | ×3.2 (35) | resist-long |
| power | `war.arc` | `war_sides` | ×64.2 (11) | ×73.8 (64) | both |
| population | `nation.expansion` | `regions` | ×8.1 (4) | ×24.1 (9) | both |
| population | `nation.annexation` | `territory` | ÷3.7 (4) | ÷2.3 (35) | protectorate |
| population | `nation.independence` | `territory` | ×3.7 (1) | ×1.5 (32) | protectorate |
| population | `nation.unification` | `territory` | ÷1.9 (16) | ×3.2 (35) | resist-long |
| hab | `hab.faction_changed` | `hab` | ÷4.1 (4) | ÷1.7 (26) | protectorate |
| nuclear | `nation.nuclear_armament` | `nuclear_arc` | ÷17.4 (1) | ÷1.3 (9) | protectorate |
| nuclear | `nation.nuclear_disarmament` | `nuclear_arc` | ×17.4 (1) | ×1.5 (5) | protectorate |

- **Sums of nations beside one nation, on nation power.** `war.arc` (`war_sides`: every attacker and defender),
  `federation.lifecycle` (`members`: every nation that was a member) and `faction.takeover_wave` (`targets`: every
  nation the wave took) are above their siblings by 5 to 74 times in both campaigns. `faction.takeover` and
  `nation.merger` share the `targets` stake with the wave and sit with the one-nation kinds: 0.0017 and 0.0013 for a
  takeover against 0.027 and 0.021 for a wave.
- **One nation, but only large ones.** `nation.demobilization`, `nation.military_buildup` and
  `nation.navy_established` take one nation each and are 6 to 59 times above their siblings in both campaigns, on 1
  to 6 events each. `nation.breakaway` is above on 1 and 9 events.
- **One nation, but small ones.** `nation.miltech_shift` is 7 times below its siblings in both campaigns, on 2 and 8
  events.
- **A share of a share.** `control_point.controller_changed` divides the nation's share by its control points. Its
  median, 0.0008 in both campaigns, is 2.6 and 3.0 times below its siblings: inside the factor of three, and the
  lowest of the kinds with volume.
- **On population**, `nation.expansion` (`regions`: every region the expansion lists) is 8 and 24 times above its
  siblings, on 4 and 9 events. `nation.cession` and `nation.claims_declared` use the same stake and are not.
- **On hab**, no kind is beyond three in both campaigns. `faction.colonisation_wave`, which sums the habs of its
  wave, is 2.3 and 2.0 times above.
- **On nuclear share**, the two `protectorate` kinds have one event each.
- **Fleet, battle, organization and faction** each have one kind that shows a share, so nothing stands beside it.

### By stake

Every event of the kinds on one stake, per campaign, with the stake's median against the median of the measure's most
frequent stake.

| Measure | Stake | Kinds | Campaign | With a share | P10 | P50 | P90 | Max | P50 against the measure's most frequent stake | At or below the fall cut-off | Between | At or above the rise cut-off |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| power | `actor` | 11 | protectorate | 321 | 0.000292 | 0.00146 | 0.0199 | 0.161 | ÷1.2 `nation` | 89 | 232 | 0 |
| power | `actor` | 11 | resist-long | 462 | 0.000217 | 0.00135 | 0.0209 | 0.259 | ÷1.1 `nation` | 138 | 322 | 2 |
| power | `belligerents` | 1 | protectorate | 0 | | | | | | | | |
| power | `belligerents` | 1 | resist-long | 0 | | | | | | | | |
| power | `control_point` | 1 | protectorate | 936 | 0.000225 | 0.000798 | 0.00553 | 0.0348 | ÷2.2 `nation` | 298 | 638 | 0 |
| power | `control_point` | 1 | resist-long | 1062 | 0.000181 | 0.000769 | 0.00649 | 0.0266 | ÷2.0 `nation` | 409 | 653 | 0 |
| power | `independent_nation` | 2 | protectorate | 1 | 0.00646 | 0.00646 | 0.00646 | 0.00646 | ×3.8 `nation` | 0 | 1 | 0 |
| power | `independent_nation` | 2 | resist-long | 32 | 0.000729 | 0.00324 | 0.0289 | 0.185 | ×2.1 `nation` | 2 | 29 | 1 |
| power | `members` | 1 | protectorate | 12 | 0.00185 | 0.00874 | 0.16 | 0.163 | ×5.1 `nation` | 0 | 12 | 0 |
| power | `members` | 1 | resist-long | 23 | 0.00898 | 0.0866 | 0.183 | 0.611 | ×55.8 `nation` | 0 | 20 | 3 |
| power | `nation` | 7 | protectorate | 1842 | 0.000299 | 0.00172 | 0.0194 | 0.159 | most frequent | 426 | 1416 | 0 |
| power | `nation` | 7 | resist-long | 2865 | 0.000273 | 0.00155 | 0.0199 | 0.202 | most frequent | 739 | 2122 | 4 |
| power | `targets` | 3 | protectorate | 397 | 0.000332 | 0.00206 | 0.0235 | 0.209 | ×1.2 `nation` | 80 | 316 | 1 |
| power | `targets` | 3 | resist-long | 442 | 0.000267 | 0.00172 | 0.0267 | 0.259 | ×1.1 `nation` | 110 | 330 | 2 |
| power | `war_sides` | 1 | protectorate | 11 | 0.0366 | 0.112 | 0.139 | 0.218 | ×65.1 `nation` | 0 | 10 | 1 |
| power | `war_sides` | 1 | resist-long | 64 | 0.0485 | 0.141 | 0.276 | 0.495 | ×90.8 `nation` | 0 | 37 | 27 |
| population | `regions` | 3 | protectorate | 30 | 0.000448 | 0.00296 | 0.0267 | 0.0795 | ×1.9 `territory` | 3 | 27 | 0 |
| population | `regions` | 3 | resist-long | 121 | 0.000139 | 0.00194 | 0.0538 | 0.235 | ×1.1 `territory` | 34 | 86 | 1 |
| population | `territory` | 6 | protectorate | 204 | 0.000149 | 0.00154 | 0.0097 | 0.165 | most frequent | 50 | 154 | 0 |
| population | `territory` | 6 | resist-long | 766 | 0.000267 | 0.00184 | 0.0112 | 0.162 | most frequent | 146 | 620 | 0 |
| organization | `organization` | 1 | protectorate | 1616 | 0.000331 | 0.000705 | 0.00298 | 0.00829 | most frequent | 714 | 902 | 0 |
| organization | `organization` | 1 | resist-long | 3836 | 0.000298 | 0.000793 | 0.00285 | 0.00794 | most frequent | 1808 | 2028 | 0 |
| hab | `colony` | 1 | protectorate | 15 | 0.00529 | 0.0152 | 0.13 | 0.32 | ×1.6 `hab` | 0 | 14 | 1 |
| hab | `colony` | 1 | resist-long | 51 | 0.0018 | 0.00873 | 0.0604 | 0.36 | ×2.0 `hab` | 0 | 50 | 1 |
| hab | `hab` | 4 | protectorate | 291 | 0.00228 | 0.00943 | 0.04 | 0.36 | most frequent | 0 | 290 | 1 |
| hab | `hab` | 4 | resist-long | 727 | 0.000885 | 0.00437 | 0.0175 | 0.2 | most frequent | 53 | 674 | 0 |
| fleet | `fleet` | 1 | protectorate | 0 | | | | | | | | |
| fleet | `fleet` | 1 | resist-long | 0 | | | | | | | | |
| fleet | `new_ships` | 1 | protectorate | 6 | 0.0106 | 0.0164 | 0.0604 | 0.0604 | most frequent | 0 | 6 | 0 |
| fleet | `new_ships` | 1 | resist-long | 86 | 0.00868 | 0.0331 | 0.102 | 0.274 | most frequent | 0 | 84 | 2 |
| battle | `combat` | 1 | protectorate | 17 | 0.00325 | 0.00459 | 0.0492 | 0.0567 | most frequent | 0 | 17 | 0 |
| battle | `combat` | 1 | resist-long | 152 | 0.00245 | 0.0268 | 0.0734 | 0.178 | most frequent | 3 | 119 | 30 |
| faction | `left_faction` | 1 | protectorate | 7 | 0.0368 | 0.0618 | 0.195 | 0.195 | most frequent | 0 | 7 | 0 |
| faction | `left_faction` | 1 | resist-long | 10 | 0.0332 | 0.0797 | 0.109 | 0.142 | most frequent | 0 | 10 | 0 |
| nuclear | `nuclear_arc` | 3 | protectorate | 2 | 0.025 | 0.025 | 0.435 | 0.435 | most frequent | 0 | 1 | 1 |
| nuclear | `nuclear_arc` | 3 | resist-long | 17 | 0.0164 | 0.0208 | 0.117 | 0.389 | most frequent | 0 | 16 | 1 |

## 5. The largest shares against the share needed to rise

### The cut-offs and the events

| Measure | Reference | Falls at or below | Rises at or above | Campaign | Largest share on an event (kind) | Events at or above the rise cut-off | Events at or below the fall cut-off |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |
| power | 0.01 | 0.000562 | 0.178 | protectorate | 0.218 (`war.arc`) | 2 of 3520 | 893 of 3520 |
| power | 0.01 | 0.000562 | 0.178 | resist-long | 0.611 (`federation.lifecycle`) | 39 of 4950 | 1398 of 4950 |
| population | 0.01 | 0.000562 | 0.178 | protectorate | 0.165 (`nation.unification`) | 0 of 234 | 53 of 234 |
| population | 0.01 | 0.000562 | 0.178 | resist-long | 0.235 (`nation.expansion`) | 1 of 887 | 180 of 887 |
| organization | 0.01 | 0.000562 | 0.178 | protectorate | 0.00829 (`organization.assigned_councilor_changed`) | 0 of 1616 | 714 of 1616 |
| organization | 0.01 | 0.000562 | 0.178 | resist-long | 0.00794 (`organization.assigned_councilor_changed`) | 0 of 3836 | 1808 of 3836 |
| hab | 0.015 | 0.000844 | 0.267 | protectorate | 0.36 (`faction.first_hab_on_body`) | 2 of 306 | 0 of 306 |
| hab | 0.015 | 0.000844 | 0.267 | resist-long | 0.36 (`faction.colonisation_wave`) | 1 of 778 | 53 of 778 |
| fleet | 0.01 | 0.000562 | 0.178 | protectorate | 0.0604 (`faction.fleet_buildup`) | 0 of 6 | 0 of 6 |
| fleet | 0.01 | 0.000562 | 0.178 | resist-long | 0.274 (`faction.fleet_buildup`) | 2 of 86 | 0 of 86 |
| battle | 0.0033 | 0.000186 | 0.0587 | protectorate | 0.0567 (`faction.combat_recorded`) | 0 of 17 | 0 of 17 |
| battle | 0.0033 | 0.000186 | 0.0587 | resist-long | 0.178 (`faction.combat_recorded`) | 30 of 152 | 3 of 152 |
| faction | 0.143 | 0.00803 | 2.54 | protectorate | 0.195 (`councilor.faction_changed`) | 0 of 7 | 0 of 7 |
| faction | 0.143 | 0.00803 | 2.54 | resist-long | 0.142 (`councilor.faction_changed`) | 0 of 10 | 0 of 10 |
| nuclear | 0.01 | 0.000562 | 0.178 | protectorate | 0.435 (`nation.nuclear_disarmament`) | 1 of 2 | 0 of 2 |
| nuclear | 0.01 | 0.000562 | 0.178 | resist-long | 0.389 (`nation.nuclear_disarmament`) | 1 of 17 | 0 of 17 |

### The largest share one entity holds

Read at every save. **Saves with an entity at or above the rise cut-off** says how often any kind that takes one
entity could rise at all.

| Measure | Entity | Rises at or above | Campaign | Largest share (save, who) | Largest ÷ rise cut-off | Smallest of the per-save largest (save) | Saves with an entity at or above the rise cut-off | Most such entities in one save | Entities per save | Median entity's share, per save | Entities at or below the fall cut-off, per save |
| --- | --- | ---: | --- | --- | ---: | --- | ---: | ---: | --- | --- | --- |
| power | nation | 0.178 | protectorate | 0.161 (2027-10-01, China) | 0.90 | 0.131 (2035-06-16) | 0 of 25 | 0 | 155 to 174 | 0.00109 to 0.00135 | 28 % to 34 % |
| power | nation | 0.178 | resist-long | 0.264 (2046-02-22, Pan-Asian Combine) | 1.48 | 0.153 (2031-09-16) | 20 of 63 | 2 | 53 to 174 | 0.000694 to 0.00126 | 31 % to 44 % |
| population | region | 0.178 | protectorate | 0.0318 (2026-02-13, New Delhi) | 0.18 | 0.0312 (2032-09-01) | 0 of 25 | 0 | 363 to 363 | 0.00138 to 0.00144 | 27 % to 28 % |
| population | region | 0.178 | resist-long | 0.0318 (2026-08-01, New Delhi) | 0.18 | 0.031 (2045-11-01) | 0 of 63 | 0 | 363 to 363 | 0.00138 to 0.00143 | 27 % to 28 % |
| organization | organization | 0.178 | protectorate | 0.00829 (2026-02-13, Central Intelligence Agency) | 0.05 | 0.00271 (2034-09-16) | 0 of 25 | 0 | 270 to 699 | 0.0012 to 0.00369 | 0 % to 38 % |
| organization | organization | 0.178 | resist-long | 0.00794 (2026-08-01, Central Intelligence Agency) | 0.04 | 0.0025 (2045-11-01) | 0 of 63 | 0 | 292 to 813 | 0.00111 to 0.00353 | 0 % to 36 % |
| hab | hab, any holder | 0.267 | protectorate | 0.36 (2026-02-13, Alien Surface Base Alpha, alien) | 1.35 | 0.0185 (2035-06-16) | 12 of 25 | 14 | 6 to 169 | 0.00823 to 0.16 | 0 % to 0 % |
| hab | hab, any holder | 0.267 | resist-long | 0.36 (2026-08-01, Alien Surface Base Alpha, alien) | 1.35 | 0.00626 (2046-10-08) | 5 of 63 | 9 | 11 to 273 | 0.00404 to 0.04 | 0 % to 29 % |
| hab | hab, human-held | 0.267 | protectorate | 0.0678 (2029-12-01, Uluru Base) | 0.25 | 0.0143 (2033-09-16) | 0 of 25 | 0 | 2 to 145 | 0.00417 to 0.04 | 0 % to 0 % |
| hab | hab, human-held | 0.267 | resist-long | 0.04 (2026-08-01, The International Space Station) | 0.15 | 0.00626 (2046-10-08) | 0 of 63 | 0 | 5 to 251 | 0.00212 to 0.04 | 0 % to 32 % |
| fleet | ship or fleet, any holder | 0.178 | protectorate | 0.167 (2035-06-16, Victor-14, alien) | 0.94 | 0.00406 (2026-02-13) | 0 of 25 | 0 | 11 to 207 | 0.00406 to 0.00952 | 0 % to 0 % |
| fleet | ship or fleet, any holder | 0.178 | resist-long | 0.349 (2040-10-16, Victor-215, alien) | 1.96 | 0.005 (2026-08-01) | 19 of 63 | 3 | 10 to 681 | 0.00143 to 0.005 | 0 % to 13 % |
| fleet | ship or fleet, human-held | 0.178 | protectorate | 0.0327 (2033-09-16, Papa-17) | 0.18 | 0.00207 (2031-06-01) | 0 of 25 | 0 | 2 to 65 | 0.00177 to 0.00272 | 0 % to 0 % |
| fleet | ship or fleet, human-held | 0.178 | resist-long | 0.349 (2040-02-16, an unnamed fleet) | 1.96 | 0.00357 (2031-01-14) | 13 of 63 | 2 | 9 to 417 | 0.00103 to 0.00465 | 0 % to 12 % |
| fleet | fleet, human-held | 0.178 | protectorate | 0.0327 (2033-09-16) | 0.18 | 0.00207 (2031-06-01) | 0 of 25 | 0 | 1 to 19 | 0.00177 to 0.00524 | 0 % to 0 % |
| fleet | fleet, human-held | 0.178 | resist-long | 0.349 (2040-02-16) | 1.96 | 0.00357 (2031-01-14) | 13 of 63 | 2 | 3 to 51 | 0.00103 to 0.0106 | 0 % to 10 % |
| faction | faction | 2.54 | protectorate | 0.416 (2035-06-16, the Protectorate) | 0.16 | 0.0152 (2026-02-13) | 0 of 25 | 0 | 8 to 8 | 0.0031 to 0.0916 | 0 % to 50 % |
| faction | faction | 2.54 | resist-long | 0.875 (2046-02-22, the Resistance) | 0.34 | 0.118 (2026-08-01) | 0 of 63 | 0 | 8 to 8 | 0.0155 to 0.105 | 12 % to 12 % |

- **Nation power.** In `protectorate` the largest nation holds 0.131 to 0.161 (China, on 2027-10-01, at the most):
  0.74 to 0.90 of the rise cut-off. In `resist-long` the Pan-Asian Combine holds the cut-off or more from the save of
  2039-03-16 and the European Union from 2045-08-01; no other nation does. Between 53 and 174 nations hold a share in
  `resist-long` and between 155 and 174 in `protectorate`.
- **Population.** The largest region is New Delhi at 0.031 to 0.032 in both campaigns, 0.18 of the rise cut-off. The
  one event at or above it is a `nation.expansion` of 0.235 in `resist-long`.
- **Organization.** The largest organization holds 0.0083 and 0.0079 at the first save, and 0.0027 and 0.0025 in the
  save where the largest is smallest; the campaigns hold 270 to 699 and 292 to 813 organizations. The reference is
  0.01, so every event is below it.
- **Hab.** No hab at or above the rise cut-off is human-held. The largest is an alien base at 0.36, a tier² of 9 over
  the floor of 25, at the first save of each campaign, and one save holds up to 14 and 9 such habs. The largest
  human-held hab holds 0.068 and 0.040. Three events are at or above the cut-off, all the alien faction's: a
  `faction.first_hab_on_body` (2026) and a `faction.colonisation_wave` (2027) in `protectorate`, and a
  `faction.colonisation_wave` (2027) in `resist-long`.
- **Fleet.** A human-held fleet reaches 0.033 in `protectorate` and 0.349 in `resist-long`, where one is at or above
  the cut-off in 13 of 63 saves. `fleet.faction_changed`, the one kind that takes a fleet, has no event.
  `faction.fleet_buildup` sums the ships it cites and passes the cut-off twice in `resist-long`.
- **Faction.** The largest faction holds 0.416 in `protectorate` and 0.875 in `resist-long`. The rise cut-off, 2.54,
  is more than the whole.
- **Battle and nuclear share** have no share held by an entity: a battle's share is its contested mass over the
  world's ship mass, and a nuclear share is an arc's net move over the world's warheads. The largest on an event is
  0.057 and 0.178 for a battle and 0.435 and 0.389 for a nuclear arc. The world holds 39 to 75 warheads over
  `protectorate` and 44 to 72 over `resist-long` at the saves, so one warhead is a share of 0.013 to 0.026, above the
  reference. The smallest arc in the table is 0.0164, and no arc is lowered.

## 6. Coverage

Thin, as [Sample coverage: are the current sample campaigns enough](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/539)
defines it: only one sample campaign shows it, or it has fewer than 5 occurrences in total. The first coverage column
counts the kind's events; the second counts only those with a share, which is what a scaling is judged on.

| Kind | Measure | protectorate: events (with a share) | resist-long: events (with a share) | Total events (with a share) | Coverage of the kind | Coverage of its shares |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `nation.cohesion_shift` | power | 73 (73) | 92 (92) | 165 (165) |  |  |
| `nation.demobilization` | power | 1 (1) | 3 (3) | 4 (4) | thin | thin |
| `nation.diplomatic_realignment` | power | 104 (104) | 202 (202) | 306 (306) |  |  |
| `nation.economic_trajectory` | power | 4 (4) | 20 (20) | 24 (24) |  |  |
| `nation.education_shift` | power | 0 (0) | 0 (0) | 0 (0) | not shown | not shown |
| `nation.government_shift` | power | 15 (15) | 15 (15) | 30 (30) |  |  |
| `nation.inequality_shift` | power | 9 (9) | 14 (14) | 23 (23) |  |  |
| `nation.military_buildup` | power | 1 (1) | 3 (3) | 4 (4) | thin | thin |
| `nation.miltech_shift` | power | 2 (2) | 8 (8) | 10 (10) |  |  |
| `nation.navy_established` | power | 4 (4) | 6 (6) | 10 (10) |  |  |
| `nation.unrest_shift` | power | 108 (108) | 99 (99) | 207 (207) |  |  |
| `nation.relation_changed` | power | 950 (0) | 2814 (0) | 3764 (0) |  | not shown |
| `control_point.controller_changed` | power | 936 (936) | 1062 (1062) | 1998 (1998) |  |  |
| `nation.breakaway` | power | 1 (1) | 9 (9) | 10 (10) |  |  |
| `nation.release` | power | 0 (0) | 23 (23) | 23 (23) | thin | thin |
| `federation.lifecycle` | power | 12 (12) | 23 (23) | 35 (35) |  |  |
| `faction.nation_control_changed` | power | 1121 (1121) | 1613 (1613) | 2734 (2734) |  |  |
| `nation.appeared` | power | 0 (0) | 0 (0) | 0 (0) | not shown | not shown |
| `nation.claims_changed` | power | 19 (7) | 79 (22) | 98 (29) |  |  |
| `nation.disappeared` | power | 0 (0) | 0 (0) | 0 (0) | not shown | not shown |
| `nation.executive_change_recorded` | power | 331 (331) | 411 (411) | 742 (742) |  |  |
| `nation.federation_changed` | power | 0 (0) | 0 (0) | 0 (0) | not shown | not shown |
| `nation.statistic_shifted` | power | 383 (383) | 819 (819) | 1202 (1202) |  |  |
| `faction.takeover` | power | 338 (338) | 360 (360) | 698 (698) |  |  |
| `faction.takeover_wave` | power | 43 (43) | 47 (47) | 90 (90) |  |  |
| `nation.merger` | power | 16 (16) | 35 (35) | 51 (51) |  |  |
| `war.arc` | power | 11 (11) | 64 (64) | 75 (75) |  |  |
| `nation.cession` | population | 11 (11) | 33 (33) | 44 (44) |  |  |
| `nation.claims_declared` | population | 15 (15) | 79 (79) | 94 (94) |  |  |
| `nation.expansion` | population | 4 (4) | 9 (9) | 13 (13) |  |  |
| `nation.annexation` | population | 4 (4) | 35 (35) | 39 (39) |  |  |
| `nation.independence` | population | 1 (1) | 32 (32) | 33 (33) |  |  |
| `nation.territory_gained` | population | 24 (24) | 111 (111) | 135 (135) |  |  |
| `nation.territory_lost` | population | 45 (45) | 170 (170) | 215 (215) |  |  |
| `nation.unification` | population | 16 (16) | 35 (35) | 51 (51) |  |  |
| `region.nation_changed` | population | 114 (114) | 383 (383) | 497 (497) |  |  |
| `organization.assigned_councilor_changed` | organization | 1616 (1616) | 3836 (3836) | 5452 (5452) |  |  |
| `faction.colonisation_wave` | hab | 15 (15) | 51 (51) | 66 (66) |  |  |
| `faction.first_hab_on_body` | hab | 82 (82) | 212 (212) | 294 (294) |  |  |
| `hab.appeared` | hab | 184 (184) | 375 (375) | 559 (559) |  |  |
| `hab.destroyed` | hab | 21 (21) | 114 (114) | 135 (135) |  |  |
| `hab.faction_changed` | hab | 4 (4) | 26 (26) | 30 (30) |  |  |
| `fleet.faction_changed` | fleet | 0 (0) | 0 (0) | 0 (0) | not shown | not shown |
| `faction.fleet_buildup` | fleet | 6 (6) | 86 (86) | 92 (92) |  |  |
| `faction.combat_recorded` | battle | 18 (17) | 174 (152) | 192 (169) |  |  |
| `councilor.faction_changed` | faction | 30 (7) | 49 (10) | 79 (17) |  |  |
| `nation.nuclear_armament` | nuclear | 1 (1) | 9 (9) | 10 (10) |  |  |
| `nation.nuclear_buildup` | nuclear | 0 (0) | 3 (3) | 3 (3) | thin | thin |
| `nation.nuclear_disarmament` | nuclear | 1 (1) | 5 (5) | 6 (6) |  |  |

| Measure | Kinds | Kinds shown | protectorate: events with a share | resist-long: events with a share | Coverage |
| --- | ---: | ---: | ---: | ---: | --- |
| power | 27 | 23 | 3520 | 4950 |  |
| population | 9 | 9 | 234 | 887 |  |
| organization | 1 | 1 | 1616 | 3836 |  |
| hab | 5 | 5 | 306 | 778 |  |
| fleet | 2 | 1 | 6 | 86 |  |
| battle | 1 | 1 | 17 | 152 |  |
| faction | 1 | 1 | 7 | 10 |  |
| nuclear | 3 | 3 | 2 | 17 |  |

- **Thin kinds:** `nation.demobilization` (4 events), `nation.military_buildup` (4), `nation.nuclear_buildup` (3,
  `resist-long` only) and `nation.release` (23, `resist-long` only).
- **Not shown:** `nation.appeared`, `nation.disappeared`, `nation.federation_changed`, `nation.education_shift` and
  `fleet.faction_changed`. The first two are the campaign defining kinds that
  [Calibration principles: what makes a level, a reference and a spread right](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/558)
  moves to a major base to rise by stake; the samples hold no share for either.
- **Shown without a share:** `nation.relation_changed`.
- **Measures:** none is thin by the rule. Fleet rests on one kind and 6 events in `protectorate`; faction on one
  kind and 7 and 10 events; nuclear share on 2 events in `protectorate`; battle on 17 events in `protectorate`
  against 152 in `resist-long`.
- **Time:** `protectorate` ends on 2035-06-16. Every later observation is `resist-long` alone, which includes every
  save in which a nation holds the rise cut-off or more.

## What could not be measured

- **How many entities a summed stake adds up.** The table keeps each event's share, not the entities behind it, so
  the number of nations in a war arc, a federation or a takeover wave is not reported.
- **The largest entity share between saves.** It is read at 25 and 63 saves.
- **An entity share for battle and nuclear share.** Neither measure has one; section 5 gives the largest share on an
  event instead.
- **The five kinds without an event and the `belligerents` stake.** There is nothing to read.
- **Why two kinds on one stake differ.** The tables show that `nation.navy_established` takes larger nations than
  `nation.unrest_shift`; whether that is the narrative rule's own threshold was not traced.
- **Draft stakes.** None is declared, so none was measured.
