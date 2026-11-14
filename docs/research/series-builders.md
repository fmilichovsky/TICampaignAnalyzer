# Series builders: generic shapes of today's stakes

Research note for the stake calibration dashboard map (#446), answering #449. It is not a decision record. Sources
are this repository at `main` `72048b5` unless a line says otherwise. Line numbers point at that commit. The nuclear
share is read from PR #445 (head `1713816`, open, closes #360). The issue body of #360 says "closed, implemented",
but on `main` only the glossary terms (#443) have landed.

A **series** (working term) is the share distribution a reference slides over: for each event, the share its stake
measures, plus what the replay needs to rescore it. A **builder** is a predefined function that produces a series
from benchmark pipeline products for a stake that has no `Stake` implementation yet.

## Summary

Every stake today varies along two independent axes:

- **The shape:** how an event's entities, attributes or record become one share. This is the builder.
- **The share function:** which world total the share is taken of (`StakeMeasure`). This is the measure.

The two are already separate in code. `Scaling` and `NarrativeScaling` pair one measure with one entity selector, and
the shares come from `_IntervalShares._measured` per measure (`significance.py:294-313`, `456-468`, `541-550`). The
blended faction stake is a share function, not a shape. "Held or moved" (CONTEXT.md, **Stake**) is a property of the
entity selector, not a separate shape: a territory stake is the held population share of the regions that moved.

Four builders cover the 18 stakes (17 on `main`, plus `nuclear_arc` in PR #445) and both design cases. A fifth item is a combinator, and one is a
modifier.

| Builder | Use when … | Stakes today |
| --- | --- | --- |
| **Entity sum** | the event concerns named entities and matters in proportion to their summed weight in the world | 15 of 18 (all but the three below) |
| **Per-part share** | the event moves one of several equal parts of an entity, such as one control point of a nation | `control_point` |
| **Record share** | a save-carried record sizes the event, and its entities' holdings do not | `combat` |
| **Net move** | the event is a change in a counted quantity, and the size of the change matters, not the size of its holder | `nuclear_arc` (PR #445) |
| *Max of measures* (combinator) | the event can move any of several measures, and the measure it moved most decides | none yet; #361 needs it |
| *Both sides armed* (modifier) | a conflict escalates when both sides hold warheads | `belligerents`, `war_sides` |

- **#360:** net move plus a new warheads share function. PR #445 built exactly that, as a `net_move` flag.
- **#361:** entity sum (actor) plus two new share functions, boost and mission control, joined by the max-of-measures
  combinator. The combinator is the one missing piece. It should compare scales, not raw shares, when the two
  references differ.

## 1. Catalogue of today's stakes

Every stake declared by a kind, read from the kind registry (`kinds.KINDS`, listed by stake). Atomic and
reconstructed events are scored by `Stakes` over the two snapshots of their interval (`significance.py:338-419`,
`_basis` at `676-699`). Narrative events are scored by `ReportStakes` over the two situation reports of their first
interval (`422-450`, `_narrative_basis` at `702-718`).

| Stake | Pass | Measure | Entities (selector) | Shape | Event types |
| --- | --- | --- | --- | --- | --- |
| `nation` | atomic | power | first nation entity (`_nation`, `475`) | entity sum | `nation.appeared`, `.disappeared`, `.claims_changed`, `.executive_change_recorded`, `.federation_changed`, `.statistic_shifted`, `faction.nation_control_changed` |
| `belligerents` | atomic | power | every nation entity, only for `relation == "wars"` (`483-486`) | entity sum + armed bonus | `nation.relation_changed` |
| `territory` | atomic, reconstructed | population | the event's region, else its `regions` list, else the regions of the cited `region.nation_changed` events (`489-502`) | entity sum, moved entities | `region.nation_changed`, `nation.territory_gained`, `.territory_lost`, `.independence`, `.unification`, `.annexation` |
| `control_point` | atomic | power | first nation entity, share divided by the points it holds (`529`, `_points` at `650-656`) | per-part share | `control_point.controller_changed` |
| `organization` | atomic | organization | first organization entity (`479`) | entity sum | `organization.assigned_councilor_changed` |
| `hab` | atomic | hab | the `habs` attribute, else the first hab by state type (`508-512`) | entity sum | `hab.appeared`, `.destroyed`, `.faction_changed`, `faction.first_hab_on_body` |
| `fleet` | atomic | fleet | first fleet entity (`515`) | entity sum | `fleet.faction_changed` |
| `left_faction` | atomic | faction (blended) | the `before` attribute's entity (`519-522`) | entity sum | `councilor.faction_changed` |
| `combat` | atomic | battle | none, `from_record=True` (`534`, `contested_share` at `372-395`) | record share | `faction.combat_recorded` |
| `actor` | narrative | power | first nation in the actor role (`562-565`) | entity sum | `nation.*_shift` (7 band shifts), `.economic_trajectory`, `.diplomatic_realignment`, `.military_buildup`, `.demobilization`, `.navy_established` |
| `targets` | narrative | power | every nation in the target role (`568`) | entity sum | `faction.takeover`, `faction.takeover_wave`, `nation.merger` |
| `war_sides` | narrative | power | the `attackers` and `defenders` lists (`580`) | entity sum + armed bonus | `war.arc` |
| `members` | narrative | power | `members_initial`, `members_final` and every member change (`584-595`) | entity sum | `federation.lifecycle` |
| `regions` | narrative | population | the `regions` list (`598`) | entity sum, moved entities | `nation.expansion`, `.cession`, `.claims_declared` |
| `independent_nation` | narrative | power | beneficiary, else actor (`602-604`) | entity sum | `nation.release`, `.breakaway` |
| `colony` | narrative | hab | the `habs` of the cited events (`607-609`) | entity sum, cited entities | `faction.colonisation_wave` |
| `new_ships` | narrative | fleet | the first entity of each cited `ship.appeared` (`612-614`) | entity sum, cited entities | `faction.fleet_buildup` |
| `nuclear_arc` | narrative | nuclear | actor, for the basis only; the share comes from the arc's attributes (PR #445) | net move | `nation.nuclear_armament`, `.nuclear_buildup`, `.nuclear_disarmament` |

Shared mechanics, the same for every entity-sum stake:

- **Side.** The summed share of the distinct entities on the interval's earlier side. An entity with no share there
  is read on the later side. No entity on either side means no basis (`_IntervalShares.share`, `315-324`). ADR-0011:
  "It is read on the interval's earlier side."
- **Sum.** `prominence.total` sums the distinct entities (`prominence.py:108-110`). `power_shares` normalises, so
  shares of members, sides and holdings add (`prominence.py:42-62`).
- **Scale.** `round(10·log10(share / reference))`, clamped to `[scale_min, scale_max]` (`significance.py:644-647`). A
  share of zero or less gets `scale_min`. The reference is `CODE_REFERENCES` for hab, fleet, battle and faction (and
  nuclear in PR #445), else `ReferenceSettings` (`630-641`, `config.py:148-161`).
- **Score.** `clamp(base + scale + bonus)` for atomic events (`751-752`, `840-845`). For narrative events, the max of
  that and the highest cited score (`811-812`).

Not yet scaled, and candidates for later design series: `nation.space_program_growth` (`Rule.ENTERED_TOP`, #361),
`nation.population_collapse` (rule, which #360 keeps), `nation.space_defences_established`, `faction.space_campaign`,
`world.ranking_changed`, `campaign.first_milestone` and `technology.milestone` (rule-tiered).

## 2. Share functions (the measure axis)

A builder takes a share function as a parameter. The functions today, and the products each reads:

| Measure | Share function | Reads from a report? | Source |
| --- | --- | --- | --- |
| power | weighted GDP, population and strength shares over landed nations | yes (`SituationReport.power_shares`) | `prominence.py:42-82`, `situation.py:373-383` |
| population | region population over world population | yes (`population_shares`) | `prominence.py:85-95`, `situation.py:424-427` |
| organization | tier^`tier_exponent` over all organizations | **no**: "A report states no organization tiers" | `prominence.py:98-105`, `significance.py:423-424` |
| hab | tier² over human tier² (floor `HAB_FLOOR`) | yes (`hab_shares`) | `prominence.py:202-204`, `situation.py:416-418` |
| fleet | dry mass over human dry mass (floor `FLEET_SATURATION`) | yes (`fleet_shares`) | `prominence.py:207-209`, `situation.py:420-422` |
| faction | Earth share blended with space share by saturation | yes (`faction_stakes`) | `prominence.py:212-225`, `situation.py:385-414` |
| battle | contested mass over world weighted ship mass | **no**: needs `ShipMasses` design and hull tables and the combat record | `significance.py:372-416` |
| nuclear (PR #445) | net move over world warheads at the larger end | yes (`NationSituation.nuclear_weapons`) | PR #445 `ReportStakes.world_warheads`, `_nuclear_share` |
| boost, mission control (#361, proposed) | the nation's value over the summed known values | yes: `NationSituation.boost` and `.mission_control` are there today | `situation.py:118-119` |

The faction stake shows that blending belongs to the share function. Its selector is an ordinary attribute entity
(`_left_faction`). The blend of Earth and space, and the saturation, are inside `faction_stakes`. A dashboard that
slides the faction reference over a fixed table cannot change `w_space`, which the map already rules out of scope.

## 3. The builders

Each builder returns, per event, **the share, the entities named in the basis, and the bonus eligibility**. PR #445
separates these: its basis names the actor while the share ignores the actor's holdings. The record share does the
same: its basis names the sides' factions. So the entities are an output, not only an input.

### 3.1 Entity sum

`entity_sum(events, select, measure)`: the summed share, under `measure`, of the distinct entities `select` names,
read on the earlier side of the event's (first) interval, falling back to the later side.

**Use when** the event concerns named entities, and it matters in proportion to how much of the world they hold
(their power, population, habs or fleet) or how much they moved (the regions or habs that changed hands).

The selector is the only per-stake code. Today's selectors fall into four forms:

- *the first entity of a domain or state type*: `nation`, `organization`, `fleet`, `hab` (fallback);
- *a role*: `actor` (the first only), `targets`, `independent_nation` (beneficiary, else actor);
- *a list or entity attribute*: `regions`, `war_sides`, `members`, `hab` (`habs`), `left_faction` (`before`),
  `belligerents` (gated on `relation`);
- *entities of cited events*: `colony`, `new_ships`, `territory` (reconstructed fallback).

A design series names one of these forms plus its argument (domain, role, attribute name, cited type and attribute),
so it needs no code. The gated `belligerents` and the domain or state-type fallbacks would need a predicate. They
could stay code, since they are implemented stakes and get their series from the calibration table anyway.

**Inputs.**

- Events of a type, with their attributes, roles and entity refs.
- For cited selectors, the events they cite: `constituents` for narrative events, `evidence` for reconstructed ones
  (`significance.py:418-419`, `sequence.py:187-193`).
- The two situation reports of the event's (first) interval, or the two snapshots for the organization measure.

**Outside the pipeline.** Easy for every measure except organization. Atomic events read their shares from snapshots
(`Stakes._measured`, `361-370`), but `nation_power`, `region_shares` and the space shares are documented to equal
the report's shares for the same snapshot (`prominence.py:65-67`, `90-92`). So a cache of situation reports keyed
by interval (`aggregation.interval_reports`, `aggregation.py:129-133`) serves them. Organization tiers are in the
snapshot only, so an organization series needs the snapshots, or a report field added for it.

### 3.2 Per-part share

`per_part(events, select, measure, parts)`: the entity sum of one entity, divided by the number of equal parts it
holds.

**Use when** the event moves one part of an entity that is split into several equal parts, and the event's weight is
the entity's weight over its parts. Today the only case is a control point: a nation's power share over its control
points.

**Inputs.**

- The entity-sum inputs.
- The part count. Today it comes from `Lookup.state(nation).controlPoints` on the earlier side, else the later
  side, else 1 (`_points`, `650-656`).

**Outside the pipeline.** Needs a Lookup over two snapshots as written. `NationSituation.control_points` carries the
same count from the later snapshot's `controlPoints` (`situation.py:496`, `reconstruction/common.py:37-43`). It
differs in two small ways: it counts entity references only, and it is the report's own side. So a report-based
series is possible, but a parity check should confirm that it matches `_points`.

### 3.3 Record share

`record_share(events, measure_record)`: a share computed from the content of the save-carried record entry the event
rests on, over a world total. The entities are the record's participants, for the basis only.

**Use when** a save-carried record states the event's own size (ADR-0006), and the participants' holdings would
mismeasure it: a large fleet swatting a scout is a skirmish (ADR-0011, "Battles use contested mass").

**Inputs.**

- The event's source location, to find the entry by record index.
- The record set from the later snapshot (`Lookup.record_set`, `_combat_entry` at `403-416`).
- `ShipMasses` of the earlier snapshot: masses by faction and design, and median masses by hull (`prominence.py:147-199`).
- `Lookup.faction_kind`, for the alien weight.
- The world weighted ship mass, which the report carries (`situation.py:278`).

**Outside the pipeline.** Hard. It needs both snapshots: the record, the design and hull masses (the report keeps
only `dry_mass_by_asset`, `situation.py:330`) and the faction kinds. For an implemented stake, the calibration table
should carry the share the pipeline measured (#448), not recompute it. A future record-shaped design series would
need the in-process extraction run of #448, with snapshots in hand. This is the only builder that cannot work from
cached reports plus events.

### 3.4 Net move

`net_move(events, before_attr, after_attr, world_total)`: `|after − before|` of a counted quantity, read from the
event's attributes, over the quantity's world total. The total is taken at the larger of the earlier report of the
first interval and the later report of the last interval. Unknown counts are skipped (ADR-0005), and the total is
never below the move (PR #445, `_nuclear_share`).

**Use when** the event is a change in a quantity whose world total is small or lumpy. The size of the change should
decide, not the size of whoever made it. Without this, a great power's token move would outrank a small nation's
total one (#360, "a great buildup outranks a token one").

**Inputs.**

- Events with numeric before and after attributes.
- The situation reports of the event's first **and last** interval. PR #445 had to add the second `ReportStakes` to
  `narrative_score` for this (PR #445 `aggregation.py`, `narrative_score(..., last=...)`).
- The interval keys the event spans (`Event.intervals`).

**Outside the pipeline.** Easy from cached reports plus events. It is the only builder that reads two intervals, so
the cache key per event is (first interval, last interval), not one interval.

### 3.5 Max of measures (combinator)

`max_of(series_a, series_b, …, gate)`: per event, the constituent series that gives the highest **scale**, among the
measures the event moved (`gate`). The basis names the winning measure.

**Use when** one event can move several measures, each with its own world total and reference, and the one it moved
most decides. An example is a space program that grew in boost, mission control or both.

Compare `share / reference`, not raw shares. With equal references the two orders agree. With different references,
"the higher share" would let the measure with the larger typical share always win. `SignificanceBasis` has one
`measure` field (`significance.py:741-748`), so the combinator must pick one measure per event, not blend them.

**Inputs.** Those of its constituent series, plus the gate. For #361 the gate is whether `{metric}_before` and
`{metric}_after` are set on the event (`assets.py:212-219`).

**Dashboard effect.** One event's score depends on two references, so moving one slider can switch the winning
measure. Replay must evaluate the max per event (#450), and each measure's panel should count the events it won.

### 3.6 Both sides armed (modifier)

Adds `ReferenceSettings.nuclear_bonus` when the conflict is between nuclear-armed parties. It is outside the clamp
(`config.py:158-161`).

**Use when** the event is a conflict between named sides.

The two current versions differ in a way the series should record, not hide:

- **Atomic `belligerents`:** more than one distinct nation, and **every** listed nation armed. It reads
  `numNuclearWeapons` through the Lookup (`significance.py:659-665`, `692-697`).
- **Narrative `war_sides`:** **at least one** armed nation on **each** side. It reads the report
  (`ReportStakes.nuclear_armed`, `443-450`; `_armed_on_both_sides`, `721-722`).

Both can be read from reports, because `NationSituation.nuclear_weapons` is `numNuclearWeapons` as is
(`situation.py:122`). The series row should carry eligibility as a boolean, so the dashboard can toggle the bonus
(the map's Notes; #448 notes that today's stored `bonus` loses this).

## 4. Testing the set against the design cases

### #360, nuclear share: net move + warheads

- **Builder:** net move, with `before_attr="before"`, `after_attr="after"`, and a world total of the summed known
  `nuclear_weapons` in a report.
- **Entities for the basis:** the actor.
- **Reference:** `0.01`, a code constant.
- **Events:** `nation.nuclear_armament`, `.nuclear_buildup`, `.nuclear_disarmament`. They exist on the benchmarks
  today, so the series can be built before the stake is.

**Expressible:** yes, with no new builder. PR #445 confirms the shape. It added `net_move: bool` to
`NarrativeScaling` beside `nuclear_bonus`, plus `_nuclear_share`. This is the third boolean flag on a scaling, after
`per_point` and `from_record`. Each flag swaps the shape, which suggests the scaling should name its builder instead
of carrying one flag per shape.

**What the builder set showed:**

- An entity sum over a warheads measure would compute the actor's held share of the world's warheads. That is the
  alternative #360 rejected. With both builders, a designer can calibrate both and compare them.
- The second report side (the last interval) is a new pipeline input. No entity-sum stake needs it.
- PR #445's reviewer note says an armament's first interval can come from its corroborating
  `nation.nuclear_program_changed`. The builder must take the event's own interval list, not the constituent shifts'.
- The warhead shift (`nation.statistic_shifted`) becomes trivial evidence in #360, because the max-of-cited would
  otherwise carry the power-scaled atomic score. A design series should show the cited ceiling next to the own score.
  If not, a calibration of the own stake alone overstates how much the reference decides.

### #361, space program share: entity sum (actor) × {boost, mission control}, max of measures

- **Builder:** max of two entity sums. Each sums the actor's share, under a new share function: the nation's boost
  over the summed known boost of the report's nations, and the same for mission control.
- **Gate:** the measures the run moved (`{metric}_before` is set).
- **Events:** `nation.space_program_growth`, which exists on the benchmarks today. It is minor, and `Rule.ENTERED_TOP`
  promotes it.

**Expressible:** yes, except for the combinator. **What is missing:**

1. **Two share functions.** The inputs are already in the report (`NationSituation.boost`, `.mission_control`), so
   it is a report method, as with `world_warheads` in PR #445. Still open:
   - which nations the total covers: landed only, as `power_shares` uses, or every nation with a known value;
   - whether an unknown value is skipped (ADR-0005).
2. **The combinator.** Neither scaling class holds more than one measure, and the basis names one. #361's wording,
   "the higher share", should become "the higher scale" unless the two references are equal (§3.5).
3. **Held or moved.** Read on the earlier side, the share is the program the nation had before it grew, so a program
   that grew from almost nothing scores low. #361 asks for the held share. The net-move builder offers the
   alternative: the growth over the world total, with `{metric}_before` and `{metric}_after` already on the event.
   The dashboard can show both before #361 is grilled.
4. **Two references at once.** Two new references (settings in #361's wording, or registry entries, #447), and a
   replay that takes the max per event (§3.5).

## 5. Pipeline products per builder

| Builder | Events | Cited events | Reports (first interval) | Reports (last interval) | Snapshots / Lookup | Runs from cached reports + events? |
| --- | --- | --- | --- | --- | --- | --- |
| Entity sum | of the type | only for cited selectors | both sides | — | organization measure only | yes, except organization |
| Per-part share | of the type | — | both sides | — | `controlPoints` today; the report count may match (parity to check) | probably |
| Record share | of the type, with source location | — | earlier side (world mass) | — | record set, `ShipMasses`, faction kinds | **no** |
| Net move | of the type, with before and after attributes | — | earlier side | later side | — | yes |
| Max of measures | as its parts | as its parts | as its parts | as its parts | as its parts | as its parts |
| Both sides armed | sides or entity list | — | both sides (`nuclear_weapons`) | — | the Lookup today for atomic; the report has the same field | yes |

## 6. What makes a builder hard to run outside the pipeline

- **A Lookup over two snapshots.** It serves record sets, faction kinds, `controlPoints` and `numNuclearWeapons` in
  the atomic pass. Only the record share needs something the report lacks. The rest have report equivalents, but a
  parity check against `_points` and `_holds_nuclear_weapons` should confirm them.
- **Snapshot-only measures:** organization tiers and the per-design ship masses.
- **Cited evidence.** Reconstructed events cite the interval's objective events (`evidence=objective`), and narrative
  events cite constituents up to three levels deep (#448). A cited-entities selector needs those events in the cache,
  not only their ids.
- **Interval identity.** The atomic pass works on one interval. The narrative pass keys reports by
  `interval_reports`, and the net move needs the event's first and last interval keys. So the cache must key reports
  by interval key, not by date alone.
- **Settings baked into shares.** Power weights, `w_space` and `tier_exponent` change the shares themselves. A series
  is valid only for the settings it was extracted under, which is already part of the cache key in the map.

## 7. Open points for the grilling tickets

- **#447, registry.** Treat the shape as a named builder on the scaling. Today it is a set of booleans: `per_point`,
  `from_record` and, in PR #445, `net_move`. A design series and an implemented stake could then share one
  declaration: builder, selector or attributes, measure, reference.
- **#448, row schema.**
  - One row per event, with: the unrounded share, the basis entities and the bonus eligibility, as the builders
    output them.
  - For max-of: one share per constituent measure, plus the gate.
  - For net move: the first and last interval keys.
- **#451, design series.**
  - Entity sum and net move are declarable without code: a selector form and its argument, or two attribute names.
    That fits the "20-line PR".
  - A new share function is code, but a small report method.
  - The record share is not a design-series builder until #448 has an in-process extraction run with snapshots.
- **#361 grilling:** "higher share" or "higher scale"; held or moved; the world-total population.
