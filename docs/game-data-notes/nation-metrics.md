# Nation statistics: long series, bands and routine magnitudes

Evidence base for the redesign of the nation metric rules (roadmap, *Nation metrics redesign*). It records how the
nation statistics behave between saves and within one save, what the save carries beyond the scalar values, and
how often the game's own value bands are crossed, so that each metric can get a rule shaped by its behaviour. It
follows the rules of the [notes README](README.md): structure, counts, magnitudes and dates only; reason
identifiers and template vocabulary are named, nations and players are not.

Observed on 2026-10-23 in thirteen private complete saves of three campaigns, read from the raw JSON:

| Campaign | Build | Saves | Game dates | Intervals (days) |
| --- | --- | --- | --- | --- |
| Appease | newer | 3 | 2026-02 to 2026-03 | 7, 21 |
| Protectorate | newer | 5 | 2026-02 to 2027-07 | 61, 245, 106, 106 |
| Resist | older | 5 | 2045-08 to 2046-10 | 92, 21, 92, 228 |

The Appease and Protectorate campaigns start at the same game date with the same 174 nations holding regions;
Resist has 53. "Nation" below means a nation holding at least one region on both sides of an interval; placeholder
nations never change (see the
[metric shift magnitudes](higher-level-event-sources.md#observations-on-already-normalized-fields)).

## Summary

| Source | Normalized today? | What it carries | Status |
| --- | --- | --- | --- |
| `TINationState.tracker_PCGDP_ByQuarter` | Yes, unused | per-capita GDP for every quarter since campaign start | observed |
| `TINationState.tracker_*ChangeReason_AllTime` (6 maps) | Yes (`causes`) | cumulative per-cause change since campaign start; the start value is current value minus their sum | observed for education and GDP, with outliers for cohesion and unrest |
| `TINationState.history*` (20 arrays) | Acknowledged `derived_history` | 32 recent samples | observed; not a long series |
| `TINationState.historyWarStatus` | Acknowledged | unknown quantity | not the strength estimate below |
| `TIRegionState.populationInMillions` | Yes | the only population figure | observed |
| `TIRegionState.boostPerYear_dekatons`, `missionControl`, `antiSpaceDefenses`, `numSTOFighters` | Yes, unused | space-support assets per region | observed |
| `TIArmyState.deploymentType` | Yes, copied raw | `Standard` or `Naval`; navies are armies | observed |
| `TIRegionState.occupations`, `leadOccupier` | Yes (`occupations` as a nation -> fraction map) | occupation | observed; `leadOccupier` set only on a fully occupied region ([strength](#armies-navies-and-a-strength-estimate)) |

## Long series carried in one save

### Per-capita GDP by quarter

`tracker_PCGDP_ByQuarter` (shape in the [domain field map](domain-field-map.md)) is keyed by
`TITimeState.currentQuarterSinceStart`: the latest Resist save (quarter 83) carries 84 entries on 163 nations and 83
on 121 (those start at quarter 1); 11 nations carry negative keys and a list not in key order, 3 of them 28 and 3 of
them 44 quarters before the start already in the first Appease and Protectorate saves (*hypothesis*: template
history for nations the scenario can create). Quarter 0 is the campaign's first quarter: `daysInCampaign` 7121 at
2045-08-01 places the Resist start at 2026-02-01 and 78 quarters later is 2045-08. 140 nations have a stretch of
zeros inside a non-zero series (*hypothesis*: quarters in which the nation held no region). The other
`tracker_*_ByQuarter` members are `null` on every nation of both builds.

**Observed** (2026-10-29, all thirteen saves): `currentQuarterSinceStart` counts calendar quarters since the one the
campaign starts in, not three-month steps from the start date. With every campaign starting on 2026-02-01
(`currentDateTime` minus `daysInCampaign`, within a day), the counter was 1 on 2026-04-15, 3 on 2026-12-16, 6 on
2027-07-16, 78 on 2045-08-01 and 83 on 2046-10-08; three-month steps from 2026-02-01 would give 0, 3, 5, 78 and 82.
The save dated 2027-04-01 00:00 still had 4, so the counter rises during the quarter's first day, not at its start.
The largest key in every nation's series equalled the save's counter. `nation.pcgdp_trend` therefore dates quarter
`k` by the first day of the `k`-th calendar quarter after the start's (quarter 0 by the start itself).

Year-over-year change of the series in the latest Resist save, over the 9,673 nation-quarters where both ends are
non-zero: p1 -8.8 %, p5 -3.2 %, p10 -2.3 %, p50 0.0 %, p90 +4.5 %, p95 +6.7 %, p99 +14.4 %. Beyond ±10 %: 236 up,
59 down; beyond ±20 %: 44 up, 11 down; beyond ±30 %: 21 up, 8 down. The extremes were -81 % and +235 % on single
nations over three consecutive quarters each. Over 20 quarters (6,919 windows): p5 -16 %, p50 0 %, p95 +33 %;
117 windows above +50 %, 26 above +100 %, 130 below -25 %. Over the whole series (nations with more than 40 non-zero
quarters), the last-to-first ratio ranged from 0.50 (three nations at or below 0.55) to 3.24 (three above 2.7).

### Cumulative cause trackers reach back to the campaign start

For the 47 nations present with the same `templateName` and holding regions in both the first Appease save
(campaign day 1) and the first Resist save (day 7121, a different build), the Appease value plus the sum of the
Resist save's `tracker_<Statistic>ChangeReason_AllTime` map was compared with the Resist value:

| Statistic | median error | p90 | max |
| --- | --- | --- | --- |
| education | 0.000 | 0.000 | 0.000 |
| inequality | 0.000 | 0.000 | 2.33 |
| GDP (relative) | 1.7 % | 3.0 % | 8.1 % |
| democracy | 0.08 | 0.70 | 4.93 |
| cohesion | 0.04 | 7.20 | 10.10 |
| unrest | 0.00 | 1.81 | 12.63 |

So the maps are cumulative since the campaign start and a nation's start value is derivable from any single save
for education, GDP and, with outliers, democracy and inequality. *Hypothesis:* the cohesion and unrest outliers are
nations re-created or reset by the game (releases, dissolutions) whose maps were not reset with them; not checked.
Reasons seen in the maps beyond the ones already listed in the
[higher-level sources](higher-level-event-sources.md#observations-on-already-normalized-fields):
`DemReason_GovernmentPriority`, `DemReason_AtWar`, `UnrestReason_StabilizeMission`, `UnrestReason_OppressionPriority`,
`UnrestReason_EventEffect`.

### The `history*` arrays

All twenty `history*` arrays hold exactly 32 entries on every nation of every save, with values that differ from
the current scalar by at most a few per mille across the array. They are a rolling buffer of recent samples, not a
campaign series; they stay `derived_history`. `historyWarStatus` was 0 on most nations and took values from -586
to 1,849 on the others in the latest Resist save; it does not match the strength estimate below (negative on a
nation with armies and nuclear weapons, largest on a nation with four naval armies) and is left unexplained.

## Population

The nation has no population field; `populationInMillions` on its regions is the figure. Between consecutive saves
the change that territory does not explain (the later population, minus the population of regions gained, plus the
population of regions lost, relative to the earlier population, per year) was:

| Interval | p5 | p50 | p95 | min | max |
| --- | --- | --- | --- | --- | --- |
| Appease 7 d | -2.0 % | +4.3 % | +12.7 % | -2.9 % | +15.9 % |
| Appease 21 d | 0.0 % | 0.0 % | 0.0 % | -0.1 % | 0.0 % |
| Protectorate 61 to 245 d (4 intervals) | -0.39 % to -0.54 % | +0.95 % to +1.11 % | +2.77 % to +3.08 % | -1.2 % | +3.9 % |
| Resist 21 to 228 d (4 intervals) | -0.50 % to -0.76 % | +0.43 % to +0.71 % | +1.79 % to +2.78 % | -1.1 % | +3.6 % |

The 7-day figures are a daily step annualized; the 21-day Appease interval saw no population change at all
(*hypothesis*: population updates on a monthly tick). Over intervals of 61 days or more no nation lost more than
1.2 % a year of its population beyond territory. `nuclearDetonations` was 0 on every region of every save and
`TIGlobalValuesState.nuclearStrikes` was 0 throughout, so no depopulation event and no nuclear strike has been
observed; a depopulation threshold is a hypothesis until one is.

## Economic rates between saves

For nations whose regions did not change, annualized change per interval (Protectorate and Resist; the Appease
intervals are too short to annualize):

| Measure | p5 | p50 | p95 | extremes |
| --- | --- | --- | --- | --- |
| GDP | -0.6 % to -3.9 % | -0.8 % to +1.5 % | +6.4 % to +21.7 % | -29.2 % (one nation, 92 days), +70.7 % (one nation, 61 days) |
| per-capita GDP | -1.6 % to -5.0 % | -0.7 % to +1.5 % | +3.6 % to +20.8 % | -29.9 %, +69.2 % (the same two) |

The p95 of the Resist intervals (15 % to 21 % a year) is carried by a few small nations growing from a low base;
the Protectorate intervals sit at 4 % to 8 %. These are consistent with the quarterly series above.

## Value bands

The game labels each statistic's value with a band. The boundaries below are **published** ([README](README.md)):
the game's vocabulary as transcribed by the author from the Terra Invicta wiki (2026-10-23); no save carries them,
so they cannot be checked against one. The crossing counts are observed.

| Statistic | Boundaries (band begins at) |
| --- | --- |
| `unrest` | 1.5 Subversion, 3 Strife, 4.5 Insurgency, 6 Guerilla War, 7.5 Insurrection, 9 Civil War; below 1.5 Peaceful |
| `democracy` | 2 Authoritarian, 4 Anocracy, 6 Flawed Democracy, 8 Full Democracy; below 2 Totalitarian |
| `education` | 5 Developing, 8 Advanced; below 5 Limited (10 and above exceeds the real-world index the scale is built on) |
| `cohesion` | 1 Fractured, 2 Sectarian, 3 Polarized, 4 Competitive, 5 Diverse, 6 Integrated, 7 Homogenous, 8 Dominated, 9 Hegemonic, 10 Monolithic; below 1 Fragmented |
| `inequality` | 2 Low, 3 Moderate, 4 High, 5 Very High, 6 Extreme; below 2 Very Low |
| `militaryTechLevel` | 3 Atomic, 4 Information, 5 Robotics, 6 Invasion, 7 Fusion; below 3 Industrial |

### Crossings between consecutive saves

Nations whose band differed between the two saves of an interval (raw), then the same with a margin (the value
ends at least 0.25 beyond the boundary it crossed; 0.1 for military tech), then the margin crossings that still
crossed after subtracting the `*MovementToRestValue` delta of the interval from the later value (the *rest-value
filter*), then the margin crossings whose band still held at the following save:

| Interval | Statistic | raw | margin | after rest-value filter | held at next save |
| --- | --- | --- | --- | --- | --- |
| Appease 7 d | cohesion | 166 | 106 | 92 | 106 of 106 |
| Appease 7 d | unrest | 11 | 4 | 0 | 4 of 4 |
| Appease 7 d | democracy | 1 | 0 | | |
| Protectorate 61 d | unrest | 43 | 35 | | 25 of 35 |
| Protectorate 61 d | cohesion | 46 | 10 | | 10 of 10 |
| Protectorate 61 d | inequality, democracy, miltech | 3, 1, 1 | 0 | | |
| Protectorate 245 d | cohesion | 170 | 144 | 133 | 117 of 144 |
| Protectorate 245 d | unrest | 97 | 74 | 14 | 70 of 74 |
| Protectorate 245 d | inequality | 12 | 1 | | 1 of 1 |
| Protectorate 245 d | democracy, education, miltech | 6, 1, 1 | 0 | | |
| Protectorate 106 d | cohesion | 52 | 22 | | 22 of 22 |
| Protectorate 106 d | unrest | 49 | 14 | | 13 of 14 |
| Protectorate 106 d (last) | cohesion | 76 | 34 | 1 | |
| Protectorate 106 d (last) | unrest | 41 | 23 | 3 | |
| Resist 92 d | cohesion | 36 | 28 | 28 | 28 of 28 |
| Resist 92 d | unrest | 9 | 7 | 3 | 7 of 7 |
| Resist 21 d | unrest, cohesion, inequality | 5, 3, 1 | 0 | | |
| Resist 92 d (second) | cohesion | 10 | 2 | | 2 of 2 |
| Resist 92 d (second) | unrest | 4 | 3 | 2 | 1 of 3 |
| Resist 228 d | cohesion | 29 | 14 | 1 | |
| Resist 228 d | unrest | 12 | 5 | 2 | |
| Resist 228 d | inequality, miltech, education | 5, 1, 1 | 0 | | |

Observations behind the table:

- **Boundary flapping.** Unrest moves in 0.25 steps and sits on 1.25, 1.5 and 1.75 on most nations, so the 1.5
  boundary is crossed back and forth by dozens of nations per interval. Democracy and inequality crossings were
  values within 0.02 of a boundary moving across it (one nation crossed 4.0 in three successive intervals, 4.01 to
  4.00 to 4.02). With the margin, democracy, education and inequality crossings all but disappear: 0 or 1 per
  interval, and each of those was a move of 0.5 or more.
- **Unrest is mostly the game converging.** Of the margin crossings, the share of the interval's tracker delta under
  `UnrestReason_MovementToRestValue` had a median of 0.82 in Protectorate and 0.44 to 0.67 in Resist; the dominant
  reason of the survivors of the rest-value filter was `UnrestReason_OppressionPriority`,
  `UnrestReason_StabilizeMission` or `UnrestReason_EventEffect`. Under the filter the 245-day interval keeps 14 of
  74 crossings; two of them moved two bands.
- **Cohesion crosses bands routinely.** Its bands are one unit wide and it moved 1.1 on 166 of 174 nations in the
  7-day Appease interval, every one under `CohesionReason_Effect`; in the 245-day Protectorate interval 144 nations
  crossed with the margin, 74 of them two bands or more, again dominated by `CohesionReason_Effect` in both
  directions, which the rest-value filter does not remove. In the later Protectorate and Resist intervals the
  crossings are dominated by `CohesionReason_MovementToRestValue` (median share 0.84 to 0.85) and the filter removes
  nearly all (34 to 1, 14 to 1). Only the extremes (below 1, 9 and above) and multi-band moves not explained by the
  rest value are rare.
- **Rest-state caches do not predict persistence.** `unrestRestState_dailyCache` was in a different band from
  `unrest` on 105 of 174 nations and `cohesionRestState_dailyCache` on 161 of 174 in the 2026-12 Protectorate save;
  whether the rest state agreed with the new band changed the hold rate at the next save only from 56 % to 72 %
  (unrest) and from 67 % to 100 % on 13 cases (cohesion). The tracker-delta filter above is the usable test.
- **Military tech** crossed an age boundary on one nation per interval at most (one of them downward, 4.0 to 3.9).
  Bands in the latest saves: Protectorate 144 Atomic, 21 Information, 8 Industrial (174 nations); Resist 34 Atomic,
  13 Information, 5 Industrial, 1 Invasion (53 nations).
- **Education above 10** held on 14 nations in the first Resist save and 16 in the last (highest 12.6), none in
  Appease or Protectorate.

### Band shifts as built

The table is `analyzers/politics/bands.py`; `nation.band_crossed` applies the margin and the `nation.*_shift` rules
the rest-value filter, the hold and carrier suppression. Over the private saves (2026-10-24,
`events --narrative`, default settings), **observed**:

- `nation.band_crossed` per interval matched the margin column above to within a few nations (Protectorate 245 d:
  130 cohesion, 73 unrest, 1 inequality).
- `nation.unrest_shift`: 8 in the Protectorate 245-day interval, 0 to 2 elsewhere.
- `nation.cohesion_shift`: 31 in the Protectorate 245-day interval (the move must be two bands both with and
  without the rest-value delta, or cross 1 or 9), 4 in the Appease 7-day interval, 0 to 2 elsewhere. A
  cohesion move whose rest-value delta runs against it widens under the filter alone; requiring the unfiltered
  move to be two bands too keeps those out.
- No government, education, inequality or military-tech shift: the three margin crossings (one inequality in
  Protectorate, one inequality and one democracy in Resist) fell in the same interval as a takeover or release of
  their nation, whose `metric_shifts` carry them.

### Population and per-capita GDP as built

`nation.population_changed` and `nation.pcgdp_trend` with the analyzers' constants (residual of 5 % or 10 % a year;
20 quarters, +50 % / -25 %), and the `nation.population_collapse` and `nation.economic_trajectory` rules over them. Over the private saves (2026-10-29, `events --narrative`), **observed**:

- No `nation.population_changed` in any interval of any campaign, so no `nation.population_collapse`.
- No trend in Appease or Protectorate: their series hold at most seven quarters, short of a 20-quarter window.
- Resist: 15 `nation.pcgdp_trend` (13 boom, 2 slump), 10 of them `before_sequence`, forming 14 trajectories (one of
  them chains two booms of one nation); 4 promoted to `campaign_defining` as top-GDP nations.
- Of the nations whose whole-series ratio is at or below 0.55 (three) or above 2.7 (three), five appear as a
  trajectory of the matching direction. The sixth fell from 1 to 0.55 over the campaign without any 20-quarter
  window below -21 %: a gradual decline over more than five years is not a slump under this rule.
- Every trend quarter date lies within its interval or, for `before_sequence`, before the first save.

## Nuclear weapons and programs

The situation report reads each nation's warhead count from `TINationState.numNuclearWeapons`, an integer, **observed**
(2026-11-13) on every nation of every save of the Protectorate and Resist benchmark campaigns (positive on 169 of
3,675 and 27 of 270 nation rows, 0 on the rest), never absent. A nation whose save lacks the field is reported
unknown, not zero; that case occurs only in the synthetic fixtures.

`numNuclearWeapons` and `nuclearProgram` did not change in any Appease or Protectorate interval: 9 nations held
weapons (30, 28, 6, 3, 2, 2, 2, 1, 1) and 10 ran a program. In Resist, 5 nations held weapons in the first four saves
(37, 13, 5, 2, 2) and 8 ran a program; in the 228-day interval two nations went from 0 to 1 weapon with
`nuclearProgram` false to true in the same interval (the two 0 to 1 changes already noted in the
[higher-level sources](higher-level-event-sources.md)). The two largest 2026 arsenals belong to nations that in Resist
hold 0 weapons or have been absorbed, and the one still present holds 6 regions and about 28 % of its 2026 GDP, with
four nations of its former territory present as separate nations. `policy_noNukes` was false on every nation of
every save. The 32-sample `historyNukes` buffer cannot date these changes.

Read through the nuclear arcs (2026-10-29, `events --narrative`, default settings), **observed**: the last Resist
interval holds two `nation.nuclear_armament`, each citing a `nation.nuclear_program_changed` of its nation, both
`major` (GDP places 18 and 21). No buildup or disarmament in any interval of any campaign, and no
`nation.policy_changed`. The dismantling of the two largest 2026 arsenals predates the Resist saves and is not
datable from them.

## Space-support assets

Summing the region fields over a nation's regions:

| Save | top nation boost (dekatons/yr) | 2nd, 3rd | top nation mission control | 2nd, 3rd | top region boost |
| --- | --- | --- | --- | --- | --- |
| Appease and Protectorate first (2026-02) | 96.1 | 57.1, 7.0 | 6 | 3, 3 | 65.5 |
| Protectorate last (2027-07) | 96.1 | 57.7, 12.8 | 6 | 3, 3 | 65.5 |
| Resist first (2045-08) | 3,672.7 | 2,207.0, 1,557.4 | 365 | 278, 156 | 658.5 |
| Resist last (2046-10) | 3,672.7 | 1,916.2, 1,557.4 | 388 | 268, 167 | 658.5 |

Boost is flat on most nations and grew by 1 % to 15 % a year on the few building it (one nation 291.7 to 306.8 over
Resist); the one large drop (2,207 to 1,916) coincided with that nation's territory loss. Mission control on the four
largest holders moved 1 to 4 per quarter. `antiSpaceDefenses` was true on 4 regions and `numSTOFighters` non-zero on
5 in every Resist save, and on none in Appease or Protectorate. `TISpaceDefensesFacilityState` is a state type of its
own; the facility references on regions (`boostFacility`, `missionControlFacility`, `spaceDefenseFacility`) were
present on every region and were not decoded.

Read through the space-asset events and the situation reports (observed 2026-10-29): the Resist drop above is 13 %
over the last interval, in which that nation's regions fell from 98 to 94, below the 25 % a space-asset change needs,
so it shows in the reports' `boost` only. The changes that did pass in Resist came with territory: a boost rise from
8.4 to 225.1 had 99 % of it in regions gained, and most mission control moves were entirely regions changing hands.
Protectorate had five such changes, none of them territorial. Mission control is a small integer on most nations
(places 5 to 10 of Protectorate hold 1 or 2), so a top ten by it ties across its boundary; a ranking change counts
only nations clearly inside or outside the top.

## Armies, navies and a strength estimate

`TIArmyState.armyType` was `Human` on every army; `deploymentType` was `Standard` on 15 and `Naval` on 12 of the 27
armies in Appease and the first two Protectorate saves (30 in the last three: 18 and 12), and 10 and 9 of 19 in
Resist. Both kinds appear in the nation's `armies` list (9 of 20 list entries in the latest Resist save are naval).
`strength` is a fraction (below 1 on 0 to 4 armies per save). Army counts did not change in any Resist interval and
grew by 3 in one Protectorate interval. No region carried an occupation in the thirteen saves above. A later read
of all nineteen Protectorate and five Resist saves (2026-11-07) found occupations in eleven of them: one or two
regions per save, each with a single occupier holding 0.05 to 1.0 of the region. `leadOccupier` was set on one
region only, the one occupied at 1.0, and named the same nation as the occupation; it is `null` on every partly
occupied region.

The author's strength formula (regions not occupied × military tech × 0.7, plus standard armies × military tech × 3 ×
mean remaining strength, plus naval armies, minus unrest, plus 100 if any nuclear weapon, plus 5 per weapon) ranks
the nations differently from GDP: in the last Protectorate save the four largest economies hold the first four places
in a different order (338, 298, 227, 199), and in the last Resist save the first three (586, 336, 329) are followed by
two nations with one weapon each at places 6 and 7, ahead of larger conventional powers, because any arsenal adds
100. The formula is **published**: the game's own strength estimate as the Terra Invicta wiki states it, transcribed
by the author (2026-10-23). No save field carries its result (`historyWarStatus` is not it), so it cannot be checked
against one; the rankings above are observed applications of it, and the situation reports' `strength` reproduces
them (338.0, 298.2, 227.5, 199.2 and 585.9, 335.8, 329.0, with the two one-weapon nations at places 6 and 7; observed
2026-10-29). The wiki does not say how a partly occupied region counts; the estimate weighs each region by one minus
its occupiers' summed fractions (*hypothesis*: not checkable against a save), so a fully occupied region counts
nothing. With that rule every nation holding regions has a strength in all 24 saves (2026-11-07); before it, an
occupation made the owner's estimate unknown.

### Power share against GDP

Observed 2026-11-07 on the first, the 2027-07 and the latest (2032-11) Protectorate saves and the first and last
Resist saves, with occupied regions weighed as above; the Appease saves were no longer available. The power share is
the mean of a nation's shares of world GDP, population and strength, one third each (`narrative/prominence.py`). The
shares built from the snapshot and from its situation report were identical, and summed to 1, in all five saves.

| Campaign | Save | Nations with a share | Largest power share | Largest GDP share | Top-10 overlap | Median rank shift |
| --- | --- | --- | --- | --- | --- | --- |
| Protectorate | 2026-02 | 174 | 15.9 % | 19.8 % | 7 | 12 |
| Protectorate | 2027-07 | 173 | 15.9 % | 20.0 % | 8 | 12 |
| Protectorate | 2032-11 | 166 | 13.6 % | 19.0 % | 7 | 10 |
| Resist | 2045-08 | 53 | 26.4 % | 37.2 % | 9 | 4 |
| Resist | 2046-10 | 53 | 25.7 % | 37.5 % | 8 | 4 |

The largest economy holds the first power place in every save, with a smaller share: the power share flattens the
top. Nations far down the GDP ranking enter the power top ten on strength: GDP places 26, 50 and 134 reach power
places 5, 9 and 10 in the first Protectorate save, places 17, 46 and 143 reach 6, 7 and 8 in the latest, and places
18 and 21 reach 7 and 8 in the last Resist save; those from outside the GDP top ten hold 5 to 8 % of world strength
each. Population alone lifts a nation at most to place 12 (GDP place 20, no measurable strength). Every nation holding
regions has a share in all five saves.

### Scaled atomic events

Observed 2026-11-07 on five Protectorate saves (2029-06 to 2031-06) with every reference share at 0.01. The score
moves by `10·log10(share / reference)` points, so a stake a tenth of the reference lowers it by 10.

| Event type | Scaled events | Median scale | Range |
| --- | --- | --- | --- |
| `control_point.controller_changed` (per point) | 139 | -11 | -20 to 1 |
| `faction.nation_control_changed` | 168 | -9 | -20 to 4 |
| `nation.executive_change_recorded` | 52 | -8 | -20 to 6 |
| `organization.assigned_councilor_changed` | 333 | -13 | -14 to -4 |
| `region.nation_changed` | 6 | -9 | -16 to -6 |

Most nations and regions hold far less than a hundredth of the world, so the typical scaled event is lowered and
only the large ones keep or exceed their level: of the organization assignments 132 stay `major` and 201 fall to
`minor`, the split the former top-tier rule drew by tier alone. The references were left at 0.01 (*hypothesis*: a
reference near the median share would lift most events instead of lowering them, which the clamp bounds either way).

### Scaled nation narrative events

Band shifts, per-capita GDP trajectories, diplomatic realignments, military buildups and demobilizations and navies
established scale by the power share of their nation, read in the situation reports of the event's first interval.
Observed 2026-11-14 on the three benchmark campaigns (`events --narrative`, every reference share at 0.01), compared
with raising a top-ten GDP nation's event one level:

| Campaign | Narrative events | Level changed | Up | Down |
| --- | --- | --- | --- | --- |
| Protectorate (benchmark) | 772 | 86 | 0 | 86 |
| Protectorate, first five saves | 201 | 22 | 0 | 22 |
| Resist (benchmark) | 64 | 14 | 0 | 14 |

- The nations of GDP places 11 to about 100 keep their level: their stake lies within a few points of the
  reference.
- Small states drop one level (GDP places from about 100 down, such as Iceland, Djibouti and The Bahamas).
- The top-ten economies drop one level too. Their stake adds 3 to 12 points, while a level is 25 points wide and
  starts 13 points above a base. Rising a level takes a share of about 20 %, which no nation of the Protectorate
  saves holds (the largest is 14 to 16 %, table above).
