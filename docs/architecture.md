# Terra Invicta Narrative Save Analyzer --- Architectural Vision

## 1. Purpose

Terra Invicta produces a rich, persistent simulation state, but the save
game is optimized for resuming play rather than explaining what
happened. A campaign can contain years of wars, political
transformations, faction struggles, space operations, technological
shifts, and other consequential changes, while the save itself does not
present those developments as a coherent history.

The **Terra Invicta Narrative Save Analyzer** is intended to reconstruct
that history from one or more Terra Invicta save files.

The central idea is to treat saves as **snapshots of a changing world**
and derive a progressively more semantic representation:

1.  **Raw save state** --- parsed game data.
2.  **Objective changes/events** --- facts directly evidenced by
    comparing states.
3.  **Inferred events** --- plausible actions or causes reconstructed
    from those changes.
4.  **Narrative events** --- semantically grouped developments suitable
    for human presentation.
5.  **Campaign narrative** --- chronological, readable history generated
    from the event stream.

The architecture should preserve the distinction between what the save
proves and what the analyzer infers. The system should be capable of
producing useful narratives without pretending that an inference is an
objective fact.

------------------------------------------------------------------------

## 2. Design Goals

### Primary goals

-   Reconstruct meaningful campaign history from ordinary Terra Invicta
    saves.
-   Work incrementally across a sequence of saves rather than requiring
    game telemetry.
-   Preserve provenance from every narrative claim back to save-state
    evidence.
-   Distinguish **objective evidence** from
    **interpretation/inference**.
-   Distinguish **atomic events** from higher-level **narrative
    events**.
-   Support multiple narrative views without changing the underlying
    analysis.
-   Make analyzers modular so new game systems can be added
    independently.
-   Make the initial implementation practical as a Python CLI and evolve
    it toward continuous campaign analysis.

### Secondary goals

-   Produce deterministic, inspectable intermediate outputs.
-   Make analyzer failures local rather than catastrophic.
-   Allow uncertain or incomplete reconstructions.
-   Support both per-save diffs and a cumulative campaign history.
-   Keep game-version-specific parsing concerns isolated from semantic
    analysis.

### Non-goals

-   Recreating the game's internal event log if one does not exist.
-   Guaranteeing that every inferred action is historically correct.
-   Building a complete game-state simulator.
-   Replacing the game's UI.
-   Requiring modification of the game or an in-game mod for the MVP.

------------------------------------------------------------------------

## 3. Core Architectural Principle

The project should be structured as a pipeline in which each stage adds
interpretation without destroying lower-level evidence.

``` text
Save files
   │
   ▼
[Save Loader / Parser]
   │
   ▼
[Normalized Save State]
   │
   ▼
[State Diff / Objective Event Detection]
   │
   ▼
[Inference / Event Reconstruction]
   │
   ▼
[Atomic Event Stream]
   │
   ▼
[Narrative Aggregation]
   │
   ▼
[Narrative Event Stream]
   │
   ▼
[Narrative Rendering]
   │
   ├── per-save Markdown
   ├── cumulative campaign Markdown
   └── future: other formats / UIs
```

A key property is that **narrative presentation is downstream of
analysis**. The renderer should not need to rediscover what happened.

------------------------------------------------------------------------

# 4. Data Model

The model deliberately uses several independent dimensions rather than
making one classification do too much work.

## 4.1 SaveSnapshot

A `SaveSnapshot` represents the normalized, analyzer-friendly state
extracted from one save.

Conceptually:

``` python
@dataclass
class SaveSnapshot:
    source: SaveSource
    game_version: str | None
    timestamp: datetime | None
    turn: int | None
    date: GameDate
    factions: dict[EntityId, FactionState]
    nations: dict[EntityId, NationState]
    regions: dict[EntityId, RegionState]
    armies: dict[EntityId, ArmyState]
    councilors: dict[EntityId, CouncilorState]
    organizations: dict[EntityId, OrganizationState]
    space: SpaceState
    technologies: dict[EntityId, TechnologyState]
    diplomacy: DiplomacyState
    economy: EconomyState
    research: ResearchState
    raw_metadata: dict[str, Any]
```

This is a **normalized semantic state**, not a 1:1 copy of the game's
serialized structure.

The parser should preserve enough raw/source information to allow
debugging and provenance, but downstream analyzers should depend
primarily on stable normalized objects.

------------------------------------------------------------------------

## 4.2 StateDiff

A `StateDiff` captures changes between two snapshots.

``` python
@dataclass
class StateDiff:
    before: SaveSnapshot
    after: SaveSnapshot
    changes: list[StateChange]
```

A `StateChange` is deliberately low-level:

``` python
@dataclass
class StateChange:
    domain: Domain
    entity_id: EntityId | None
    field: str
    before: Any
    after: Any
    evidence: Evidence
```

Examples:

-   Germany's controlling faction changed from Servants to Resistance.
-   Slovenia's owner changed from independent to EU.
-   A councilor disappeared from a faction.
-   A fleet's location changed.
-   A space asset was destroyed.
-   A technology changed state.
-   An army's composition changed.

The diff layer should remain relatively literal. It is not yet trying to
explain *why* something changed.

------------------------------------------------------------------------

# 5. Event Model

## 5.1 Event is the common semantic envelope

The system should use a common event abstraction while allowing
different semantic layers.

``` python
@dataclass
class Event:
    id: EventId
    date: GameDate
    event_type: EventType
    status: EventStatus
    confidence: Confidence
    sources: list[EvidenceRef]
    entities: list[EntityRef]
    attributes: dict[str, Any]
```

The important fields are:

-   **event type** --- what kind of thing happened.
-   **status** --- objective vs inferred.
-   **confidence** --- how strongly the reconstruction is supported.
-   **sources** --- what save changes support the event.
-   **entities** --- actors, targets, locations, assets, etc.
-   **attributes** --- event-specific structured data.

The model should avoid embedding prose in the core event representation.

------------------------------------------------------------------------

## 5.2 Objective vs. Inferred is one dimension

This distinction answers:

> **How directly is this event supported by the save data?**

### Objective event

A direct state transition.

Examples:

-   "The EU gained control of Slovenia."
-   "A Resistance councilor left the Servants."
-   "A fleet was destroyed."
-   "Technology X completed."

### Inferred event

A reconstructed action or causal explanation.

Examples:

-   "The EU annexed Slovenia."
-   "The Resistance purged the Servants from Germany."
-   "The fleet was defeated in battle."
-   "The councilor defected."

An inferred event may be strongly supported without being literally
persisted in the save.

This dimension should not be overloaded with presentation concerns.

------------------------------------------------------------------------

## 5.3 Atomic vs. Narrative is a separate dimension

This distinction answers:

> **How much of the event stream does this event represent?**

### AtomicEvent

The smallest meaningful semantic unit produced by analysis.

Examples:

-   `FactionControlChanged`
-   `CouncilorPurged`
-   `NationAnnexed`
-   `ArmyDestroyed`
-   `FleetDestroyed`
-   `TechnologyCompleted`
-   `FleetMoved`
-   `FactionJoinedWar`

An atomic event normally corresponds to one concrete transition or a
tightly reconstructed action.

### NarrativeEvent

A higher-level grouping of related atomic events that humans naturally
perceive as one development.

Examples:

-   **"The Resistance purge of Germany"**
    -   control changes
    -   councilor removals
    -   crackdown activity
    -   subsequent control consolidation
-   **"The European Union's annexation of Slovenia"**
    -   diplomatic relationship change
    -   ownership/control change
    -   political integration changes
-   **"The Servants' disastrous campaign in Eastern Europe"**
    -   several battles
    -   army losses
    -   territory changes
    -   strategic retreat

A narrative event can contain objective and inferred atomic events
simultaneously.

Therefore:

``` text
                 Objective / Inferred
                         │
                         │ independent
                         ▼
Atomic ────────────────► Narrative
```

These are orthogonal dimensions.

------------------------------------------------------------------------

# 6. Provenance and Evidence

Every derived event should be traceable to evidence.

``` python
@dataclass
class Evidence:
    save_id: SaveId
    path: str | None
    domain: str
    description: str
    before: Any
    after: Any
```

An event can reference multiple evidence records.

For example, an inferred "purge" might cite:

-   councilor membership disappeared,
-   councilor status changed,
-   control of the nation changed,
-   faction ownership changed.

The renderer can use provenance for:

-   confidence indicators,
-   debugging,
-   verbose analysis output,
-   future interactive inspection.

The system should never lose the evidence merely because a higher-level
narrative event was created.

------------------------------------------------------------------------

# 7. Confidence

Confidence is distinct from objective/inferred classification.

Suggested levels:

``` python
class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

Examples:

-   Direct ownership field changed → high confidence objective event.
-   A destroyed fleet plus matching disappearance of opposing assets →
    high/medium confidence battle inference.
-   Several indirect changes suggest a purge → medium confidence
    inferred event.
-   A strategic motivation reconstructed from timing alone → low
    confidence interpretation.

Confidence should describe **the analyzer's confidence in the
reconstruction**, not how important the event is.

------------------------------------------------------------------------

# 8. Entity Model

Events should reference stable logical entities rather than embedding
arbitrary strings.

Useful entity categories include:

-   Faction
-   Nation
-   Region
-   Councilor
-   Army
-   Fleet
-   Ship
-   SpaceStation
-   SpaceBody
-   Technology
-   Organization
-   War / Conflict
-   Location

Entity IDs should be stable across snapshots whenever the underlying
game entity can be identified.

Where the game does not provide stable IDs, the project should use
carefully designed identity heuristics and record identity uncertainty.

------------------------------------------------------------------------

# 9. Analyzer Architecture

Analyzers should operate against normalized state and/or diffs and emit
events.

``` python
class Analyzer(Protocol):
    def analyze(
        self,
        before: SaveSnapshot,
        after: SaveSnapshot,
        diff: StateDiff,
    ) -> list[AtomicEvent]: ...
```

Potential analyzer families:

``` text
analyzers/
  politics/
    control_changes.py
    councilors.py
    diplomacy.py
    nations.py

  military/
    armies.py
    battles.py
    wars.py
    occupations.py

  space/
    fleets.py
    battles.py
    stations.py
    launches.py

  technology/
    research.py

  economy/
    resources.py
    institutions.py

  faction/
    faction_state.py
```

The exact decomposition should follow discovered game data rather than
prematurely mirroring every field in the save.

Analyzers should be independently testable.

------------------------------------------------------------------------

# 10. Event Reconstruction

Some meaningful events will not be directly visible as a single state
transition.

The reconstruction layer should therefore support rules that combine
evidence.

Example:

``` text
Observed:
  - Nation control changes from Servants → Resistance
  - Servants councilor disappears
  - Resistance councilor appears
  - Control point count changes
  - No corresponding diplomatic transfer

Possible reconstruction:
  → "Resistance purge of Servant control"

Status:
  inferred

Confidence:
  medium/high

Evidence:
  all five changes
```

The reconstruction system should favor explicit rules over opaque
heuristics.

Where multiple explanations fit the evidence, the model should permit:

-   multiple candidate events,
-   reduced confidence,
-   or a conservative objective description.

The analyzer should not invent unsupported causality simply to produce
nicer prose.

------------------------------------------------------------------------

# 11. Narrative Aggregation

Narrative aggregation operates on atomic events.

Its job is to identify clusters that form coherent human-scale
developments.

Inputs:

``` text
Atomic events
  ├── temporal proximity
  ├── shared entities
  ├── shared locations
  ├── causal relationships
  ├── event types
  └── strategic context
```

Output:

``` python
@dataclass
class NarrativeEvent:
    id: EventId
    start_date: GameDate
    end_date: GameDate
    title_hint: str | None
    event_type: NarrativeEventType
    constituent_events: list[EventId]
    significance: float
    confidence: Confidence
    sources: list[EvidenceRef]
    entities: list[EntityRef]
    attributes: dict[str, Any]
```

Narrative aggregation should be conservative initially.

A simple first implementation can use:

-   time windows,
-   shared faction,
-   shared nation/location,
-   event-type compatibility,
-   explicit causal links.

Later implementations can add strategic and semantic reasoning.

------------------------------------------------------------------------

# 12. Significance

Not every state change belongs in the final campaign history.

Events should carry a significance score or category, separate from
confidence.

For example:

``` python
class Significance(Enum):
    TRIVIAL = "trivial"
    MINOR = "minor"
    MAJOR = "major"
    CAMPAIGN_DEFINING = "campaign_defining"
```

This allows the renderer to offer different levels of detail:

-   concise campaign summary,
-   normal history,
-   forensic event log.

Significance should be based on the impact of the event, not how certain
it is.

------------------------------------------------------------------------

# 13. Narrative Rendering

Rendering should consume narrative events rather than raw save
differences.

A renderer might produce:

``` markdown
## 2043

### The European Union absorbs Slovenia

The European Union brought Slovenia into its political sphere, expanding its control in Central Europe.

### Resistance consolidates Germany

The Resistance removed remaining Servant influence from Germany and established itself as the dominant faction.
```

A verbose renderer might additionally expose:

``` markdown
> Inferred event — medium confidence

Evidence:
- Germany's controlling faction changed.
- Servant councilor/control data disappeared.
- Resistance control increased.
```

The prose generator should not be the authoritative source of event
facts. Structured events remain canonical.

------------------------------------------------------------------------

# 14. Repository Structure

A plausible Python repository:

``` text
terra-invicta-narrative/
├── pyproject.toml
├── README.md
├── LICENSE
├── docs/
│   ├── architecture.md
│   ├── roadmap.md
│   └── game-data-notes/
│
├── src/
│   └── tinarrative/
│       ├── cli.py
│       │
│       ├── io/
│       │   ├── save_loader.py
│       │   └── save_discovery.py
│       │
│       ├── model/
│       │   ├── snapshot.py
│       │   ├── entities.py
│       │   ├── changes.py
│       │   ├── events.py
│       │   └── evidence.py
│       │
│       ├── parsing/
│       │   ├── raw_save.py
│       │   ├── normalization.py
│       │   └── game_version.py
│       │
│       ├── diff/
│       │   └── state_diff.py
│       │
│       ├── analyzers/
│       │   ├── base.py
│       │   ├── politics/
│       │   ├── military/
│       │   ├── space/
│       │   ├── technology/
│       │   └── faction/
│       │
│       ├── reconstruction/
│       │   ├── rules.py
│       │   └── inference.py
│       │
│       ├── narrative/
│       │   ├── aggregation.py
│       │   ├── significance.py
│       │   └── chronology.py
│       │
│       └── rendering/
│           ├── markdown.py
│           └── templates/
│
└── tests/
    ├── fixtures/
    ├── parser/
    ├── diff/
    ├── analyzers/
    ├── reconstruction/
    ├── narrative/
    └── rendering/
```

The exact package names are not important; the separation of concerns
is.

------------------------------------------------------------------------

# 15. Processing Modes

## Mode A --- Single diff

Input:

``` text
save_A, save_B
```

Output:

``` text
What changed between these saves?
```

This is the foundation for debugging and MVP validation.

## Mode B --- Ordered save sequence

Input:

``` text
save_001
save_002
save_003
...
```

Output:

``` text
chronological sequence of events
```

This enables campaign history generation.

## Mode C --- Campaign directory

Input:

``` text
Documents/My Games/TerraInvicta/saves/
```

The application discovers saves, orders them, processes new snapshots,
and produces/updates campaign history.

## Mode D --- Incremental/watch-oriented analysis

Future capability:

``` text
new save detected
   ↓
analyze only new interval
   ↓
append/update event store
   ↓
regenerate affected narrative
```

This should be enabled by the architecture but does not need to be part
of the first implementation.

------------------------------------------------------------------------

# 16. Persistence Strategy

The first version can remain file-oriented:

``` text
save → parse → analyze → markdown
```

As campaign-scale processing develops, introduce a structured analysis
store.

Potential storage:

``` text
campaign/
  metadata.json
  snapshots/
  diffs/
  events/
  narrative/
  history.md
```

A SQLite database is a likely later option when querying, incremental
updates, and cross-campaign analysis become important.

The event model should therefore avoid assumptions that require a
particular persistence technology.

------------------------------------------------------------------------

# 17. Determinism and Reproducibility

Given the same save sequence and analyzer version, the system should
ideally produce the same structured events.

This is especially important if probabilistic/LLM-assisted narrative
generation is added later.

Recommended principle:

``` text
Deterministic structured analysis
        ↓
optional probabilistic prose generation
```

The structured event store remains authoritative.

------------------------------------------------------------------------

# 18. Testing Strategy

Testing should be heavily fixture-driven.

Important fixture types:

### Parser fixtures

Representative raw save fragments and complete saves.

### Diff fixtures

Before/after snapshots with known changes.

### Analyzer fixtures

Known state transitions producing expected atomic events.

### Reconstruction fixtures

Multiple changes that should combine into a single inferred event.

### Narrative fixtures

Sequences of atomic events expected to form one or more narrative
events.

### Golden-output fixtures

Structured event stream → expected Markdown.

Tests should favor small, synthetic fixtures for individual rules and a
smaller number of real saves for integration tests.

------------------------------------------------------------------------

# 19. Handling Imperfect Saves

Real save data may be:

-   incomplete,
-   inconsistent,
-   version-dependent,
-   partially undocumented,
-   missing historical information.

The architecture should treat absence of evidence as normal.

A parser should prefer:

``` text
unknown
```

over:

``` text
false
```

and an analyzer should prefer:

``` text
not enough evidence to infer
```

over:

``` text
confidently invented event
```

------------------------------------------------------------------------

# 20. Future LLM Integration

An LLM may eventually be useful for:

-   turning structured events into polished prose,
-   suggesting titles,
-   grouping borderline events,
-   explaining strategic context,
-   producing alternate narrative styles.

It should not be the sole mechanism for factual reconstruction.

A safe architecture is:

``` text
save
 ↓
deterministic parser
 ↓
deterministic/objective diff
 ↓
deterministic or rule-based inference
 ↓
structured narrative events
 ↓
LLM-assisted prose
```

LLM output should reference structured event IDs so generated prose can
be audited.

------------------------------------------------------------------------

# 21. Architectural Summary

The project should be thought of as a **compiler from game state to
history**.

``` text
Serialized game state
        ↓
Normalized semantic state
        ↓
Observed state transitions
        ↓
Objective atomic events
        ↓
Inferred atomic events
        ↓
Grouped narrative events
        ↓
Campaign narrative
```

The most important modeling decisions are:

1.  **State snapshots are the factual foundation.**
2.  **Diffs represent observable changes.**
3.  **Atomic events represent concrete semantic developments.**
4.  **Objective vs. inferred describes epistemic status.**
5.  **Atomic vs. narrative describes abstraction level.**
6.  **Confidence and significance are independent dimensions.**
7.  **Evidence/provenance survives every transformation.**
8.  **Rendering is downstream and replaceable.**

This separation should allow the project to begin as a pragmatic
save-diff CLI while retaining a credible path toward a full
campaign-history generator.
