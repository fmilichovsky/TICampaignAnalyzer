# Terra Invicta Narrative Save Analyzer --- Architectural Vision

This document holds the concepts, principles and the designs not yet built. Implemented contracts live in the
code; each section names the module that defines them. Observations of the save format live in [game-data
notes](game-data-notes/README.md).

## 1. Purpose

Terra Invicta produces a rich, persistent simulation state, but the save game is optimized for resuming play
rather than explaining what happened. A campaign can contain years of wars, political transformations, faction
struggles, space operations and technological shifts, while the save itself does not present them as a
coherent history.

The **Terra Invicta Narrative Save Analyzer** reconstructs that history from one or more save files. It treats
saves as **snapshots of a changing world** and derives a progressively more semantic representation:

1.  **Raw save state** --- parsed game data.
2.  **Objective changes/events** --- facts directly evidenced by comparing states.
3.  **Inferred events** --- plausible actions or causes reconstructed from those changes.
4.  **Narrative events** --- semantically grouped developments suitable for human presentation.
5.  **Campaign narrative** --- chronological, readable history generated from the event stream.

The architecture preserves the distinction between what the save proves and what the analyzer infers. It
produces useful narratives without pretending that an inference is an objective fact.

## 2. Design Goals

### Primary goals

-   Reconstruct meaningful campaign history from ordinary saves.
-   Work incrementally across a sequence of saves rather than requiring game telemetry.
-   Preserve provenance from every narrative claim back to save-state evidence.
-   Distinguish **objective evidence** from **interpretation/inference**.
-   Distinguish **atomic events** from higher-level **narrative events**.
-   Support multiple narrative views without changing the underlying analysis.
-   Make analyzers modular so new game systems can be added independently.
-   Start as a practical Python CLI and evolve toward continuous campaign analysis.

### Secondary goals

Deterministic, inspectable intermediate outputs; analyzer failures that stay local; uncertain or incomplete
reconstructions allowed; both per-save diffs and a cumulative history; game-version-specific parsing isolated
from semantic analysis.

### Non-goals

Recreating a game event log that does not exist; guaranteeing that every inferred action is historically
correct; a complete game-state simulator; replacing the game's UI; requiring a game modification or mod.

## 3. Core Architectural Principle

The project is a pipeline in which each stage adds interpretation without destroying lower-level evidence.

``` text
Save files
  → [Save Loader / Parser]
  → [Normalized Save State]            entity collections + save-carried records (dated logs, counters)
  → [State Diff / Objective Event Detection]
  → [Inference / Event Reconstruction]
  → [Atomic Event Stream]
  → [Narrative Aggregation]
  → [Narrative Event Stream]
  → [Narrative Rendering]              per-save Markdown, campaign Markdown, LLM narration
```

A key property is that **narrative presentation is downstream of analysis**. The renderer never needs to
rediscover what happened.

# 4. Data Model

The model uses several independent dimensions rather than making one classification do too much work. All
model types are frozen, deterministically sorted dataclasses with a JSON-friendly `to_dict()`; they are
defined in `src/tinarrative/model/`.

## 4.1 SaveSnapshot

A `SaveSnapshot` is the normalized, analyzer-friendly state extracted from one save: the game date and turn
counters, entity collections per domain (factions, nations, regions, control points, councilors,
organizations, armies, fleets, ships, habs, space bodies, wars, federations, technologies, campaign
singletons) and the save-carried records (4.3).

It is a **normalized semantic state**, not a 1:1 copy of the serialized structure. Every entity keeps a
`SourceLocation` (state type, map ID, JSON path) for debugging and provenance, but downstream stages depend
only on the normalized objects.

Two rules govern normalization:

-   **Absent is not false.** A field the save does not carry is `Unknown(reason)`, never `False`, zero or
    empty. An in-save reference resolves to an `EntityRef` only when the target exists in the same save under
    the expected domain; otherwise it stays `Unknown` with the raw ID.
-   **Nothing is dropped silently.** Every structure outside the code-form schema (`parsing/fields.py`,
    `parsing/inventory.py`) is reported through `parsing.unknowns.UnknownCollector` as a content-free finding,
    and is never coerced into a model value ([unknowns registry](game-data-notes/unknowns/README.md)).

Defined in `src/tinarrative/model/snapshot.py` (`SaveSnapshot`, `EntityState`), `model/entities.py`
(`EntityId`, `EntityRef`, `IdentityConfidence`) and `model/values.py` (`Observed`, `Unknown`); filled by
`src/tinarrative/parsing/normalization.py`.

## 4.2 StateDiff

A `StateDiff` captures the changes between two snapshots. A `StateChange` is deliberately low-level: a domain,
an entity, a field, the before and after values, and evidence locating each side in its save.

For example: Germany's controlling faction changed from Servants to Resistance; a councilor disappeared from a
faction; a fleet's location changed.

The diff layer stays literal. It does not try to explain *why* something changed: a value that is `Unknown` on
either side gives an `unknown` change and nothing is inferred from the known side; reordering a list is not a
change; an entity present in one snapshot only is `appeared`/`disappeared`.

Defined in `src/tinarrative/model/changes.py` (`StateDiff`, `StateChange`, `ChangeKind`) and
`src/tinarrative/diff/state_diff.py` (`diff_states`).

## 4.3 Save-carried records

Between objective snapshot state and inferred events sits a layer the save carries literally: dated logs and
cumulative counters that no field of the same snapshot can re-derive, such as a faction's resource ledger, its
hab destruction log, the control points it lost with their dates, kill lists, milestones, cumulative counters
and a nation's last executive change. They fill the gaps between sparse saves with exact dates, so they are
evidence in their own right: never folded into inferred events and never acknowledged as `derived_history`.
The lifecycle of each record is in the [field map](game-data-notes/domain-field-map.md) and the [higher-level
event sources](game-data-notes/higher-level-event-sources.md).

A field qualifies as a record when its entries are dated or cumulative, are not derivable from the rest of the
snapshot, and are carried forward from save to save rather than recomputed from current state. Rolling windows
and running histories the game recomputes from state the snapshot already holds are `derived_history` and stay
unnormalized.

A problem inside one entry (an unparseable date, an unresolvable reference) stays inside that entry, so the
rest of the log remains evidence. The diff compares a log as a multiset of entries and never assumes it is
append-only. A downstream stage may date an event by a record entry rather than by the save interval, but must
cite the entry.

Defined in `src/tinarrative/model/records.py` (`RecordSet`, `RecordKind`, the entry types, `diff_key`),
`parsing/records.py` (`decode_records`) and `parsing/fields.py` (`RECORD_FIELDS`).

# 5. Event Model

## 5.1 Event is the common semantic envelope

Every layer uses one event abstraction. Its important fields are:

-   **event type** --- what kind of thing happened.
-   **status** --- objective vs inferred.
-   **confidence** --- how strongly the reconstruction is supported.
-   **significance** --- how much it matters (section 12).
-   **sources** --- the save changes that support the event.
-   **constituents** --- the events an inferred or narrative event rests on.
-   **entities** --- actors, targets, locations, assets.
-   **attributes** --- event-specific structured data.

The core event representation carries no prose. Defined in `src/tinarrative/model/events.py` (`Event`,
`EventSource`, `EventStatus`).

## 5.2 Objective vs. Inferred is one dimension

This distinction answers: **how directly is this event supported by the save data?** An *objective* event is a
direct state transition: "The EU gained control of Slovenia", "A fleet's `destroyed` flag was set",
"Technology X completed." An *inferred* event is a reconstructed action or causal explanation: "The EU annexed
Slovenia", "The Resistance purged the Servants from Germany", "The councilor defected." An inferred event may
be strongly supported without being literally persisted in the save.

Save-carried records (section 4.3) are objective evidence of a third sort: a ledger or destruction-log entry
is literally persisted, dated by the game, and not a transition between two snapshots. An event built from one
is objective and dated by the entry.

This dimension is never overloaded with presentation concerns.

## 5.3 Atomic vs. Narrative is a separate dimension

This distinction answers: **how much of the event stream does this event represent?** An *atomic* event is the
smallest meaningful semantic unit produced by analysis, normally one concrete transition or a tightly
reconstructed action: a control point changing controller, a nation gaining regions, a technology completing.

A *narrative* event is a higher-level grouping of related atomic events that humans perceive as one
development: "the Resistance takeover of Germany" (control changes, councilor removals, consolidation), "the
European Union's absorption of Slovenia", "the Servants' space campaign against the Academy". A narrative
event can contain objective and inferred atomic events simultaneously.

The two dimensions are orthogonal.

# 6. Provenance and Evidence

Every derived event is traceable to evidence. Evidence names the save, the state type, the map ID and the JSON
path of each side; evidence that cites a save-carried record names the entry itself (field and index,
`RecordSet.entry_location`). An event can cite several pieces of evidence: an inferred takeover cites the
control-point changes, the executive record and the councilor changes it rests on.

The system never loses evidence because a higher-level event was created: an inferred or narrative event cites
the sources of its constituents, with their roles (primary or corroborating).

Defined in `src/tinarrative/model/evidence.py` (`Evidence`, `SourceLocation`) and `model/events.py`
(`EventSource`, `SourceRole`).

# 7. Confidence

Confidence is distinct from the objective/inferred classification and has three levels: `high`, `medium`,
`low`.

-   Direct ownership field changed → high confidence objective event.
-   A vanished hab plus a matching destruction-log entry → high confidence destruction inference.
-   Several indirect changes suggest a takeover → medium confidence inferred event.
-   A motivation reconstructed from timing alone → low confidence.

Confidence describes **the analyzer's confidence in the reconstruction**, not how important the event is.

# 8. Entity Model

Events reference stable logical entities rather than embedding strings: factions, nations, regions,
councilors, armies, fleets, ships, habs, space bodies, technologies, organizations, wars and federations.

Entity IDs are stable across snapshots whenever the underlying game entity can be identified. Where the game
provides no stable ID, identity rests on documented heuristics and records its uncertainty
(`IdentityConfidence`), so differently-established identities never compare equal. The per-domain strategy is
in [entity identity](game-data-notes/entity-identity.md).

Every entity carries its in-game name, and output renders it as `Name (domain:key)` so the ID stays available
for audit. Names can be player content: allowed in the user's own output, never in logs or fixtures.

# 9. Analyzer Architecture

An analyzer takes `(before, after, diff)` for one interval and emits objective atomic events
(`analyzers/base.py`, `Analyzer`).

Families follow discovered game data rather than mirroring every field: politics, military, space, technology,
faction (the ledger), campaign (global values, notifications) and aliens.

Principles:

-   **The diff is the evidence.** An analyzer never re-derives a fact from the snapshots; the snapshots supply
    context only (an entity's name, a control point's nation, a faction's kind). Events cite the literal
    changes they report.
-   **Ownership and control stay distinct.** A control point reports its controller; a nation's
    `controlPoints` list says which points belong to the nation, never that a faction controls it. That
    reading is reconstruction (section 10).
-   **No literal change is dropped.** A mirrored reference list is owned by the analyzer of the entities it
    contains, so no two analyzers report the same change; a list member no event explains is reported as
    `<owner>.<field>_changed`.
-   **Wording follows the field.** The words *destroyed*, *destruction* and *refit* occur only in event types
    whose primary source is the save field that literally carries them. A vanished fleet, army or hab is
    reported as absent or unresolved, never as a merge, loss or battle. No analyzer names a purge, coup,
    annexation, defection, a declared or won war, or a peace.
-   **Thresholds that decide emission live with the analyzer**, so no analyzer depends on the narrative stage.
    Their evidence is in [nation statistics](game-data-notes/nation-metrics.md) and the [higher-level event
    sources](game-data-notes/higher-level-event-sources.md).

Defined in `src/tinarrative/analyzers/`: the families' modules, the shared machinery in `analyzers/common.py`
(`run_analyzers`, `Transition`, `classify`, `EventBuilder`, `MembershipLedger`) and the registries in
`analyzers/__init__.py` (`ALL_ANALYZERS`, `FIRST_INTERVAL_ANALYZERS`).

# 10. Event Reconstruction

Some meaningful events are not directly visible as a single state transition, so the reconstruction layer
combines evidence by rules.

``` text
Observed: the nation's executive control point changes from Servants to Resistance; its executive-change
          record names a coup; a Servants councilor disappears; no diplomatic transfer.
Inferred: "Resistance took control of the nation's executive", high confidence, citing all four.
```

Principles:

-   **Explicit rules over opaque heuristics.** Each rule's evidence is in [sources for higher-level
    events](game-data-notes/higher-level-event-sources.md).
-   **One interval, objective inputs.** A rule sees one interval's objective events, with the snapshots and
    the diff as context. No rule builds on another inference.
-   **Snapshot facts qualify, they never prove.** A fact read from a snapshot alone (a nation holding no
    regions afterwards, the sides of a war) only qualifies evidence.
-   **Ambiguity is kept.** Where several explanations fit, every candidate is kept one confidence level lower
    and marked `ambiguous`, with the others as `alternatives`; or the event stays a conservative objective
    description.
-   **No invented causality** to produce nicer prose. A cause the save records (an executive-change cause)
    stays an attribute.

The rules cover three kinds of development:

-   **territorial**: territory gained and lost, independence, unification and annexation, read from region
    transfers and the game's tracked reasons;
-   **control**: a faction's hold on a nation's executive, plurality or every control point changing, the
    anchor of takeovers and breakaways;
-   **space**: a faction's first hab on a body, a hab destroyed (a vanished hab joined to its destruction-log
    entry), and a battle outcome between two factions.

Defined in `src/tinarrative/reconstruction/inference.py` (`infer_events`), with the rules in
`reconstruction/territorial.py`, `reconstruction/control.py` and `reconstruction/space.py` and the shared
citation and executive-seat lookup in `reconstruction/common.py`. `tinarrative save diff` runs no analyzers
and no reconstruction; `tinarrative events --inferred` reports inferred events.

# 11. Narrative Aggregation

Narrative aggregation operates on the atomic event stream of a save sequence. Its job is to state, once each,
the human-scale developments a campaign history reports: a faction taking over a nation and consolidating its
hold, a war from declaration to peace, a federation's life, a nation absorbing its neighbours over several
years, a space campaign that destroyed a rival's bases. Each development carries its span, its actors by role
and every piece of evidence beneath it.

The design is a small set of explicit, named rules; grouping by temporal proximity and shared entities alone
was rejected.

## 11.1 Inputs and scope

-   The qualified chronological event stream of one sequence (section 15, Mode B): objective and inferred
    events of every interval, with interval-qualified IDs.
-   One *situation report* per save (11.4), which replaces the snapshots: aggregation never holds a snapshot,
    so the sequence's two-snapshot memory bound stands.
-   It is the first stage allowed to see more than one interval. Every rule declares its window: one interval,
    a number of consecutive intervals, or the whole sequence. Windows are measured in game days, never in
    saves, because save spacing is arbitrary. A window is measured from the earliest date an event can have
    had, so consecutive intervals always touch and a long interval never splits one development.
-   Grouping is conservative: a rule emits only when its *anchor* evidence exists (an executive change, a war
    present in one save and absent in a later one, a federation member change), never from temporal proximity
    or shared entities alone. Proximity and shared entities decide which further events a rule attaches to an
    anchor, not whether a development exists.

## 11.2 The narrative event

A narrative event is an `Event` (section 5.1) with additional fields, not a parallel type: its span (`start`
and `end`, each with its date basis), whether it is `open` (still running at the last save), the `intervals`
it spans and its `roles` (actor, target, beneficiary, loser, assisting, location, body).

-   **Constituents** name atomic and inferred events by qualified ID; `sources` is the union of their sources
    with roles kept. The evidence beneath a development is never dropped.
-   **Status** is objective when every constituent is objective and the join is by a stable entity ID (a war,
    a federation, a nation across its own events); inferred when the join is heuristic (a shared nation plus a
    time window) or any constituent is inferred.
-   **Confidence** is the minimum over the constituents, lowered one level for a heuristic join; a rule that
    claims more states why.
-   **Significance** is assigned by the rule (section 12) and never below the most significant constituent.
-   **Dating**: `start` is the earliest constituent `not_before`, `end` the latest constituent date, each with
    the basis of the event it came from; a record-dated constituent narrows the span. Corroborating-only
    events (ledger charges) are cited but never set the end. An event whose anchor is still present in the
    last save is `open`, so a later run over more saves (Mode D) extends it instead of emitting a second one,
    and a later installment (20.7) continues it.
-   **Roles**, not titles: the narrator needs to know who acted, on whom, who benefited and who assisted.
    Attributes stay literal structured facts. No prose.
-   **Nesting**: one level per order. A rule of order k sees the stream plus the narrative events of lower
    orders, so a war arc may contain an expansion that happened during the war; a rule never builds on a rule
    of its own order, and there are no cycles.

Defined in `src/tinarrative/narrative/aggregation.py` (`NarrativeRule`, `NarrativeBuilder`, `Join`,
`aggregate`) and `model/events.py` (the narrative fields of `Event`, `Role`).

## 11.3 First catalogue

The catalogue was chosen against the format the project aims for (period-dated developments naming factions
and nations) and against the evidence the normalized model holds. Rule thresholds and windows are runtime
settings ([configuration](configuration.md)); their evidence is in [sources for higher-level
events](game-data-notes/higher-level-event-sources.md) and [nation
statistics](game-data-notes/nation-metrics.md).

Geopolitics:

| Type | Says |
| --- | --- |
| `faction.takeover` | faction X took control of nation N and consolidated it |
| `war.arc` | war between A and B and their allies from start to peace, with regions transferred |
| `federation.lifecycle` | federation formed, joined, left, renamed, dissolved |
| `nation.expansion` | N absorbed M1..Mk over a period, peacefully or by war |
| `nation.release` / `nation.breakaway` | parent released N / N broke away under faction X |
| `nation.cession` | N transferred regions to M without war (medium at most: a conquest without a war looks the same) |
| `nation.claims_declared` | N claims regions of M |
| `nation.<statistic>_shift` | N moved into another of the game's bands of unrest, democracy, education, cohesion, inequality or military tech, and held it |
| `nation.population_collapse` | N's population fell beyond what territory explains |
| `nation.economic_trajectory` | N's per-capita GDP boomed or slumped over years |
| `nation.military_buildup` / `nation.demobilization` | N's standard armies grew or shrank |
| `nation.navy_established` | N raised its first naval army |
| `nation.space_program_growth` | N grew its launch capacity or mission control |
| `nation.space_defences_established` | N defended its first regions against orbit |
| `world.ranking_changed` | nations entered or left the top N by GDP, strength, boost or mission control |

Every geopolitical development carries `metric_shifts`: the statistic shifts of its nations inside its span,
as context rather than constituents, so a takeover or merger states what it did to democracy, GDP and
inequality without a separate event. A band shift is suppressed when such a development already carries it.
The only band labels assigned are the game's own (`analyzers/politics/bands.py`, provenance in [nation
statistics](game-data-notes/nation-metrics.md#value-bands)); no label of ours ("democratic") is.

Space:

| Type | Says |
| --- | --- |
| `faction.space_campaign` | X destroyed k habs and fleets of Y over a period, winning n recorded battles |
| `faction.colonisation_wave` | X established habs on bodies B1..Bn in a period |
| `campaign.first_milestone` | a campaign-wide first, dated |
| `faction.fleet_buildup` | X commissioned n ships of class C |
| `technology.milestone` | a technology or project from a curated list completed (the list is interpretation) |

**Dated mission records as evidence.** Every faction carries a `Transactions` ledger (section 4.3) whose
labels include mission and operation names. It can attribute an action to a faction and narrow its date where
a visible effect already exists. The councilor's current mission field is never used. A ledger entry names no
target, some labels are hashed, each label's list is pruned, and an entry is a cost charged when the mission
is assigned, some time before it resolves (see the `Transactions` section of the [higher-level event
sources](game-data-notes/higher-level-event-sources.md)). So the bounds are:

1.  only a documented label allow-list, each label checked against a visible effect;
2.  entries are read by date from the later snapshot inside the window, never from diff presence;
3.  `faction.transaction_recorded` is `minor` and cited only as corroboration of an event whose effect is
    already evidenced, within a window from the entry date up to the assignment-to-outcome bound, never after
    the effect; it may narrow a span's start but never sets its end;
4.  attribution only when exactly one faction's ledger carries the label in the window and that faction is the
    visible beneficiary; otherwise `candidates` and no attribution;
5.  record-dating only in that single-candidate case;
6.  confidence never above medium on ledger evidence alone, since one charge may corroborate developments in
    several nations and identifies none (the atomic event records a literal entry and is itself high
    confidence; the cap binds the narrative events that cite it);
7.  `Unrest` entries are cross-checked against `factionUnrestAttempts` before either is trusted.

Defined in `src/tinarrative/narrative/catalogue.py` (`NARRATIVE_RULES`, `narrative_rules`), with the rules in
`narrative/geopolitics.py`, `narrative/nation_metrics.py`, `narrative/assets.py` and `narrative/space.py`, the
curated milestones in `narrative/milestones.py` and the ledger analyzer in `analyzers/faction/ledger.py`.
Their settings are `config.GeopoliticsSettings`, `config.NationMetricsSettings` and `config.SpaceSettings`.

## 11.4 Situation reports

A situation report is the deterministic digest of one snapshot that the narrative layer and the narrator need
as context: who holds each nation's executive and how many of its control points, federations with members,
wars with sides, each nation's statistics, armies and space assets, habs, fleets and ships per faction,
milestones and campaign-wide counters. It is read from the snapshot alone, is snapshot-dated evidence rather
than an event, and lets a development say "formerly held by faction Y" or "then a member of federation F".

Every value is literal: a report counts a nation's points per faction but never says a faction controls it. A
value the snapshot does not establish is `Unknown`, never zero. The sequence keeps the reports and discards
the snapshots.

Defined in `src/tinarrative/narrative/situation.py` (`build_situation`, `SituationReport`); the JSON form is
in [events](commands/events.md#situation-report).

# 12. Significance

Not every state change belongs in the final campaign history. Every event carries a significance level,
separate from confidence: `trivial`, `minor`, `major` or `campaign_defining`. It lets a renderer offer a
concise summary, a normal history or a forensic log. Significance is the impact of the event, not how certain
it is.

Principles:

-   **One module judges impact.** Analyzers never set significance; a post-pass assigns it from a context rule
    for the event type, then a per-type table, then the default. Each entry carries its evidence or rationale,
    and no threshold is tuned to one campaign.
-   **Evidence events rank low.** An event that is evidence for the rules that explain it (a statistic shift,
    a band crossing, a rank change) is `trivial` on its own. Routine churn is `trivial`; leftover lists of
    geopolitical relations stay `minor`, so the unexplained residue is never hidden.
-   **Narrative events are ranked by their rule**, never below their most significant constituent.

Defined in `src/tinarrative/narrative/significance.py` (`assign_significance`, `significance_of`) and
`model/events.py` (`Significance`, `SIGNIFICANCE_ORDER`). `tinarrative events --min-significance` is the first
consumer.

### Entity-scaled score (design)

The levels rank an event by its type, so a coup in a leading power and one on a micro-state, a fleet action
and a skirmish of two ships, or a war between nuclear blocs and one between minor states share a level. This
design adds the weight of the entities involved. It is staged on the roadmap (*Entity-scaled significance*);
until a stage lands, the levels above hold.

**Score.** Every event carries an integer `score` from 0 to 100 beside its level, on a logarithmic scale where
ten points are ten times the stake:

``` text
score = clamp(base(type) + scale(stake), 0, 100)
scale = clamp(round(10 · log10(share / reference)), scale_min, scale_max)
```

The level is a fixed band over the score (`trivial` 0–24, `minor` 25–49, `major` 50–74, `campaign_defining`
75–100). `base(type)` is the midpoint of the band the type's rule or table names today, so an event without a
stake, or with a stake at the reference share, keeps its present level and the rules migrate one at a time.
The bands, the clamp and one reference share per measure are runtime settings, calibrated per measure.

**Stake.** A stake is a share of a world total in the same snapshot, never an absolute magnitude: magnitudes
grow by orders of magnitude over a campaign, shares stay comparable. It measures what the event moved, not
only who acted: the territory transferred, the nation whose government fell, every belligerent of a war, the
forces engaged in a battle. It is read on the interval's earlier side (what was at stake), on the later side
for an entity that exists only there. Only the types whose impact grows with the stake are scaled, and they
are listed explicitly; movement and churn are never scaled.

| Entity | Share |
| --- | --- |
| Nation | power share: the weighted mean of its shares of world GDP, population and strength (the game's published estimate, [nation statistics](game-data-notes/nation-metrics.md#armies-navies-and-a-strength-estimate)) |
| Region | share of world population |
| Federation, alliance, war side | sum of its members' power shares |
| Faction | Earth share (each nation's power share times the faction's share of its control points, summed) blended with its space share |
| Hab, organization | tier² over the total tier²: one tier-3 outweighs three tier-1 |
| Fleet | ship mass over the human ship mass |
| Battle | contested mass, below |
| Campaign-wide (milestones, climate, nuclear strikes) | none: the scale is 0 |

Because every term is a share, shares add: a war side, a federation or a faction's holdings are sums. The
takeover's top-GDP promotion becomes one case of the nation stake.

**Space and the alien faction.** Early in a campaign the alien faction holds nearly every space asset and the
human factions very few ([space assets](game-data-notes/space-assets.md)). A total that counts the aliens
would make them half the world from the start, and a human total alone would make one station half of space.
So the space totals count the human factions only (the alien faction's own stake is its Earth share, while an
asset event still measures its asset against that total), every space share is taken over `max(total,
saturation)`, and the space weight in a faction's stake ramps up as the human total reaches the saturation.
Until humans hold a real presence in space, factions are ranked by their Earth holdings.

**Battles.** Each side's mass (hull counts times the hull class's mass) is weighted, alien ships above 1
because they outclass human ships ton for ton. The contested mass is `smaller + min(larger, k · smaller)`:
mass beyond `k` times the opponent's adds nothing, so a large fleet swatting a scout is a skirmish, and the
outcome never changes the stake. Habs assaulted or destroyed are a second measure; the battle takes the higher
score. Losses are attributes for the narrator, not stake.

**Combination.** Stakes add in share space; the type sets the base:

``` text
development.score = max(base(rule) + scale(Σ shares of the rule's distinct stake entities),
                        max(score of every cited event))
```

Constituent scores are never summed: one fact is often recorded several times, and a sum would rank by record
count. The maximum stays the floor, and once atomic events are scaled, a micro-state's disappearance no longer
lifts every development that cites it. A conflict with nuclear-armed nations on opposite sides adds a
configured bonus, for escalation risk a share does not capture. Perspective (the player's faction) is not
impact and stays with the narrator.

**Provenance.** The score is interpretation. Each event records its `significance_basis` (base, measure,
share, scale, stake entities) in the `events` output; the narrator package keeps `score` and drops the basis.

**Consumers.** The level stays the deterministic cut-off (`--min-significance`, continuity recall, the
citation audit). The score orders within it: chapter length shares and recall follow it, and the narrator
prompt leads with the highest-scored developments.

# 13. Narrative Rendering

Rendering consumes the narrator package (13.1) rather than raw save differences. The Markdown renderer is one
consumer; an LLM narrator (section 20) is another. The prose generator is never the authoritative source of
event facts: structured events remain canonical.

The deterministic Markdown of `tinarrative events` is a forensic view, not a history: atomic events per
interval, and with `--narrative` the narrative events by the year they start in. A narrative line reads,
conceptually:

``` text
<start> to <end> · faction.space_campaign · inferred, high · major
  actor: <faction A>; target: <faction B>; bodies: <B1>, <B2>
  constituents: hab.destroyed/..., faction.battle_outcome/...
```

Defined in `src/tinarrative/rendering/markdown.py` and `rendering/json_report.py`.

## 13.1 Narrator input

The product handed to an LLM, or to a reader who wants the facts without prose, is a *narrator package*, built
deterministically from one save sequence:

1.  the narrative events in chronological order, each with its span, roles, attributes, confidence,
    significance and constituent IDs;
2.  the situation reports (11.4), one per save;
3.  an entity glossary: the name and domain of every entity the package references by ID only, and the earlier
    names of a renamed entity, so prose never invents a name and never meets a bare ID;
4.  the atomic events the listed narrative events are built from, for drill-down and audit.

Every line carries event IDs so generated prose can cite them (section 20). The package is not a separate
command: `tinarrative events --narrative --format json` is its canonical form and the Markdown report's
narrative section its digest. The forensic view and the package are one report at different filter settings,
so they cannot drift apart ([events](commands/events.md)).

The package is for a reader, so it carries IDs and names but no provenance: it drops every source and every
file path. Provenance stays with the same run without `--narrative`, and a narrative event's sources are its
constituents', so citing an ID is enough to audit a sentence. Atomic events that only restate bookkeeping a
narrative event sums up are left out of the package.

A package too large for one model request is cut into *chapter packages* (20.3) without rewriting an entry.

Defined in `src/tinarrative/rendering/json_report.py` (`build_document`), `narrative/glossary.py`
(`build_glossary`) and `narrative/evidence.py` (`is_evidence`).

# 14. Repository Structure

The package is split into one subpackage per pipeline stage; see [README.md](../README.md#package-layout). The
exact names matter less than the separation of concerns.

# 15. Processing Modes

## Mode A --- Single diff

Two saves in, "what changed between these saves?" out (`tinarrative save diff`): the foundation for debugging
and validation.

## Mode B --- Ordered save sequence

The saves of one campaign in, a chronological event stream out.

Principles:

-   **Game time orders, never file names.** Saves are sorted by their game time; a save without one is
    rejected rather than placed by name. Byte-identical saves are one save with several paths.
-   **Two snapshots at most.** Each consecutive pair is analysed as one interval (diff, analyzers,
    significance, reconstruction), keyed by its later save. Consecutive intervals share their boundary
    snapshot, so the per-interval results concatenate without overlap.
-   **IDs are qualified by interval.** An event ID is unique within an interval only, so every ID gets an
    `@<interval key>` suffix before the streams are merged
    ([chronology](game-data-notes/chronology-and-deduplication.md)).
-   **Joining across intervals is aggregation.** Reconstruction rules see one interval; evidence split across
    a boundary is joined by narrative aggregation (section 11), which runs over the whole qualified stream and
    the situation reports. Per-interval analysis finds more than one outer diff of the first and last save,
    which hides intermediate states.

Defined in `src/tinarrative/sequence.py` (`survey`, `plan_sequence`, `run_sequence`, `analyze_interval`,
`narrative_events`) and `narrative/chronology.py` (`qualify`, `chronological`); the command is
[events](commands/events.md).

## Mode C --- Campaign directory

A save directory in; the application discovers saves, partitions them into campaigns, orders them and produces
the campaign history.

The serialized format has no observed campaign identifier, so partitioning uses a documented continuity
profile. Grouping is inference with provenance: every group carries the signals it was formed on, a conflict
or missing evidence produces separate or unclassified groups rather than an invented chronology, and `events`
refuses to mix groups. See [campaign grouping](game-data-notes/campaign-grouping.md).

Defined in `src/tinarrative/grouping.py` (`group_saves`, `CampaignGroup`, `select_campaign`) and
`parsing/continuity.py` (`campaign_profile`); the commands are [campaigns](commands/campaigns.md) and `events
--campaign`.

## Mode D --- Continuous capture

The game's save directory, watched while the game runs, in; a store holding every save the game wrote, grouped
by campaign, from which events and narration run at any time, out.

The game's rotating autosaves, combat and exit saves sample a campaign far more densely than manual saves, but
a file may be overwritten soon after it appears, so a save not copied then is lost. The save modes are
recorded in [save directory](game-data-notes/save-directory.md).

### Continuous capture (design)

Staged on the roadmap (*Continuous capture*). It applies the core principle (section 3) to storage: what was
captured is evidence and is kept byte for byte; everything read from it is derived and can be rebuilt.

``` text
save directory → capture (poll, settle, copy) → objects + capture log     evidence
  → index (one survey per object)                                          derived
  → campaigns (grouping, unchanged) → lines (save tree, current line)      inference
  → sequence plan → intervals (cached) → events, narration
```

**Capture** has one job, to win the race against the game, so it does as little as possible. It polls with the
standard library (no runtime dependencies, so no file-system watcher). A file is taken once its size and
modification time have stayed the same across two polls; capture reads it, re-checks the `stat`, hashes the
bytes (the identity `survey` already uses) and writes them unchanged and atomically into a content-addressed
object store. Every observation appends one line to a capture log, with a save-kind hint read from the name
for display only: names are not a chronology. Capture rejects nothing: a file that is not a supported save is
archived and marked when indexed, so a wrong rejection can be undone.

**Catch-up is the same pass.** On start, and in a one-shot run, every file that differs from its last
capture-log line is captured. Saves written while nothing was capturing join the timeline wherever their game
time places them. A save overwritten while nothing was capturing is gone, and the store does not pretend
otherwise.

**Index.** Each object is surveyed once (game time, campaign profile, build, status), recorded with a
fingerprint of the parser; a record from another parser is recomputed. Indexing runs after pending captures,
because a full parse is slow and the race is not.

**Campaigns.** Grouping is the rule of Mode C, applied to index records. A campaign reloaded and played
differently keeps its identity, so both attempts stay in one group and lines (below) split it. A store
campaign has a stable ID derived from its identity signals, because the selector key depends on the listing;
the selector key stays the name a user types.

**Sequence.** `plan_sequence` runs on the index records of one line instead of a fresh survey, and snapshots
load from objects. A save later than every other adds one interval; an earlier one, such as an old save
imported late, splits one interval in two.

**Interval cache.** An interval's analysis is a function of its two saves and the code, so its result
(unqualified events and both situation reports) is cached under the two object hashes and a fingerprint of the
analysis code. Qualification happens when the cache is read, so a split interval orphans one entry and
invalidates nothing else. Narrative aggregation is not cached: its windows and `open` depend on the last save,
and it needs no snapshot. Cache entries and objects are deleted only on request.

**One writer, no automatic narration.** An exclusive lock admits one capturing process per store; readers read
only objects and files written by rename, so they run while capture does. Capture and indexing never contact a
provider; a growing campaign is narrated in installments (20.7) when the user runs `narrate`.

**Privacy.** The store holds whole saves on the user's machine, outside the repository. The log carries
counts, sizes and hash prefixes, never a file name, a path beyond `safe_path` or a string read from a save
([debugging](debugging.md)).

### Lines (design)

When the player loads an earlier save and plays on, the saves written after it on the first attempt stop being
the campaign's history, but they stay in the store and keep the campaign's identity. Ordered by game time the
two attempts interleave, and every interval between them diffs two timelines. *Lines* separate them. Staged on
the roadmap (*Continuous capture*); until it lands, one campaign has one game-time order.

**Continuity test.** Save B *continues* save A (A no later than B) unless a *witness record* contradicts it. A
witness is a save-carried record (4.3) that the game-data notes observe to be carried forward unchanged along
one line of play: a log that only grows as a strict prefix, a keyed log that never loses a key, ledger entries
that are never rewritten. After a fork both attempts record their own battles, charges and losses, so their
witnesses disagree. The witness set and the exact contradiction rules come from the notes, not from this
section. The result is `contradicted` (naming the record), `consistent` or `undetermined`; it is inference
with provenance, reported like the grouping signals.

**Save tree.** A save's parent is the latest earlier save it continues, tested from the nearest backwards, so
a campaign without a reload costs one test per save and gives exactly today's sequence. `undetermined` counts
as consistent, because absence of evidence is not a fork. A fork save never captured is not needed: the new
line attaches to the nearest earlier save it continues, with a longer interval.

**Witness digest.** Each index record carries a digest per witness record, so the test reads two index records
and never a snapshot.

**Lines.** A *fork* is a save with more than one child. A line is named by its first save after a fork, the
original line by the campaign's first save. Selecting a line takes the path from the campaign's first save
through the line's first save to its newest descendant, following at each later fork the child holding the
most recently captured save. The sequence, interval keys and qualified IDs run on that path unchanged; the
interval cache, keyed by save hashes, serves every line.

**Current line.** In a store, the current line holds the most recently captured save. Saves given as paths
have no capture order, so a campaign with several lines is treated like a directory with several campaigns:
`events` and `narrate` require a line, list the lines, or ask through the picker.

**Abandoned lines** are kept and never deleted. The listing shows each line (fork, span, save count, whether
current), and any line can be analyzed or narrated by name, so an abandoned attempt reads as an alternate
history. No narrative mentions a reload: it is an act of the player, not an event of the campaign.

**Capture is unchanged.** A live capture earlier in game time than the newest save suggests a reload, but the
tree is built from the content of the saves, never from that hint.

# 16. Persistence Strategy

Modes A to C are file-oriented: they read the saves they are given and keep nothing between runs.

Mode D adds a store (design, staged on the roadmap): plain files, laid out so that two members are evidence
and everything else derives from them.

``` text
<store>/
  captures.jsonl                      # capture log, append-only        evidence
  objects/<sha256>.json.xz            # every distinct save, byte-exact evidence
  index/<sha256>.json                 # one survey per object           derived
  campaigns/<campaign-id>/
    campaign.json                     # identity signals, selector key  inference
    intervals/                        # interval cache                  derived
    narration/<name>/                 # narrate output, installments (20.7)
```

An object is named by the hash of the uncompressed bytes, so a decompressed object is exactly the file the
game wrote. Deleting the derived members loses nothing but time, apart from narration responses, which only a
provider can make again. The store lives in a per-user data directory or a configured location, never inside
the save directory, which belongs to the game.

A database remains a later option; the event model assumes no persistence technology.

# 17. Determinism and Reproducibility

Given the same save sequence and analyzer version, the system produces the same structured events:
deterministic structured analysis first, optional probabilistic prose generation after, and the structured
events remain authoritative. For the narrator (section 20) the boundary sits between request and response: the
chapter plan and every request are byte-deterministic functions of the package and the settings, while the
prose is not. The run manifest records both sides, so a history can be traced to its inputs even when it
cannot be reproduced word for word.

# 18. Testing Strategy

Testing is fixture-driven: small, hand-authored synthetic fixtures for parsers, diffs, analyzers,
reconstruction rules and narrative rules, golden outputs for rendering, and a few tests over real saves kept
out of the default run. See [testing](testing.md).

# 19. Handling Imperfect Saves

Real save data may be incomplete, inconsistent, version-dependent, partially undocumented or missing
historical information. The architecture treats absence of evidence as normal: a parser prefers `unknown` over
`false`, and an analyzer prefers "not enough evidence to infer" over a confidently invented event.

# 20. LLM Narration

An LLM turns structured events into prose and context; it is never the mechanism for factual reconstruction:

``` text
save → deterministic parser → objective diff → rule-based inference
     → structured narrative events → LLM-assisted prose
```

The contract between the two halves is the narrator package (13.1): the LLM receives narrative events,
situation reports and the glossary, and returns prose whose claims cite event IDs, so it can be audited. It
may order and phrase, but does not merge narrative events the rules kept apart, does not get the raw atomic
stream as its primary input, and never supplies a fact the package does not contain. Anything the package
cannot state (motives, the public framing of a move) is worded as interpretation, cites nothing, and never
becomes the premise of a later factual claim. The prompt and its rationale are in [narrator](narrator.md); the
command is [narrate](commands/narrate.md).

## 20.1 Command and data flow

``` text
saves (events pipeline) or package JSON (--package) → narrator package → chapter plan (20.3)
  → chapter packages + continuity (20.4) → requests (byte-deterministic)
  → provider (20.5, --send only) → assembly + citation audit (20.6)
```

`narrate` builds the package in-process from the same save inputs as `events`, or reads a finished one. Both
give the same package, so the narrator half depends only on the package's JSON form and its own settings,
never on `parsing`, `sequence` or the model types (a test enforces it). The package is the only interface
between the deterministic half and the narrator, and can be narrated on another machine or long after it was
built.

Sending is explicit. Without `--send` the command writes the chapter plan and every request and contacts
nothing, so a request can be reviewed, diffed or run by hand. The package carries no paths or provenance, but
it does carry the campaign, which with `--send` reaches a third party unless the provider is local.

## 20.2 Request parameters

The prompt reads a request block at the head of the user message, with three groups of keys: chosen by the
user (audience, citations, style, length); derived by the program but overridable (the period, from the
campaign's span and made coarser where saves are further apart than the period, since a period finer than the
saves can only be invented; the focus faction); and set by the program only (the chapter, its part, the dates
it covers). The block lists only the keys that are set, in a fixed order, so the same inputs send the same
bytes.

The significance level applies to the narrative only; of the atomic stream, only the constituents of the
listed developments are kept, as drill-down for detail and citation, not a second account.

Defined in `src/tinarrative/narrator/request.py` (`build_request`, `render_request`, `prompt_version`).

## 20.3 Token budget and chapters

A package grows with the number of saves, so a long campaign does not fit one request and `narrate` cuts it
into *chapters*, each its own request.

-   **Budget.** An input and an output token bound are settings, so a small local model and a large hosted one
    use the same planner.
-   **Local estimate.** Input size is estimated deterministically from the serialized request. The planner
    never asks a provider to count tokens, so chapter boundaries depend on the package and settings only.
    Reported token counts go into the manifest to check the estimate.
-   **Chapters** are contiguous runs of whole periods that start and end on a save. A development belongs to
    the chapter holding its start.
-   **Chapter packages** have the narrator package's schema restricted to the chapter, with an opening and a
    closing situation, plus `chapter` and `continuity` members. Slicing selects entries and never rewrites
    one.
-   **Over budget**, a period is reduced in a fixed, recorded order: drop the atomic stream, then split at
    save boundaries, then stop before sending and report the budget needed. Developments are never dropped and
    the significance level is never raised behind the user's back; either would remove facts without the
    reader knowing.

Defined in `src/tinarrative/narrator/chapters.py` (`plan_chapters`, `estimate`, `ChapterPlan`); settings in
[configuration](configuration.md).

## 20.4 Continuity

Continuity between chapters is built from the package, never from earlier prose. A chapter's `continuity`
holds the developments still running from an earlier chapter, marked as already told, and a capped digest of
the earlier chapters' major developments, so the model can refer back without inventing the past. The opening
situation is the previous chapter's closing one.

No chapter's prose is input to another: generated text is not a source, and an error in one chapter must not
become a premise of the next. Chapters are therefore independent requests that can be re-run, resumed, cached
or sent in parallel. The prompt's part rules decide which chapter opens the history and which ends on the
closing situation.

## 20.5 Providers

The narrator talks to a model through one provider-neutral request and one neutral completion (text, finish
reason, token counts); adapters translate for the `anthropic`, `openai` (also OpenAI-compatible servers) and
`ollama` APIs. Design rules:

-   no runtime dependencies: a standard-library HTTP transport behind an interface that tests replace with a
    fake; no test touches the network;
-   bounded retries on rate limits and server errors, honouring the provider's hint; a completion cut at its
    length limit or refused is a failed chapter, never a short one;
-   a local model's context is set from the budget, since a too-small context truncates input silently;
-   the model is always named by the user (no default model ID, which would go stale); settings profiles
    choose provider, model and limits;
-   API keys come only from an environment variable the profile names, never from a settings file, the output
    or a log;
-   narrator settings never change what `events` builds.

Defined in `src/tinarrative/narrator/providers.py` (`CompletionRequest`, `Completion`, `complete`) and
`narrator/transport.py` (`Transport`).

## 20.6 Output, audit and reproducibility

A run writes its requests, responses, the assembled `history.md` and a `manifest.json` into one directory.
Design rules:

-   The history names the provider, the model as reported, the prompt version (a hash of the prompt, so it
    cannot drift) and the campaign. Footnotes are renumbered across the whole history.
-   The manifest records the package hash, settings, chapter plan, request hashes, token counts and the
    citation audit.
-   The **citation audit** checks every cited ID against the chapter package it was written from and lists
    unmatched citations and uncited major developments. It reports and never rejects prose: a wrong citation
    is a finding for the prompt.
-   A chapter whose stored response came from an identical request is not sent again, so a run resumes where
    it stopped and a changed setting re-sends only the chapters it changes. Assembly reads only the output
    directory.
-   The run log carries counts, sizes and statuses, never a request, a response, a key or a string read from a
    save.

Defined in `src/tinarrative/narrator/assembly.py` (`assemble`, `citable`).

## 20.7 Installments (design)

A campaign that keeps growing (Mode D) is narrated more than once. Rerunning `narrate` over the grown package
re-plans every chapter: the derived period may change and every request names the chapter count, so every
chapter would be told again in new words. An *installment* narrates only what came after the last narration
and leaves the earlier prose as it was. Staged on the roadmap (*Continuous capture*); it works for any input,
a store campaign or save paths.

**Narration directory.** One subdirectory per installment, each with the layout of 20.6, plus a narration
record. The request options are fixed by the first installment and reused, so a period derived from a short
early span stays the period of the whole narration unless the user names another; the per-chapter coarsening
still applies.

**Seal.** An installment is sealed when it is assembled; its closing save is the seal point. Installment *n*
covers the intervals after the seal of installment *n − 1* up to the last save, planned by the chapter planner
over the full package restricted to those intervals, and opens on the sealing save's situation. A sealed
installment is never planned or sent again; resume works inside the open one.

**Parts.** Every installment after the first uses `middle` for all its chapters but its last, which is `last`.
No chapter reopens the history, so the prompt's part rules hold unchanged, and a sealed ending stays true of
the history up to its save.

**Continuity across installments** is built from the package, with sealed installments standing in for earlier
chapters: `earlier` from their stored requests, not their prose; `continuing` for developments running across
the seal or whose record changed after it was told; and `late` for developments that start before the seal but
appeared in no sealed request (a rule window spanning the seal finds them only once later saves exist). Late
developments are told at their own dates in the installment's first chapter. This adds one prompt rule, so the
prompt version changes for new requests only.

**History.** `history.md` concatenates the sealed installments and the current one, with one cover per
installment; footnotes are renumbered across the whole and the audit runs per installment.

**Drift.** A save can land inside a sealed span, or a later save can rewrite what a sealed development said.
The manifest lists the drift (sealed IDs that no longer exist, saves inside sealed spans no sealed request
covered). Nothing is re-narrated silently: the user chooses to unseal from an installment onward.

A reload (Mode D, *Lines*) can leave a seal on an abandoned line, whose prose tells a future the current line
no longer has. Appending then refuses and names the first installment off the current line; the user
re-narrates from there or keeps narrating the sealed line.

# 21. Architectural Summary

The project is a **compiler from game state to history**.

``` text
Serialized game state → normalized semantic state → observed state transitions → objective atomic events
  → inferred atomic events → grouped narrative events → campaign narrative
```

The most important modeling decisions: **state snapshots are the factual foundation**; **diffs represent
observable changes**; **atomic events represent concrete semantic developments**; **objective vs. inferred
describes epistemic status**; **atomic vs. narrative describes abstraction level**; **confidence and
significance are independent dimensions**; **evidence survives every transformation**; **rendering is
downstream and replaceable**.

This separation lets the project begin as a pragmatic save-diff CLI while keeping a credible path toward a
full campaign-history generator.
