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
   │  entity collections + save-carried records (dated logs, counters)
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

### Implemented contract (`src/tinarrative/model/`)

The snippets above are conceptual; the implemented types differ as follows:

-   All model types are frozen dataclasses holding tuples, sorted
    deterministically on construction (collections by `EntityId`, changes by
    domain/entity/field). Each has a JSON-friendly `to_dict()`.
-   `EntityId(domain, key)` is domain-qualified; `EntityRef` adds the
    `IdentityConfidence` (`in-save-id`, `name-key`, reserved `heuristic`) and
    source state type, so differently-established identities never compare equal.
-   `Observed = FieldValue | Unknown`: a field absent from the save is
    `Unknown(reason)`, never `False`, zero or empty. `None` and `()` are known
    values. An `Unknown` may carry `raw`, the serialized value it could not
    interpret (for example the ID of an unresolved reference).
-   A resolved in-save reference is an `EntityRef` field value (domain, map ID,
    `in-save-id` confidence, owning state type). The parser resolves a reference
    only when the ID exists in the same save under the expected domain; otherwise
    the field is `Unknown(unresolved_reference, raw=...)`. Reference targets whose
    state type has no `EntityDomain` yet are kept as raw values.
-   `SaveSnapshot.date` is the ISO-8601 game timestamp or `Unknown`; `campaign_day`
    and `campaign_quarter` are the serialized turn-like counters. Every
    `EntityState` has a `SourceLocation` with the short state type, map ID and
    the RFC 6901 path of its serialized `Value` object.
-   `Evidence` keeps before/after values plus a `SourceLocation` for each side
    (save ID, state type, map ID, path; `TINationState:123` is the provenance key).
-   `StateDiff` and `StateChange` live in `model.changes`; `diff.state_diff`
    re-exports them and implements `diff_states`. Each change has a `ChangeKind`:
    `value` (one atomic known value on each side, strict equality so `1 != 1.0`),
    `membership` (lists of references or of names compared as multisets; order
    alone is not a change), `map` (objects compared key by key, the detail naming
    the keys), `unknown` (either side is `Unknown`; nothing is inferred from the
    known side), and `appeared`/`disappeared` (an entity present in one snapshot
    only, with `field = None` and no per-field changes). Entities are matched by
    `EntityId`; snapshot-level values are compared under the pseudo-domains
    `campaign` and `research` with no entity. The campaign singletons carry no
    `SourceLocation` yet, so those changes cite only the save; everything else
    cites state type, map ID and path on each side. The parser fills the faction, nation, region, control-point,
    councilor, army (both army state types), fleet, ship and hab collections
    (`parsing.fields` lists the observed fields it copies; habs are `TIHabState`
    objects in the `space object` domain). A reference field observed to point at
    more than one domain (councilor `location`: region or hab) resolves against
    that set, and the owning state type decides the resulting domain.
-   Research is the one explicitly typed substate: `SaveSnapshot.research`
    (`ResearchState`) keeps the `TIGlobalResearchState` singleton's collections
    with its location, and `SaveSnapshot.technologies` holds the name-keyed
    (`name-key` confidence) technology states derived from it, each with
    `finished`, `progress` and a path into the list it came from.
-   A fleet ID is valid only for the fleet's lifetime: merged fleets vanish and a
    fleet's `parentFleet` often names an ID absent from the save. The parser keeps
    that as `Unknown(unresolved_reference, raw=...)` rather than dropping it, so
    the diff layer sees the limitation; ships keep their IDs across merges.
-   Organizations have a collection but are not normalized yet; other space
    objects (bodies, orbits, hab sites, sectors, modules) resolve as reference
    targets only, and singular diplomacy and economy states are not modelled.
-   Save-carried records (section 4.3) are compared per owning entity and field
    with `ChangeKind.records`: `before`/`after` are the entry counts and the
    `RecordsDetail` lists the entries added, removed and (for keyed records)
    changed. Logs are compared as multisets of entries, keyed records by key,
    and single-value records (counters, a date, a reference list) like ordinary
    fields. A set that is `Unknown` on one side gives an `unknown` change.
-   The normalizer never drops information silently. Every structure outside its
    code-form schema (`parsing.inventory`, `parsing.fields`) is reported through
    `parsing.unknowns.UnknownCollector` as a content-free finding (state type, field,
    JSON shape, counts) and never coerced into a model value: an unlisted field is
    still not copied, and a reference to an unexpectedly owned ID still resolves to
    `Unknown(unresolved_reference)`. The `maintenance` package persists findings in
    `docs/game-data-notes/unknowns/registry.json` for triage into the schema.

## 4.3 Save-carried records

Between objective snapshot state and inferred events sits a layer the save
carries literally: dated logs and cumulative counters that no field of the
same snapshot can re-derive. Observed examples (2026-10-13, five
private saves of one campaign, structure only): a faction's resource ledger
since campaign start (`Transactions`), its hab destruction log, the control
points it lost with the date last lost, the alien sites it knows with the date
last updated, its kill lists and milestones, cumulative counters such as
`abductions` and `atrocities`, and a nation's last executive change with its
cause. Across the four consecutive intervals of the sample (checked 2026-10-14),
the destruction logs, milestones and kill lists only grew (the earlier value was
a strict prefix of the later one), the keyed records never lost a key, and the
ledger grew by appending for most labels while a minority of labels were
rewritten wholesale (see the field map). These fill the gaps between sparse
saves with exact dates, so they must be kept as evidence in their own right:
never folded into inferred events and never acknowledged as `derived_history`.

A field qualifies as a record when its entries are dated or cumulative, are not
derivable from the rest of the snapshot, and are carried forward from save to
save rather than recomputed from current state. Rolling windows and running
histories the game recomputes from state the snapshot already holds are
`derived_history` and stay unnormalized.

Implemented contract (`model/records.py`, `parsing/records.py`):

-   `parsing.fields.RECORD_FIELDS` lists the record fields per state type with a
    `RecordKind` (ledger, destruction log, name log, dated references, reference
    values, label values, dated labels, executive change, counter, date,
    reference list). They are known to the unknowns scan but are not copied into
    the `EntityState`.
-   Each record field of each entity becomes one `RecordSet(owner, field, kind,
    location, entries)` on `SaveSnapshot.records`, sorted by owner then field.
    Entries are typed (`LedgerEntry`, `DestructionEntry`, `KeyedEntry`,
    `ItemEntry`), keep serialized order and their index, decode componentized
    dates to ISO-8601 text, and resolve references exactly like entity fields
    (an unresolvable reference is `Unknown(unresolved_reference, raw=...)`).
-   Provenance is state type + map ID + field + index. The set's
    `SourceLocation` points at the field (`<entity Value path>/<field>`) and
    `RecordSet.entry_location` extends it to one entry (`/<label>/<index>` for a
    ledger, `/<index>` for arrays and pair maps, `/<key>` for label maps).
-   An absent field gives `entries = Unknown()`; a field without the documented
    shape gives `Unknown(unparseable, raw)` plus an `unexpected_field_shape`
    finding. A problem inside one element (an unparseable date, an unresolvable
    key) stays inside that entry, so the rest of the log remains evidence.
-   The diff stage treats new entries since the previous save as evidence and
    never re-derives them: a `records` change lists the entries added and, when
    entries of the earlier save are gone (observed for some ledger labels), the
    entries removed, literally; it never assumes a log is append-only. Downstream
    stages may date an objective event by a record entry itself rather than by
    the save interval, but must cite the entry as evidence.

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

Save-carried records (section 4.3) are objective evidence of a third sort: a
ledger entry or a destruction-log entry is literally persisted, dated by the
game, and not a transition between two snapshots. An event built from one is
objective and dated by the entry; the record itself is never an inference.

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

Evidence that cites a save-carried record names the entry, not only the
owning entity: state type, map ID, field and index
(`RecordSet.entry_location`).

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
The current per-domain strategy is in
[entity identity](game-data-notes/entity-identity.md).

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

### Implemented contract (`src/tinarrative/analyzers/`)

The first family is `analyzers/politics/`: `ControlPointAnalyzer`,
`NationAnalyzer` and `CouncilorAnalyzer`, run together by
`analyzers.run_analyzers(POLITICS_ANALYZERS, before, after, diff)`. They read
the `StateDiff` only (never re-deriving a fact from the snapshots; the
snapshots supply context such as an entity's own reference or a control
point's nation) and emit objective events whose sources are the literal
changes (section 5.2). Shared machinery for every family lives in
`analyzers/common.py`: a change index, the `Transition` classifier (`set`,
`cleared`, `changed`, `unresolved`; a side that is `missing` or `unparseable`
is a schema gap and emits nothing), snapshot lookup, the membership ledger and
the event builder.

Ownership and control are kept distinct by analyzer and type prefix:

-   `control_point.*` speaks only about a control point's `faction`
    (controller), `nation` and presence, plus `control_point.loss_recorded`
    for every `lostControlPoints` entry added or re-dated (record-dated, and
    also cited as corroboration by a matching controller change).
-   `region.nation_changed` and `nation.*` speak about territory, capital,
    federation (a raw value: the state type has no entity domain), breakaway
    links, one `nation.relation_changed` per nation pair and direction for
    `allies`/`rivals`/`wars` (the mirrored entry on the other nation is merged
    and marked `reciprocal`), presence, and the literal `lastExecutiveChange`
    record (`nation.executive_change_recorded`; its `cause` string is an
    attribute only).
-   `councilor.*` speaks about a councilor's `faction`, `status`, `location`,
    `detainingFaction` and presence.

A nation's `controlPoints` list means which control points belong to the
nation, never "faction X controls nation Y"; that is a reconstruction rule
for later. Members of the handled reference lists (`faction.controlPoints`,
`faction.councilors`, `nation.controlPoints`, `nation.regions`,
`nation.breakaways`, the relation lists) that no event explains are reported
as `<owner>.<field>_changed`, so no literal change on them is dropped; a list
unresolved on one side is one such event with `transition = unresolved`.
Everything else (councilor `orgs`, `XP`, `priorLocation`; nation statistics
and claims; control-point timers and priorities; region occupation and
annexation flags) stays in the diff and is left to other analyzers or to the
diff report. Deliberately out of reach of every analyzer: naming a purge,
coup, annexation or defection.

The asset families follow the same contract and are run together with the
politics family as `analyzers.ALL_ANALYZERS` (or separately as
`MILITARY_ANALYZERS`, `SPACE_ANALYZERS`, `TECHNOLOGY_ANALYZERS`). A handled
reference list is owned by the analyzer of the entities it contains, so no two
analyzers report the same leftover and `run_analyzers` never sees an ID twice:

-   `analyzers/military/armies.py` (`ArmyAnalyzer`): `army.region_changed`
    (`currentRegion`, mirrored by the region `armies` lists),
    `army.faction_changed` (mirrored by the faction `armies` lists),
    `army.destroyed_changed`, `army.strength_changed`, `army.type_changed`,
    `army.deployment_type_changed`, `army.home_region_changed`, presence
    (citing every faction, nation and region `armies` list that names the army
    on the existing side) and the leftovers `faction.armies_changed`,
    `nation.armies_changed`, `region.armies_changed`. A nation's `armies` list
    has no mirroring army field, so a region move leaves its nation entries as
    leftovers rather than guessing which nation an army belongs to.
-   `analyzers/space/fleets.py` (`FleetAnalyzer`): `fleet.faction_changed`
    (mirrored by faction `fleets`), `fleet.docked_location_changed` (mirrored
    by hab `dockedFleets`), `fleet.orbit_changed`, `fleet.barycenter_changed`,
    `fleet.parent_fleet_changed`, `fleet.in_combat_changed`, presence and the
    leftovers `faction.fleets_changed`, `hab.docked_fleets_changed`.
-   `analyzers/space/ships.py` (`ShipAnalyzer`): `ship.fleet_changed`
    (mirrored by fleet `ships`), `ship.last_refit_date_changed`, presence and
    the leftover `fleet.ships_changed`.
-   `analyzers/space/habs.py` (`HabAnalyzer`, prefix `hab.` for `TIHabState`
    objects of the `space object` domain): `hab.faction_changed`,
    `hab.type_changed`, `hab.tier_changed`, `hab.in_combat_changed`,
    `hab.under_assault_changed`, `hab.under_bombardment_changed`,
    `hab.core_completed_changed`, presence without corroboration, and
    `faction.hab_destruction_recorded` for every `HabDestructionLog` entry
    added (record-dated; it names a hab type and a space body, never a hab ID,
    so it is not linked to any `hab.disappeared`).
-   `analyzers/technology/research.py` (`TechnologyAnalyzer`; identity is the
    template-name key): `technology.completed` when a technology's `finished`
    goes from false to true or it appears already finished, corroborated by the
    research singleton's `finished_techs_names` member; `technology.finished_changed`
    for any other literal transition; `technology.appeared` /
    `technology.disappeared` for progress-only or vanished states; the leftover
    `research.finished_techs_changed` for a name no technology event claimed.

Wording rule: the words *destroyed*, *destruction* and *refit* occur only in
event types whose primary source is the save field that literally carries them
(`destroyed`, `HabDestructionLog`, `lastRefitDate`); the fixture-pair tests
enforce it. A fleet absent from the later save, a `parentFleet` that no longer
resolves, a ship whose `fleet` is unresolved, and a vanished army or hab are
reported as absent or unresolved, never as a merge, loss or battle. Left in the
diff on purpose: army `priorRegion`, operations and transit dates; fleet
`trajectory`, position, operations and bombardment fields; ship propellant,
armor, damage and `kills`; hab `sectors`, `councilorsOnBoard` and orbit data;
technology `progress` values (a missing progress entry is `Unknown`, which
`classify` treats as a schema gap); project-name lists; faction `Kills` and
`armiesLost` records.

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
│       ├── inspection/        # raw structural report (`tinarrative inspect`)
│       ├── identity.py        # entity-identity table and ID census
│       │
│       ├── io/
│       │   ├── save_loader.py
│       │   └── save_discovery.py
│       │
│       ├── model/
│       │   ├── snapshot.py
│       │   ├── entities.py
│       │   ├── records.py         # save-carried records (section 4.3)
│       │   ├── changes.py
│       │   ├── events.py
│       │   └── evidence.py
│       │
│       ├── parsing/
│       │   ├── raw_save.py        # RawSave + parse_raw_save
│       │   ├── errors.py          # SaveLoadError categories
│       │   ├── fields.py          # ENTITY_FIELDS, RECORD_FIELDS, ACKNOWLEDGED_FIELDS
│       │   ├── normalization.py
│       │   ├── records.py         # record decoders
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
    ├── parsing/
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

Before ordering, discovery must partition files into campaign chains. The
serialized format currently has no observed campaign identifier, so this step
uses a documented continuity profile: internal game timestamp, the non-AI
player's faction reference, readable player-faction metadata, scenario
metadata, and stable world-anchor overlap. Byte-identical saves are aliases of
one snapshot. A conflict or missing continuity evidence must produce separate
or unclassified chains, not an invented chronology. See
[`game-data-notes/campaign-grouping.md`](game-data-notes/campaign-grouping.md).

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
