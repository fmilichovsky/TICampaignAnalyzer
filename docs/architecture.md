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
    councilor, organization, army (both army state types), fleet, ship, hab, war, federation and region alien state
    collections (`parsing.fields` lists the observed fields it copies; habs are `TIHabState`
    objects in the `space object` domain; `TISpaceBodyState` objects form the `space body` domain
    (`SaveSnapshot.space_bodies`: `displayName`, `templateName` and the parent `barycenter`); the five `TIRegion*State` alien sub-states share the
    `region alien state` domain and `SaveSnapshot.region_alien_states`, told apart by state type). The
    `TIGlobalValuesState` singleton is normalized as one in-save-ID entity of the `global values` domain
    (`SaveSnapshot.global_values`), so its fields, references and records have an owner and provenance like any
    entity's; a second entry is reported as `unexpected_singleton_count` and kept. `TINotificationQueueState` is
    normalized the same way (`notification queue` domain, `SaveSnapshot.notification_queue`) as the owner of the
    notification log. A reference field observed to point at
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
-   Space bodies are a named reference target: a hab's or fleet's `barycenter` and a destruction
    entry's `SpaceBody` resolve to the `space body` domain with `name` set (`Luna (space body:7)`)
    and a parent body, which is what narration needs ("a base on Ceres"). The save serializes no
    body kind; a moon is a body whose parent is not Sol. The other space objects (orbits, hab
    sites, Lagrange points, sectors, modules) resolve as reference targets only, and singular
    diplomacy and economy states are not modelled.
-   Every normalized entity carries its `displayName`, and a resolved `EntityRef` carries it as
    `name`. `describe_event`, the Markdown and the JSON of `tinarrative events` render it as
    `Name (domain:key)` (`EntityRef.label`), keeping the ID for audit; the `diff` text report stays
    literal. Councilor names are player content: allowed
    in the user's own output, never in logs or fixtures.
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
same snapshot can re-derive. Examples: a faction's resource ledger
since campaign start (`Transactions`), its hab destruction log, the control
points it lost with the date last lost, the alien sites it knows with the date
last updated, its kill lists and milestones, cumulative counters such as
`abductions` and `atrocities`, and a nation's last executive change with its
cause. Most of these only grow, but not all (the observed lifecycle of each is in
the field map and the higher-level event sources). These fill the gaps between sparse
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
    reference list, labelled references, notification log, combat log). They are known to the unknowns scan but are not copied into
    the `EntityState`.
-   Each record field of each entity becomes one `RecordSet(owner, field, kind,
    location, entries)` on `SaveSnapshot.records`, sorted by owner then field.
    Entries are typed (`LedgerEntry`, `DestructionEntry`, `KeyedEntry`,
    `ItemEntry`, `NotificationEntry`, `CombatEntry`), keep serialized order and their index, decode componentized
    dates to ISO-8601 text, and resolve references exactly like entity fields
    (an unresolvable reference is `Unknown(unresolved_reference, raw=...)`).
-   A record of a campaign-wide singleton is owned by that singleton's entity
    (`global values` for `TIGlobalValuesState`: global milestones and the
    narrative-event logs; `notification queue` for `TINotificationQueueState`: the
    notification log), not by a pseudo-domain without an entity.
-   A log is compared as a multiset of `diff_key(entry)`. For most kinds that is the whole
    entry without its index. A notification is identified by template, date and summary, so an
    entry whose subject, outcome or faction lists were rewritten is `changed`, not removed and
    re-added. Its members outside `RECORD_ENTRY_MEMBERS` are reported as the unknown field
    `notificationSummaryQueue[].<member>`. A subject whose target type has no domain
    (`UNTRACKED_REFERENCE_TARGETS`) stays unresolved without a finding.
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
    entries of the earlier save are gone (some ledger labels), the
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
`NationAnalyzer`, `NationMetricAnalyzer`, `WarAnalyzer`, `FederationAnalyzer`,
`CouncilorAnalyzer` and `OrganizationAnalyzer`, run together by
`analyzers.run_analyzers(POLITICS_ANALYZERS, before, after, diff)`. They read
the `StateDiff` only (never re-deriving a fact from the snapshots; the
snapshots supply context such as an entity's own reference or a control
point's nation) and emit objective events whose sources are the literal
changes (section 5.2). Shared machinery for every family lives in
`analyzers/common.py`: a change index, the `Transition` classifier (`set`,
`cleared`, `changed`, `unresolved`; a side that is `missing` or `unparseable`
is a schema gap and emits nothing), snapshot lookup, the membership ledger and
the event builder. The builder adds `faction_kinds` to every event that names a
faction entity: each faction's ID mapped to `alien` (`templateName`
`AlienCouncil`) or `human`, read from the snapshots as context, never evidence.

Ownership and control are kept distinct by analyzer and type prefix:

-   `control_point.*` speaks only about a control point's `faction`
    (controller), `nation` and presence, plus `control_point.loss_recorded`
    for every `lostControlPoints` entry added or re-dated (record-dated, and
    also cited as corroboration by a matching controller change).
-   `region.nation_changed` and `nation.*` speak about territory, capital,
    breakaway links, one `nation.relation_changed` per nation pair and
    direction for `allies`/`rivals` (the mirrored entry on the other nation is
    merged and marked `reciprocal`), presence (with `population`, the summed
    `populationInMillions` of the nation's regions on the existing side), and the
    literal `lastExecutiveChange` record (`nation.executive_change_recorded`; its
    `cause` string is an attribute only). Also from `NationAnalyzer`:
    `nation.claims_changed` and `nation.hostile_claims_changed`, one per nation
    and list with the regions `added` and `removed` (each cited; the regions'
    current nations are context entities); `nation.renamed` for a `displayName`
    change, carrying both literal names; `nation.unrest_attempts_changed`, one
    per nation and faction whose `factionUnrestAttempts` count differs (`before`/
    `after`, `null` where the faction is not listed); and
    `nation.new_government_recorded`, dated by the new `dateOfNewGovernment`
    value.
-   `nation.statistic_shifted` (`analyzers/politics/nation_metrics.py`,
    `NationMetricAnalyzer`) reports a nation statistic (`GDP`, `inequality`,
    `education`, `democracy`, `cohesion`, `unrest`, `sustainability`,
    `militaryTechLevel`, `spaceFunding_year`, `numNuclearWeapons`,
    `numControlPoints`, and each `publicOpinion` key on its own) that shifted
    past its threshold. A threshold is `max(floor, rate × months)` over the
    interval between the two save dates, so short intervals need a real step
    and long ones more than routine drift; the two discrete counts fire on
    any change. Attributes are `statistic` (and `key` for `publicOpinion`),
    `before`, `after`, `relative_change` (`null` from zero) and
    `interval_days`; for the six statistics with a
    `tracker_<Statistic>ChangeReason_AllTime` map, `causes` maps each reason
    whose cumulative value moved to its delta (the deltas sum to the shift),
    and the tracker change is cited as corroboration. Nations without regions
    on both sides are placeholders with frozen values and are skipped. The
    thresholds and their evidence live in that module; the event never names
    what the causes amount to (annexation, unification), which is
    reconstruction.
-   `war.*` (`analyzers/politics/wars.py`, `TIWarState` objects of the `war`
    domain) speaks about `war.appeared` (record-dated by the war's literal
    `startDate` when present) and `war.disappeared`, each citing every nation
    `wars` entry between the two alliances on the existing side;
    `war.alliance_changed` per nation added to or removed from
    `_attackingAlliance`/`_defendingAlliance` (attribute `side`), citing the
    member's `wars` entries against the opposing alliance;
    `war.attacker_changed`, `war.defender_changed`; and
    `war.last_fighting_changed` (the `dateOfLastFighting` record, dated by its
    new value). The analyzer owns the nation `wars` lists: an entry no war
    explains is a `nation.relation_changed` with `relation = wars`, exactly as
    for `allies` and `rivals`, and an alliance list unresolved on one side is
    `war.attacking_alliance_changed`/`war.defending_alliance_changed`.
-   `federation.*` (`analyzers/politics/federations.py`) speaks about
    `federation.members_changed` per member of `members`, citing the member's
    `nation.federation` change, and `federation.appeared`/`disappeared`, citing
    the members' `federation` changes. A `nation.federation` change no member
    change or presence explains is `nation.federation_changed`.
    `federation.renamed` is one event per federation whose `displayName` or
    `federationName` changed, citing each changed field and carrying the
    literal names.
-   `organization.*` (`analyzers/politics/organizations.py`) speaks about
    `organization.assigned_councilor_changed`, citing the councilors' `orgs`
    entries (and the faction `unassignedOrgs` entry) as corroboration,
    `organization.faction_orbit_changed` and `organization.appeared`/`disappeared`.
    Councilor `orgs` and faction `unassignedOrgs` changes no organization change
    explains are `councilor.orgs_changed` and `faction.unassigned_orgs_changed`.
-   War vocabulary stays out of these types and messages: no event says a war
    was declared, won or lost, or that peace was made; that is reconstruction.
-   `councilor.*` speaks about a councilor's `faction`, `status`, `location`,
    `detainingFaction` and presence.

A nation's `controlPoints` list means which control points belong to the
nation, never "faction X controls nation Y"; that is a reconstruction rule
for later. Members of the handled reference lists (`faction.controlPoints`,
`faction.councilors`, `nation.controlPoints`, `nation.regions`,
`nation.breakaways`, the relation lists, the war alliances, federation
`members`) that no event explains are reported
as `<owner>.<field>_changed`, so no literal change on them is dropped; a list
unresolved on one side is one such event with `transition = unresolved`.
Everything else (councilor `orgs`, `XP`, `priorLocation`; nation statistic
changes below their threshold and tracker maps that changed without their
statistic; control-point timers and priorities; region occupation and
annexation flags) stays in the diff and is left to other analyzers or to the
diff report. Deliberately out of reach of every analyzer: naming a purge,
coup, annexation or defection.

The asset families follow the same contract and are run together with the
politics family as `analyzers.ALL_ANALYZERS` (or separately as
`MILITARY_ANALYZERS`, `SPACE_ANALYZERS`, `TECHNOLOGY_ANALYZERS`, `ALIEN_ANALYZERS`). A handled
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
    leftovers rather than guessing which nation an army belongs to. A presence
    event of a `TIMegafaunaArmyState` army carries `megafauna = True` (regular
    armies carry no such attribute). Every `army.*` event names the army's home
    nation (the `nation` of its `homeRegion`), when known, as an entity and as
    attribute `home_nation`: context, never cited.
-   `analyzers/space/fleets.py` (`FleetAnalyzer`): `fleet.faction_changed`
    (mirrored by faction `fleets`), `fleet.docked_location_changed` (mirrored
    by hab `dockedFleets`), `fleet.orbit_changed`, `fleet.barycenter_changed`,
    `fleet.parent_fleet_changed`, `fleet.in_combat_changed`, presence and the
    leftovers `faction.fleets_changed`, `hab.docked_fleets_changed`.
-   `analyzers/space/ships.py` (`ShipAnalyzer`): `ship.fleet_changed`
    (mirrored by fleet `ships`), `ship.last_refit_date_changed`, presence and
    the leftover `fleet.ships_changed`. A presence event carries `hull`, the
    `hullName` of the design the ship's `templateName` names in its fleet
    faction's `shipDesigns`, when that resolves; the design name never appears.
-   `analyzers/space/habs.py` (`HabAnalyzer`, prefix `hab.` for `TIHabState`
    objects of the `space object` domain): `hab.faction_changed`,
    `hab.type_changed`, `hab.tier_changed`, `hab.in_combat_changed`,
    `hab.under_assault_changed`, `hab.under_bombardment_changed`,
    `hab.core_completed_changed`, presence without corroboration, and
    `faction.hab_destruction_recorded` for every `HabDestructionLog` entry
    added (record-dated; it names a hab type and a space body, never a hab ID.
    It carries the log's faction as `owner`, and a `hab` ref only when exactly
    one entry and one vanished hab share owner, type and body; the event
    stays separate from `hab.disappeared`).
-   `analyzers/space/combat.py` (`CombatAnalyzer`): `faction.combat_recorded`
    for every `CombatLogs` entry added, citing the entry, naming the owning
    faction, the side factions, the winner and the hab faction, with the sides
    as hull-class counts per faction and the attack count as attributes. `Date`
    is `null` in the entries seen so far, so the event is interval-dated (a
    componentized date would date it by the record). `faction.combat_entry_removed`
    is interval-dated and literal. One combat logged by two factions gives two
    events; matching them is reconstruction. An unresolved side, winner or hab
    faction gives low confidence. Lines name factions and ship counts, never
    design names (player content) or hull classes (`Battleship` would read as a
    claim).
-   `analyzers/technology/research.py` (`TechnologyAnalyzer`; identity is the
    template-name key): `technology.completed` when a technology's `finished`
    goes from false to true or it appears already finished, corroborated by the
    research singleton's `finished_techs_names` member; `technology.finished_changed`
    for any other literal transition; `technology.appeared` /
    `technology.disappeared` for progress-only or vanished states; the leftover
    `research.finished_techs_changed` for a name no technology event claimed.
-   `analyzers/technology/projects.py` (`ProjectAnalyzer`; identity is the
    project name): `faction.project_completed` per name added to a faction's
    `finishedProjectNames` (a repeatable project is listed once per completion,
    so a name added more than once is one event with `completions`), and
    `faction.finished_project_names_changed` for a removed name or a list that
    changed shape.
-   `analyzers/campaign/global_values.py` (`GlobalValuesAnalyzer`, `global values`
    domain): `campaign.global_milestone_recorded` per milestone label added
    (citing the record entry, naming the faction), `campaign.global_milestone_changed`
    for a label recorded for another faction, `campaign.nuclear_strikes_changed`
    (no threshold), `campaign.sea_level_rise_triggered` when a rise flag goes
    from false to true, `campaign.narrative_event_triggered` per name added to
    the once-per-campaign list and per once-per-target label that gained
    targets, and `campaign.global_value_changed` for every other changed field or
    record, and for any removed record entry, literally. `interstateWars` is
    owned by the war analyzer: `war.appeared` / `war.disappeared` cite the war's
    entry as corroboration, and an entry no war presence explains is the
    leftover `campaign.interstate_wars_changed`. A milestone is "recorded", never
    "achieved", and a removed entry is never assumed pruned.
-   `analyzers/campaign/notifications.py` (`NotificationAnalyzer`, `notification queue`
    domain): one `notification.<templateName>` event per log entry added. The template
    name is used verbatim, and one that is not an identifier gives `notification.unknown_template`.
    The event is dated by the entry (`DateBasis.RECORD`) and cites the entry. Its entities are the
    queue and the resolved subject, and its attributes are the decoded members. An unresolved subject
    gives low confidence. `notification.entry_removed` and `notification.entry_changed` are
    interval-dated and literal: a removed entry is never assumed pruned. All template types share
    one message (template, date, subject), and the summary text is never rendered. The log is
    player-centric and pruned, so it adds to the snapshot evidence and is not a complete history.
-   `analyzers/aliens/regions.py` (`RegionAlienAnalyzer`, `region alien state`
    domain): every event names the region (the sub-state's `region`
    back-reference) first and the sub-state second, with the literal
    `transition`/`before`/`after`. `region.crashdown_changed` for
    `crashdownPresent` or the `crashdownTime` record (both cited as primary;
    record-dated by the new time, attribute `crashdown_time`),
    `region.landing_changed` (`landingPresent`), `region.alien_facility_changed`
    (`built`) and `region.xenoforming_changed` (`xenoformingLevel`, before and
    after level). No event says a crashdown, landing or xenoforming was
    detected, repelled or cleared; thresholds are reconstruction.

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
`classify` treats as a schema gap); faction `currentProjectProgress`, `Kills` and
`armiesLost` records; region alien sub-state `currentHP`, `deployingArmy`,
`supportingArmyBuildup`, `alienMissionsDetected` and sub-state presence.

The atomic facts the narrative layer (section 11.3) needed from the diff are now
emitted by the analyzers above: claims and hostile claims, nation and
federation renames, finished projects, the hull of a ship, an army's home nation, unrest
attempts, the new-government record, faction kinds and population. The allow-listed entries of the
`Transactions` ledger are emitted as `faction.transaction_recorded` by the faction family
(bounds in 11.3); the other labels stay in the diff. The nation-control reading itself (which faction holds
a nation's executive, plurality or every control point) is reconstruction, not analysis: the
`faction.nation_control_changed` rule of section 10 combines control-point events with
`positionInNation` and the executive record, and it is the anchor the takeover and breakaway
developments need.

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

### Implemented contract (`src/tinarrative/reconstruction/`)

`reconstruction.infer_events(events, before, after, diff)` takes one
interval's objective events, with the snapshots and the diff as context (as
for an analyzer), and returns inferred events sorted like `run_analyzers`
output. Inferred events in its input are ignored, so no rule builds on another
inference. An inferred event has status `inferred`, is dated by the interval,
names the IDs of the objective events it rests on in `Event.constituents`, and
cites every source of those events: the region events' sources keep their
roles and every other source is corroborating. A diff change that no analyzer
reports (a region's `isBeingAnnexed`/`annexingArmy`) is cited directly. A fact
read from a snapshot alone, such as a nation holding no regions afterwards or
the sides of a war, only qualifies evidence and is never evidence itself.

The rules live in `reconstruction/territorial.py`, `reconstruction/control.py`
and `reconstruction/space.py`, with their evidence from
[sources for higher-level events](game-data-notes/higher-level-event-sources.md);
`reconstruction/common.py` holds the shared evidence bundle, citation and the
executive-seat lookup.

#### Territorial rules

They are built on `region.nation_changed` events with a known nation on both
sides, and on the tracker reasons that moved in the interval. A reason is cited
through the `nation.statistic_shifted` event that already cites its tracker,
or directly when the statistic stayed below its threshold.

-   `nation.territory_gained` / `nation.territory_lost`: one per nation that
    gained or lost regions (attributes `regions`, `region_count`,
    `counterparts`, `territory_causes`). High when the nation's trackers moved
    under `*Reason_TerritoryChange`, `*Reason_Annexation` or
    `*Reason_RegionTransfer`, medium on the region events alone.
-   `nation.independence`: a gainer with any of the signals `executive_cause`
    (a `lastExecutiveChange` with cause `Independence`), `tracker_cause` (an
    `*Reason_Independence` delta on the gainer or a nation it gained from),
    `breakaway_parent` (a breakaway-parent change), `amicable_release`
    (`DemReason_AmicableRelease` on the gainer) or `nation_released`
    (`*Reason_NationReleased` on a nation it gained from, counted only when
    all of that nation's moved regions went to the gainer: a parent that
    lost regions to several nations does not say which one it released;
    a parent can release one nation and lose a region to another in the
    same interval). High with two
    signals, medium with one. Either release reason sets `released = True`,
    meaning the parent decided the release, and adds `release_causes`,
    `releasing_nation`, `releasing_basis` and `releasing_executive_faction`.
    The releasing nation is the earlier holder of the new nation's capital
    when the capital is among the regions that moved (`capital`), else the
    only nation it gained from (`only_parent`), else `null`. The executive
    faction is whoever controlled that nation's executive seat (its
    `Executive`-typed control point, else the one at `positionInNation` 0)
    in the earlier snapshot. It is context only and never a claim that the
    faction decided. `infer_events` sees one pair of snapshots, so the
    earlier snapshot is the earliest it can consult.
-   `nation.unification`: a gainer that took every region of two or more
    nations is medium. A nation is whole when it disappears (that event is
    cited) or holds no regions afterwards. One whole nation is not enough,
    because a release of a parent's last region or a conquest looks the same.
-   `nation.annexation`: per gainer and loser, medium on an annexation flag
    change of a transferred region (`annexation_flags`), or on a war event or
    `wars` relation event in the interval about a war that has the two nations
    on opposite sides (`war`). An unchanged war is not evidence.

When more than one of independence, unification and annexation fits one
gainer, every candidate is kept one confidence level lower, with
`ambiguous = True` and the other candidates' IDs in `alternatives`. The
territory aggregates rank `minor` and the three readings `major`
(`narrative/significance.py`).

#### Control rule

The control-point analyzer reports each point's controller; only this rule
says that a faction's hold on a nation changed. The executive seat is the
nation's `Executive`-typed point; a nation without one has its position-0
point stand in, and the event names which (`seat`). Only the first kind is
what the nation's executive-change record follows.

-   `faction.nation_control_changed`: one per nation and scope whose holder
    differs between the two snapshots, for a nation with at least one
    `control_point.controller_changed` (the primary constituents). The
    scope (`scope`) is `executive` (the faction holding the executive
    seat), `plurality` (the faction holding most points; a tie or no
    controlled point is `null`) or `sole` (the faction holding every point,
    else `null`); gaining or losing every point is a `sole` change. Attributes
    `before`, `after`, `shares_before` / `shares_after` (points per faction
    ID), `point_count_before` / `point_count_after`, `population` (the
    nation's regions after the interval, context) and `cause`, `recorded_on`
    and `new_executive` from a `nation.executive_change_recorded` of the
    nation in the interval. That record, `control_point.loss_recorded` and
    control-point presence events of the nation corroborate. High, and dated
    by the record, when the record's new executive holds the seat afterwards
    and is the scope's new holder, and the seat is the `Executive` point;
    medium otherwise; low when any point of
    the nation is unresolved on either side (the dependent holder is then
    `Unknown`, and a scope unknown on both sides is not reported). A point
    whose `nation` changed in the interval is territory, not control: it
    is left out of the comparison (`points_moved` counts them), the
    `executive` scope is compared only when the same point is the seat on
    both sides, and every confidence is one level lower. The line says control changed and never names a
    coup or purge; the cause stays an attribute, and the reading belongs to
    the `faction.takeover` narrative rule (section 11.3). Significance
    `major`, a tie included.

#### Space rules

The space analyzers keep their wording rule (a hab disappears, a log entry
is recorded); only these rules name a destruction, a first presence or a
battle outcome. A hab's `barycenter` is the body it sits on or orbits.

-   `faction.first_hab_on_body`: one per faction and body where
    `hab.appeared` events put habs of a faction that held none there in the
    earlier snapshot; high (attributes `body`, `habs`, `hab_count`,
    `first_of_any_faction`, `milestones`). A new `globalMilestones` label
    starting with `First` and containing `Base`, recorded for the faction,
    is cited only when no faction had a hab on the body before and it is the
    faction's only such body in the interval: the labels name places, not
    body IDs. `TIHabSiteState` is not normalized, so its `hab`/`pendingHab`
    transitions are not used.
-   `hab.destroyed`: a `hab.disappeared` joined to the
    `faction.hab_destruction_recorded` entries of the same faction (the hab's
    in the earlier snapshot, the log's owner), hab type and body. A
    `notification.LogHabDestroyed` naming the hab and dated like one entry
    pins that pair. One entry for one vanished hab, or a pinned pair, is high
    and dated by the entry (`destroyer`, `recorded_on`). Otherwise every
    vanished hab of the group is `ambiguous`, interval-dated and cites every
    remaining entry (`destroyers`, `recorded_dates`, `candidates`,
    `vanished`): medium when the entries cover every vanished hab, low when
    fewer entries than habs remain. A hab no entry records stays
    `hab.disappeared`.
-   `faction.battle_outcome`: per killer and victim, growth of the killer's
    `Kills` list against the victim (cited directly; only the count is kept,
    never the names) together with a loss of the victim in the interval: a
    vanished hab or fleet (`habs_lost`, `fleets_lost`) or a destruction entry
    naming the killer (`destruction_entries`). Medium; high with a
    `faction.combat_recorded` entry the killer won, or with a
    `notification.LogSpaceBattleTakesPlace` about a fleet of either side
    unless a combat entry has the victim winning. `combats_won`,
    `combats_lost` and `battle_dates` (the notifications' dates) carry the
    corroboration; the event is interval-dated because combat-log entries
    have no date. Kills keyed by the killer itself are not a battle.

The three space readings rank `major`.

`tinarrative save diff` runs no analyzers and no reconstruction: its report lists literal state changes only.
Inferred events are reported by `tinarrative events --inferred`.

------------------------------------------------------------------------

# 11. Narrative Aggregation

Narrative aggregation operates on the atomic event stream of a save
sequence. Its job is to state, once each, the human-scale developments a
campaign history reports: a faction taking over a nation and consolidating
its hold, a war from declaration to peace, a federation's life, a nation
absorbing its neighbours over several years, a space campaign that
destroyed a rival's bases. Each development carries its span, its actors
by role and every piece of evidence beneath it.

The framework is implemented (11.2, implemented contract), and so are the
geopolitical and space rules of the catalogue (11.3, implemented contracts).
This section is the contract they are built against; the
roadmap's *Narrative layer* section lists the steps. The design was revised
after measuring the atomic stream on real saves: the earlier
sketch (clusters by temporal proximity and shared entities, a `float`
significance, a `title_hint`) is withdrawn in favour of a small set of
explicit, named rules.

## 11.1 Inputs and scope

-   The qualified chronological event stream of one sequence (section 15,
    Mode B): objective and inferred events of every interval, with
    interval-qualified IDs.
-   One *situation report* per save (11.4), which replaces the snapshots:
    aggregation never holds a snapshot, so the two-snapshot memory bound of
    `run_sequence` stands.
-   It is the first stage allowed to see more than one interval. Every rule
    declares its window: one interval, a number of consecutive intervals,
    or the whole sequence. Windows are measured in game days, never in
    saves, because save spacing is arbitrary.
-   Grouping is conservative: a rule emits only when its *anchor* evidence
    exists (an executive change record, a war present in one save and
    absent in a later one, a federation member change), never from temporal
    proximity or shared entities alone. Proximity and shared entities decide
    which further events a rule attaches to an anchor, not whether a
    development exists.

## 11.2 The narrative event

A narrative event is an `Event` (section 5.1) with additional fields, not a
parallel type, so it keeps `status`, `confidence`, `significance`,
`sources`, `constituents`, `attributes` and goes through
`narrative.chronology.qualify` like every other event.

``` python
@dataclass
class Event:  # narrative extension, conceptual
    ...  # the atomic fields of section 5.1
    start: GameDate  # earliest constituent not_before
    start_basis: DateBasis
    end: GameDate  # latest constituent date
    end_basis: DateBasis
    open: bool  # still running at the last save
    intervals: tuple[str, ...]  # interval keys it spans
    # roles: actor, target, beneficiary, loser, assisting, location, body
    roles: dict[Role, list[EntityRef]]
```

-   **Constituents** name atomic and inferred events (qualified IDs);
    `sources` is the union of their sources with roles kept, as in
    reconstruction. The evidence beneath a development is never dropped.
-   **Status** is objective when every constituent is objective and the
    join is by a stable entity ID (a war, a federation, a nation across its
    own events); inferred when the join is heuristic (a shared nation plus
    a time window) or any constituent is inferred.
-   **Confidence** is the minimum over the constituents, lowered one level
    for a heuristic join; a rule that claims more states why.
-   **Significance** is assigned by the rule (section 12), defaulting to
    the maximum over the constituents. Under the entity-scaled score
    (section 12) the rule's own level is scaled by the stake it moved, and
    that maximum stays the floor.
-   **Dating**: `start` is the earliest constituent `not_before`, `end` the
    latest constituent date, each with the basis of the event it came from;
    a record-dated constituent narrows the span. Corroborating-only events
    (ledger charges) are cited but only narrow a start; they never set the
    end. An event whose anchor is
    still present in the last save is `open`, so incremental mode (Mode D)
    can extend it instead of emitting a second one.
-   **Roles** replace the earlier `title_hint`: the LLM or renderer needs
    to know who acted, on whom, who benefited and who assisted, not a
    suggested title. Attributes stay literal structured facts (counts,
    name lists, durations, the metric shifts of the span). No prose.
-   **Nesting**: one level, with an explicit rule order. A war arc may
    contain an absorption that happened during the war; a rule never builds
    on a rule of the same order, and there are no cycles.

### Implemented contract (`src/tinarrative/narrative/aggregation.py`)

`Event` carries the narrative fields as optional fields: `start`,
`start_basis`, `end`, `end_basis`, `open`, `intervals` and `roles`. An event
is narrative when `intervals` is not empty, and `to_dict` emits the fields
only then, so atomic and inferred events serialize as before. A rule is a
`NarrativeRule` (`name`, `order`, `window_days`, `apply(stream, situations,
build)`). `aggregate(stream, situations, rules)` runs the rules by order,
then name, and returns the narrative events sorted. `NarrativeBuilder.event`
applies the policy above to the constituents a rule joins, with the join
declared as `Join.ENTITY` or `Join.HEURISTIC`. `open` means the rule's
anchor entity is listed in the last situation report. `days_between`
measures windows in game days, and `interval_reports` gives a rule the
reports before and after each interval. A rule may state `open` itself
(`NarrativeBuilder.event(open=...)`) when its window, not the anchor's
presence, decides whether a later save can extend it. `NARRATIVE_RULES`
(`narrative/catalogue.py`) is the catalogue under the default settings, and
`narrative_rules(settings)` builds it under runtime settings
([configuration](configuration.md)). `sequence.narrative_events` runs
aggregation over a sequence, and `events --narrative` reports it
([command](commands/events.md#narrative-events)).

Deviations from the sketch above:

-   `roles` is a tuple of `(Role, EntityRef)` pairs sorted by role, then
    entity, not a dict, so the event stays hashable. `entities` lists the
    role entities in that order.
-   A narrative event's ID is `<type>/<parts>@<first interval key>`. It is
    born qualified, so `chronology.qualify` returns it unchanged, and an
    open event keeps its ID when later intervals extend it.
-   `date` is `end` and `not_before` the earliest constituent `not_before`,
    but a narrative event is ordered by `start`, where the development
    begins.
-   Significance is the rule's level raised to the most significant
    constituent's, so a development is never ranked below that constituent
    (section 12). `assign_significance` does not rank narrative events: it
    works one interval at a time, with that interval's snapshots as context.
-   Nesting by order is enforced. A rule of order k sees the stream plus the
    narrative events of lower orders. Citing a narrative event of its own
    order, or an ID it cannot see, raises `ValueError`, as do a duplicate ID
    and a reused rule name.
-   A start tie on date prefers the record basis, and so does an end tie.
-   Corroborating events are passed apart from the constituents. They are
    cited and count for status, confidence and significance, but only the
    constituents date an end.

## 11.3 First catalogue

The types below are the target for the first implementation, chosen
against the format the project aims for (period-dated developments naming
factions and nations) and against the evidence the normalized model already
holds. Each names its anchor and constituents; "needs" lists the atomic
facts no analyzer emits yet (roadmap items). Geopolitics first:

| Type | Says | Anchor and constituents | Window | Needs |
| --- | --- | --- | --- | --- |
| `faction.takeover` (implemented) | faction X took control of nation N (coup, regime change or politics) and consolidated it | `faction.nation_control_changed` (executive, plurality or sole controller), the `lastExecutiveChange` cause, later `control_point.controller_changed` of the same nation and faction, councilor changes of the losing faction; precursors from `factionUnrestAttempts` and unrest or opinion shifts | 1 to 3 intervals | nothing |
| `war.arc` (implemented) | war between A and B and their allies from start to peace, with regions transferred | `war.appeared` (record-dated), `war.alliance_changed`, `nation.annexation`, `war.last_fighting_changed`, `war.disappeared` | sequence | nothing |
| `federation.lifecycle` (implemented) | federation formed, joined, left, renamed, dissolved | `federation.appeared`, `federation.members_changed`, `federation.renamed`, `federation.disappeared` | sequence | nothing |
| `nation.expansion` (implemented) | N absorbed M1..Mk over a period, peacefully or by war | consecutive `nation.unification` / `nation.annexation` / `nation.territory_gained` with one gainer, `nation.disappeared` of the losers, a rename | N intervals | nothing |
| `nation.release` / `nation.breakaway` (implemented) | parent released N / N broke away under faction X | `nation.independence` (`released`), `nation.appeared`, the new nation's control event, `nation.breakaway_parent_changed` | 1 to 2 intervals | nothing |
| `nation.cession` (implemented) | N transferred regions to M without war | `nation.territory_gained` / `lost` with no annexation, unification or independence reading and no war pair; allies or one federation as context | 1 interval | nothing; medium confidence at best, since a conquest without a war looks the same |
| `nation.claims_declared` (implemented) | N claims regions of M | `nation.claims_changed` | 1 interval | nothing |
| `nation.transformation` (implemented) | N's democracy, per-capita GDP, inequality, cohesion or unrest moved sharply together, with causes | two or more `nation.statistic_shifted` of one nation in a window and their `causes`; attached to the takeover, expansion, cession or release of the same nation when one exists | 1 to 2 intervals | nothing |

Every geopolitical type carries `metric_shifts`: the nation statistic
shifts of its nations inside its span, so a takeover or merger states what
it did to democracy, GDP and inequality without a separate event. Band
labels ("totalitarian", "democratic") are not assigned; the literal values
and relative changes are.

### Implemented contract (`src/tinarrative/narrative/geopolitics.py`)

The geopolitical rules read their thresholds and windows from
`config.GeopoliticsSettings` ([configuration](configuration.md)); the
evidence for the defaults is in
[sources for higher-level events](game-data-notes/higher-level-event-sources.md)
(*Narrative rules (geopolitics)*). A window is measured from the earliest
date an event can have had: its record date, else its `not_before`. So
consecutive intervals always touch, and a long interval never splits one
development. *Anchored* windows count from the first member (takeover,
release, transformation), *chained* windows from the latest (expansion).

-   `faction.takeover` (order 0, heuristic). Anchor: an executive or sole
    control change to a faction. Anchors of one nation and faction within
    the consolidation window are one takeover until the faction loses the
    seat; a change caused by `Independence` is left to the release rule.
    Attached: the faction's control-point gains in the nation, the
    nation's executive records, councilor changes naming the losing faction
    in the anchor intervals, the faction's unrest attempts and the nation's
    unrest and opinion shifts in the precursor window, and `Coup`, `Purge`
    or `Crackdown` charges of the faction from the ledger window before an
    anchor to its date when no other faction carries the label then. The
    earliest executive record gives `executive_recorded_on` and
    `previous_executive`.
    Roles actor, target, loser. Open while the last report has the faction
    holding the executive but not every point. Major; campaign-defining
    when the nation ranks within `top_gdp_nations` by `GDP` in the report
    after the anchor's interval.
-   `federation.lifecycle` (order 0, by ID, major). Members at the first
    and last report and the member changes; open by presence.
-   `nation.cession` (order 0, heuristic, so medium at most, major). A
    gained/lost pair with no reading of the gainer in the interval and no
    war with the two on opposite sides in a report around it. Allies and a
    shared federation from the earlier report are context.
-   `nation.release` / `nation.breakaway` (order 0, by the new nation's
    ID). The new nation's appearance, breakaway parent and control events
    within the release window; `executive_faction` is context only.
-   `nation.claims_declared` (order 0, by ID). Additions to a claim list on
    regions other nations hold (`added_owners` of `nation.claims_changed`).
-   `nation.expansion` (order 1, heuristic, major). Two or more gains of
    one nation, chained within the gap. A gain is a unification, an
    annexation, a cession to it (nested) or a territory aggregate in an
    interval without a reading and outside any cession. `mode` is
    `unification`, `annexation`, `mixed` or `null`.
-   `war.arc` (order 2, by war ID, major). Anchor: `war.appeared` or
    presence in the first report. Attached: the war's alliance,
    last-fighting and disappearance events, annexations between its
    belligerents, and the expansions they belong to (nested, in place of
    their annexations). `nuclear_strikes` is the campaign-wide counter's
    change over the war's intervals, not an attribution. A record-dated
    `started_on` sets `start` (basis `record`), even when it predates every
    constituent and the first save. Constituents whose intervals all close before `started_on`
    are left out. `duration_days` is given only when the
    disappearance is record-dated; an interval-dated end gives
    `duration_days_at_most`, an upper bound, and an open war neither.
-   `nation.transformation` (order 2, by ID). Two or more distinct
    statistics among democracy, GDP, inequality, cohesion and unrest of one
    nation within the window. It is skipped when a takeover, expansion,
    cession, release or breakaway naming the nation spans one of its
    intervals. Its level comes from the shifts (minor).

`metric_shifts` is a tuple of entries, one per nation, statistic and key,
over the rule's nations and the intervals it spans. Each entry holds the
earliest shift's `before`, the latest shift's `after`, the unsigned
`relative_change`, the summed `causes` and the shift `events` by ID. The
shifts are context, not constituents, so they never widen a span or change
status, confidence or significance. Statistics that other events already
tell (`numControlPoints`) are left out. A development keeps a bounded number
of entries (`narrative.geopolitics.metric_shifts_max`): its role nations'
first, then nuclear weapons, then the largest relative change. It counts the
rest as `metric_shifts_omitted`. The narrator package drops the `events`
lists, since it does not carry the shift events.

Space milestones second:

| Type | Says | Anchor and constituents | Window | Needs |
| --- | --- | --- | --- | --- |
| `faction.space_campaign` (implemented) | X destroyed k habs and fleets of Y over a period, winning n recorded battles | `faction.battle_outcome`, `hab.destroyed`, `faction.combat_recorded`, `notification.LogSpaceBattleTakesPlace` | N intervals | nothing |
| `faction.colonisation_wave` (implemented) | X established habs on bodies B1..Bn in a period | `faction.first_hab_on_body`, `hab.appeared` | N intervals | nothing |
| `campaign.first_milestone` (implemented) | a campaign-wide first (first base on a body, first warship, first victory against the aliens), dated | `campaign.global_milestone_recorded`; a `Global Milestone` ledger entry of the same faction may date it | 1 interval | nothing |
| `faction.fleet_buildup` (implemented) | X commissioned n ships of class C | `ship.appeared` with a hull class; `Ship Construction` ledger entries as corroboration | 1 interval | nothing |
| `technology.milestone` (implemented) | a technology or project from a curated list completed | `technology.completed`, `faction.project_completed` | 1 interval | the curated list, documented as interpretation |

Implemented contract (`narrative/space.py`, all order 0, windows from
`SpaceSettings`):

-   `faction.space_campaign` (heuristic, major, by killer and victim). Battle
    outcomes of one pair chained within the campaign gap. Attached within
    their intervals: the pair's unambiguous `hab.destroyed`, combats between
    the two, battle notifications about a fleet the victim lost or naming
    either faction, the victim's `fleet.disappeared`, and the
    `faction.hab_destruction_recorded` entries behind the outcomes. Counts
    are summed from the outcomes, never recounted. Roles: actor, target,
    bodies; the bodies are those of every hab loss the campaign counts (a
    joined `hab.destroyed` or an outcome's destruction entry). The two
    campaigns of a pair (A against B, B against A) both keep the combats
    between the two, each counted from its own actor's side, and name each
    other in `mirror` when they share a combat.
-   `faction.colonisation_wave` (major, by faction). Two or more distinct
    bodies among one faction's `faction.first_hab_on_body` within the window,
    with their `hab.appeared`.
-   `campaign.first_milestone` (campaign defining, one interval). A
    `Global Milestone` charge of the milestone's faction dates it only when
    no other faction carries the label in the interval (bound 4 below).
-   `faction.fleet_buildup` (minor, one interval). The minimum number of
    `ship.appeared` of one fleet owner and hull in an interval.
-   `technology.milestone` (at the entry's tier, one interval). A completion
    whose template name is in the curated list (`narrative/milestones.py`),
    each name with a tier (`minor`, `major` or `campaign_defining`) and its
    rationale. The tiers weigh how much of the tree a completion opens, what
    the concept means outside the game and how concrete it is; the same tier
    ranks the atomic completion (section 12). The list is interpretation.

Set aside for now: `economy.space_self_sufficient` (space income against
Earth funding from the resource ledger), because the ledger's income
labels are not understood; alien activity on Earth and councilor fates stay
atomic until the geopolitical types exist.

**Dated mission records as evidence.** Every faction, AI factions included,
carries a `Transactions` ledger (section 4.3) whose labels include mission
and operation names (`Coup`, `Purge`, `Crackdown`, `HostileTakeover`,
`Ship Construction`, `FoundColonyOperation`, ...). It can attribute an
action to a faction and narrow its date where a visible effect already
exists. It is not the councilor's current mission field, which cycles
faster than saves and is never used. Its limits set the bounds: an entry
names no target; some labels are hashed; each label's list is pruned (never
rewritten), so
the ledger is not a full history and does not reach further back than the
notification log for mission labels; an entry is a cost charged when the
mission is assigned, some days to weeks before it resolves (evidence: the
`Transactions` section of the higher-level event sources). So:
(1) only a documented label allow-list, each label checked against a
visible effect over several intervals; (2) entries are read by date from
the later snapshot inside the window, never from diff presence; (3) the
`faction.transaction_recorded` event is `minor` and cited only as
corroboration of an event whose effect is already evidenced, within a
window from the entry date to about four weeks later, never after the
effect, and as corroboration it may narrow a span's start but never sets
its end; (4) attribution only when exactly one faction's ledger carries the
label in the window and that faction is the visible beneficiary, otherwise
`candidates` and no attribution, as for `hab.destroyed`; (5) record-dating
only in that single-candidate case; (6) confidence never above medium on
ledger evidence alone (a charge names no target, so one charge may
corroborate takeovers in several nations and identifies none of them; the atomic `faction.transaction_recorded` event
records a literal entry and is itself high confidence; the cap binds the
narrative events that cite it); (7) `Unrest` entries are cross-checked
against `factionUnrestAttempts` before either is trusted. The analyzer
(`analyzers/faction/ledger.py`) reads the allow-listed entries of the later
snapshot by date and cites the ledger's `records` change as the source.

## 11.4 Situation reports

A situation report is the deterministic digest of one snapshot that the
narrative layer and the narrator need as context: which faction holds each
nation's executive and what share of its control points, federations with
members, wars with sides, each nation's regime statistics as literal
values, nation count and population; habs per faction per body, fleets and
ships per faction, finished technologies and projects, global milestones,
nuclear and climate counters. It is read from the snapshot alone, is
snapshot-dated evidence rather than an event, and is what lets a
development say "formerly held by faction Y" or "then a member of
federation F". `run_sequence` keeps the reports and discards the
snapshots.

### Implemented contract (`src/tinarrative/narrative/situation.py`)

`build_situation(snapshot)` returns a frozen `SituationReport` with a
`to_dict()`; equal snapshots give equal reports. Every value is literal: a
nation's executive is the faction holding its executive-seat control point,
with the seat's basis named (section 10, control rule), and its points are
counted per faction, but no faction is said to control it, since that is the control rule's inference.
Wars per nation come from the wars' alliances. Technologies are one
campaign-wide research state in the model, so the finished-technology count
is campaign-wide; projects are counted per faction. Habs, fleets and ships
no faction of the snapshot owns are counted, not dropped. A value the
snapshot does not establish is `Unknown`, never zero or empty. `run_sequence`
attaches the reports of both saves to each `IntervalResult`, and
`sequence.situations` lists one per save. `events --format json` shows them
as `saves[].situation` ([schema](commands/events.md#situation-report)).

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

### Implemented contract (`src/tinarrative/narrative/significance.py`)

`Significance` lives in the model beside `Confidence`; every `Event` carries it,
defaulting to `minor`, and `SIGNIFICANCE_ORDER` ranks the levels explicitly.
Analyzers never set it. `assign_significance(events, before, after)` is a
post-pass of the narrative stage that copies each event with its level, so one
module holds every judgement of impact. The level comes from, in order, a
context rule for the event type (recruit-pool councilors whose `faction` is
`null` on their existing side are `trivial`, a `nation.relation_changed` for
`wars` or an executive change by `Coup`, `RegimeChange`, `Independence` or
`Enthrall` is `major`, a tier-3 organization changing hands is `major`,
megafauna presence is `major`, a `nation.statistic_shifted` of
`numNuclearWeapons` or `numControlPoints` is `major` and of any other
statistic `minor`, a technology or project completion takes the tier of the
curated milestone list and is `minor` when unlisted), then a per-type table,
then the default. Each
entry and threshold carries its evidence from
[sources for higher-level events](game-data-notes/higher-level-event-sources.md)
or its rationale, and no threshold is tuned to one campaign. Thresholds that
decide whether an event is emitted at all (the nation statistic shifts) live
with their analyzer, so no analyzer depends on the narrative stage. Routine churn
(councilor movement, ship reassignment, organization presence, log pruning,
leftover lists that mirror an asset's owner field) is `trivial`; the leftover
lists of geopolitical relations stay `minor` so the unexplained residue is never
hidden; campaign-wide milestones, nuclear strikes, sea-level stages and nation
presence are `campaign_defining`. `tinarrative events --min-significance
<level>` is the first consumer.

Narrative events (section 11) carry the same enum. Their level is assigned by
the rule that builds them, defaulting to the highest level among their
constituents (11.3, implemented contract), not by the per-type table. A
development is never ranked below its most significant constituent.

### Entity-scaled score (design)

The levels above rank an event by its type, so a coup in a leading power and
one on a micro-state, a fleet action and a skirmish of two ships, or a war
between nuclear blocs and one between minor states share a level. The design
below adds the weight of the entities involved. It is staged on the roadmap
(*Entity-scaled significance*); until a stage lands, the implemented contract
above holds.

**Score.** Every event carries an integer `score` from 0 to 100 beside its
level, on a logarithmic scale where ten points are ten times the stake:

``` text
score = clamp(base(type) + scale(stake), 0, 100)
scale = clamp(round(10 · log10(share / reference)), scale_min, scale_max)
```

The level is a fixed band over the score: `trivial` 0–24, `minor` 25–49,
`major` 50–74, `campaign_defining` 75–100. `base(type)` is the midpoint of the
band the type's rule or table names today (12, 37, 62, 87), so an event
without a stake, or with a stake at the reference share, keeps its present
level and the rules migrate one at a time. The bands, the clamp and one
reference share per measure are runtime settings; the defaults are proposed
as a 1 % reference and a clamp of −20 to +15 points, calibrated per measure
on the sample campaigns.

**Stake.** A stake is a share of a world total in the same snapshot, never an
absolute magnitude: magnitudes grow by orders of magnitude over a campaign,
shares stay comparable. It measures what the event moved, not only who acted:
the territory transferred, the nation whose government fell, every
belligerent of a war, the forces engaged in a battle. It is read on the
interval's earlier side (what was at stake), on the later side for an entity
that exists only there. Only the types whose impact grows with the stake are
scaled, and they are listed explicitly; movement and churn are never scaled,
so a large fleet changing orbit stays routine.

| Entity | Share |
| --- | --- |
| Nation | power share: the weighted mean of its shares of world GDP, population and strength, where strength is the game's published estimate ([nation statistics](game-data-notes/nation-metrics.md#armies-navies-and-a-strength-estimate)) |
| Region | share of world population |
| Federation, alliance, war side | sum of its members' power shares |
| Faction | Earth share (each nation's power share times the faction's share of that nation's control points, summed) blended with its space share |
| Hab, organization | tier² over the total tier²: one tier-3 outweighs three tier-1 |
| Fleet | ship mass over the human ship mass |
| Battle | contested mass, below |
| Campaign-wide (milestones, climate, nuclear strikes) | none: the scale is 0 |

Because every term is a share, shares add: a war side, a federation or a
faction's holdings are sums. The takeover's top-GDP promotion becomes one case
of the nation stake.

**Space and the alien faction.** Early in a campaign the alien faction holds
nearly every space asset and the human factions a station or two
([space assets](game-data-notes/space-assets.md)). A world total that counts
the aliens would make them half the world from the first save, and a human
total alone would make one station half of space. So:

-   the space totals behind faction and asset shares count the human
    factions only; the alien faction is the backdrop, and its own stake is
    its Earth share. An asset event still measures its asset, alien or
    human, against that total;
-   every space share is taken over `max(total, saturation)`, and the space
    weight in a faction's stake ramps from 0 to its configured value as the
    human total reaches the saturation. Until humans hold a real presence in
    space, factions are ranked by their Earth holdings, and a lone station is
    a small stake.

**Battles.** A battle has two sides. Each side's mass (the combat record's hull
counts times the observed mass of the hull class) is weighted, alien ships by
a factor above 1 because they outclass human ships ton for ton. The contested
mass is `smaller + min(larger, k · smaller)`: mass beyond `k` times the
opponent's adds nothing, so a large fleet swatting a scout is a skirmish, and
the outcome never changes the stake. Its share is taken over the weighted mass
of every faction's ships, with the same saturation floor. Habs assaulted or
destroyed are a second measure; the battle takes the higher score. Losses are
attributes for the narrator, not stake.

**Combination.** Stakes add in share space; the type sets the base:

``` text
development.score = max(base(rule) + scale(Σ shares of the rule's distinct stake entities),
                        max(score of every cited event))
```

Constituent scores are never summed: one fact is often recorded several times
(a region transfer and its mirror lists), and a sum would rank by record
count. The maximum stays the floor, so a development is still never ranked
below its most significant constituent; once atomic events are scaled, a
micro-state's disappearance no longer lifts every development that cites it.
A conflict with nuclear-armed nations on opposite sides adds a configured
bonus in points, for escalation risk that a share does not capture.
Perspective (the player's faction) is not impact and stays with the narrator.

**Provenance.** The score is interpretation. Each event records its
`significance_basis` (base, measure, share, scale and the stake entities) in
the `events` output; the narrator package keeps `score` and drops the basis.

**Consumers.** The level stays the deterministic cut-off: `--min-significance`,
the listing filter, continuity recall and the citation audit read it as
before. The score orders within it: chapter length shares and recall follow
it, and the narrator prompt leads with the highest-scored developments.

------------------------------------------------------------------------

# 13. Narrative Rendering

Rendering should consume the narrator package (13.1) rather than raw save
differences. The Markdown renderer is one consumer of that package; an LLM
narrator (section 20) is another.

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

The deterministic Markdown of `tinarrative events` lists atomic events per
interval and names entities as `Name (domain:key)`; it is a forensic view,
not a history. With `--narrative` it lists the narrative events by the year
they start in, above the intervals. A narrative line in the package
below reads, conceptually:

``` text
2046-03 to 2046-07 · faction.space_campaign · inferred, high · major
  actor: <faction A>; target: <faction B>; bodies: <B1>, <B2>, <B3>
  9 habs and 5 fleets of <faction B> lost; 3 recorded combats won by <faction A>
  constituents: hab.destroyed/... (x9), faction.battle_outcome/..., faction.combat_recorded/... (x3)
```

## 13.1 Narrator input

The product the project hands to an LLM, or to a reader who wants the
facts without prose, is a *narrator package*, built deterministically from
one save sequence:

1.  the narrative events in chronological order, each with its span, roles,
    attributes, confidence, significance and constituent IDs;
2.  the situation reports (11.4), one per save;
3.  an entity glossary: every referenced ID with its name and domain, and
    for a nation the names of its regions, so prose never has to invent a
    name and never meets a bare ID; an entity whose name changes keeps its
    latest name and lists the earlier ones;
4.  the atomic events the listed narrative events are built from, for
    drill-down and audit.

Every line carries event IDs so that generated prose can cite them (section
20). The package has a JSON form (canonical) and a Markdown digest grouped
by period. It is not a separate command: `tinarrative events --narrative`
produces it, `--format json` being the canonical form and the Markdown
report's narrative section, above the per-interval drill-down, the digest.
With `--narrative`, `--min-significance` sets the level of the narrative
events in both forms, and the atomic stream holds only their constituents,
followed transitively, as `--constituents` selects them (`all`, the narrator
`evidence` among them, or `none`). Narrator evidence is an event that states a
fact its narrative event does not carry; the bookkeeping a narrative event sums
up is left out of the package and stays in the audit form
(`narrative/evidence.py`). Without `--narrative`, `--min-significance` filters
the atomic stream. The forensic per-interval view and
the package are therefore one report at different filter settings, and they
cannot drift apart.

The package is for a reader, so it carries IDs and names but no provenance:
the JSON form drops every event's sources and every file path. Provenance
stays with the same run without `--narrative`, which lists the same atomic
and inferred events with their sources; a narrative event's sources are its
constituents'. Citing an ID is therefore enough to audit a sentence.

A package too large for one model request is cut into *chapter packages*
(20.3): the same schema restricted to a run of periods, plus a `chapter`
and a `continuity` member. Cutting selects entries and never rewrites one,
so an ID means the same event in a chapter package and in the full package.

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
│       ├── inspection/        # raw structural report (`tinarrative save inspect`)
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
│       │   ├── common.py
│       │   ├── territorial.py
│       │   ├── space.py
│       │   └── inference.py
│       │
│       ├── narrative/
│       │   ├── aggregation.py
│       │   ├── significance.py
│       │   ├── situation.py       # per-save situation reports (11.4)
│       │   └── chronology.py
│       │
│       ├── rendering/
│       │   ├── markdown.py
│       │   └── templates/
│       │
│       └── narrator/          # `tinarrative narrate` (section 20); reads the package only
│           ├── prompt.md      # the system prompt, shipped as package data
│           ├── request.py     # request block, user message, prompt version
│           ├── chapters.py    # estimate, chapter plan, chapter packages, continuity
│           ├── providers/     # neutral request/completion, anthropic, openai, ollama
│           └── assembly.py    # history.md, footnotes, citation audit, manifest
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

### Implemented contract (`src/tinarrative/sequence.py`, `tinarrative events`)

The saves of a plan are one campaign; the grouping step of Mode C selects
them. `survey` hashes each save, reads its `TITimeState.currentDateTime`
(`parsing.normalization.save_timestamp`) and its campaign profile
(`parsing.continuity.campaign_profile`). `plan_sequence` merges byte-identical
saves into one `SaveRef` that keeps every path, and sorts the distinct saves by
game time, then path. A save without a game time is rejected and never placed
by file name. Each save gets a key: its game time, plus `#n` for the n-th
distinct save with the same time. `run_sequence` normalizes the saves in order
with at most two snapshots held, runs `analyze_interval` (diff, analyzers,
significance, optional reconstruction; the same chain as `diff --format
markdown`) on each consecutive pair, and keys the interval by its later save.

Consecutive intervals share their boundary snapshot, so the per-interval
results concatenate without overlap. Every change is reported once, and a
save-carried log entry once, because logs are diffed as multisets, and a
record-dated event never falls outside its interval. What does not concatenate is
identity: an event ID is a type and a subject, unique within an interval only, so
an ID can recur in another interval for a different real event
(see `game-data-notes/chronology-and-deduplication.md`). `narrative.chronology.qualify`
therefore appends `@<interval key>` to every ID, to every constituent and to
the ID-valued attributes that `reconstruction.ID_ATTRIBUTES` declares, and
`chronological` merges the qualified events into one stream and rejects a
duplicate ID.

Rules still see one interval. Evidence split across a boundary (regions taken
over two intervals, drift below a per-interval statistic threshold) is not
combined. Joining events across intervals is narrative aggregation (section
11). Running the pipeline per interval found more inferred events than one
outer diff of the first and last save (40 against 26 on the same saves),
because an outer diff hides intermediate states.

Narrative aggregation runs after `run_sequence`, over the qualified stream of
the whole sequence. It needs one situation report per save (11.4) rather than
the snapshots, so `run_sequence` builds the report of each save while it holds
the snapshot and keeps only the reports; the two-snapshot memory bound stands.
`sequence.narrative_events` runs `narrative.aggregate` over `event_stream` and
`situations`.

## Mode C --- Campaign directory

Input:

``` text
Documents/My Games/TerraInvicta/saves/
```

The application discovers saves, orders them, processes new snapshots,
and produces/updates campaign history.

Before ordering, discovery must partition files into campaigns. The
serialized format has no observed campaign identifier, so this step uses a
documented continuity profile. Byte-identical saves are aliases of one
snapshot. A conflict or missing continuity evidence must produce separate or
unclassified groups, not an invented chronology. See
[`game-data-notes/campaign-grouping.md`](game-data-notes/campaign-grouping.md).

### Implemented grouping (`src/tinarrative/grouping.py`, `tinarrative campaigns`, `events --campaign`)

`survey` attaches a `CampaignProfile` to every `SaveRef`:

- the faction of the only non-AI `TIPlayerState`, kept only when it resolves to a `TIFactionState`;
- `playerFactionName`;
- the scenario template names;
- `TIGlobalValuesState.realWorldCampaignStart`.

`group_saves` buckets the surveyed saves by the equality of these four signals and compares
nothing else. It runs between `survey` and `plan_sequence`, and `plan_sequence` then runs once on
the chosen group, unchanged. A save without exactly one resolvable human player is unclassified: it
forms its own group and is never merged.

The grouping is inference with provenance (sections 3–5). Every `CampaignGroup` carries the
signals it was formed on, and `events` reports them in its `## Campaign` section and in its JSON
`campaign` member. Each group has a selector key: the faction slug plus the real-world start.
`events` refuses to mix groups. With several groups it requires `--campaign`. Without a matching
selector it prints the listing and exits 2, except in a terminal, where `picker.pick_campaign` asks
for a selector or fuzzy search text on stderr. The picker only chooses among the groups; it never
regroups. File modification time is read only to resolve `--campaign latest`.

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

For the narrator (section 20) the boundary sits between request and
response: the chapter plan and every request are byte-deterministic
functions of the package and the settings, while the prose is not. The run
manifest records both sides, the request hashes and the model that
answered, so a history can be traced to its inputs even when it cannot be
reproduced word for word.

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

# 20. LLM Narration

An LLM may be useful for:

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

The contract between the two halves is the narrator package (13.1): the LLM
receives narrative events, situation reports and the glossary, and returns
prose whose claims cite event IDs. It may order and phrase, but does not
merge narrative events the rules kept apart; it does not get the raw atomic
stream as its primary input, and it never supplies a fact the package does
not contain. Anything the package cannot state (motives, "assisted by" when
no army evidence exists, the public framing of a move) is the LLM's, is
worded as interpretation, cites nothing, and never becomes the premise of a
later factual claim. The prompt is [narrator](narrator.md).

The rest of this section is the design of `tinarrative narrate`, the
command that carries a package to a model and brings prose back. It is
implemented ([narrate](commands/narrate.md)).

## 20.1 Command and data flow

``` text
saves ──(events pipeline)──┐
                           ├─→ narrator package
package JSON (--package) ──┘          ↓
                               chapter plan (20.3)
                                      ↓
                          chapter packages + continuity (20.4)
                                      ↓
                               requests (byte-deterministic)
                                      ↓  --send only
                               provider (20.5)
                                      ↓
                          assembly + citation audit (20.6)
```

`narrate` takes the same save inputs as `events` (`PATH…`, `--campaign`,
`--config`) and builds the package in-process, through the same steps and
the same `build_document` as `events --narrative --format json`, or reads a
finished package with `--package FILE` (or `-` for stdin). The two inputs
give the same package, so the narrator half depends only on the package's
JSON form and on its own settings, never on `parsing`, `sequence` or the
model types. That keeps the contract of 13.1 the only interface between the
deterministic half and the narrator, and lets a package be narrated on
another machine or long after it was built.

Sending is explicit. Without `--send` the command writes the chapter plan
and every request and contacts nothing, which is how a request is reviewed,
diffed or run by hand against any model. With `--send` the requests go to
the configured provider. The package carries no file paths and no
provenance (13.1), but it does carry the campaign, and with `--send` that
campaign reaches a third party unless the provider is local.

## 20.2 Request parameters

The prompt reads a request block at the head of the user message. Its keys
fall into three groups.

-   **Chosen by the user**: `audience` (`public`, `insider`), `citations`
    (`footnotes`, `none`), `style` (`chronicle`, `headlines`) and `length`.
    `length` is a target for the whole history; each chapter's request
    carries its share, in proportion to the significance-weighted count of
    the developments it holds.
-   **Derived by the program, overridable**: `period` follows from the span
    of the campaign by a documented rule (short spans by quarter, medium by
    half, long by year), with thresholds in the settings, and is made
    coarser chapter by chapter where the saves are further apart than the
    period runs, since a period finer than the saves can only be invented;
    an explicit `period` is kept with a warning. `focus` is the
    player faction for an `insider` account and absent for a `public` one.
-   **Set by the program only**: `chapter` (index and count), `part`
    (`whole`, `first`, `middle`, `last`) and `covers` (the chapter's first
    and last save dates).

The block lists its keys in a fixed order and only the keys that are set,
so that two runs with the same inputs send the same bytes.

The significance level applies to the narrative only. `narrate` lists
developments at `major` and above by default and keeps, of the atomic stream,
only the constituents of the developments it lists (`--constituents evidence`): the atomic stream is drill-down for detail and
citation (above), not a second account of the period.

## 20.3 Token budget and chapters

A package grows with the number of saves rather than with the number of
developments: every save brings a situation report and every interval its
atomic stream. A long campaign therefore does not fit one request, and
`narrate` cuts it into *chapters*, each sent as its own request.

**Budget.** `max_input_tokens` is a fixed upper bound on one request's
input: system prompt, request block and chapter package together.
`max_output_tokens` bounds its prose. Both are settings, so a small local
model and a large hosted one use the same planner with different numbers.

**Estimate.** Input size is estimated locally and deterministically from
the serialized request (characters divided by a conservative
characters-per-token ratio from the settings). The planner never asks a
provider to count tokens, so the chapter boundaries depend on the package
and the settings only, never on the model, its tokenizer or the network.
The token counts a provider reports go into the run manifest (20.6), which
is how the ratio is checked against real use.

**Chapters.** A chapter is a contiguous run of whole periods of one kind
(20.2) and starts and ends on a save. The planner walks the periods in order and adds
the next one to the current chapter while the chapter's estimate stays
within the budget. A development belongs to the chapter that holds its
start, the same rule by which the prompt places it under a period.

**Chapter package.** A chapter package has the schema of the narrator
package, restricted to the chapter:

-   `narrative`: the developments that start in the chapter;
-   `saves`: two situation reports, the opening one (the closing save of the
    previous chapter) and the closing one, with `nations` pruned to the
    nations the chapter references and the largest economies;
-   `intervals`: the intervals that overlap the chapter, with the atomic
    stream reduced as in 20.2;
-   `glossary`: the entries still referenced;

plus a `chapter` member (index, count, part, covers) and a `continuity`
member (20.4). Slicing selects entries and never rewrites one: an event in
a chapter package is the event of the full package, ID and all, so a
citation audits the same way in either.

**Over budget.** When a single period does not fit, the planner reduces it
in a fixed order and records which step it took for that chapter:

1.  leave out the atomic stream, keeping developments, situations and
    glossary;
2.  split the period at save boundaries into consecutive chapters; `covers`
    tells the model that the period continues across them;
3.  if a single interval still does not fit, stop before sending anything
    and report the budget the interval would need.

Developments are never dropped to make a chapter fit, and the significance
level is never raised behind the user's back. Either would remove facts
from the history without the reader knowing.

## 20.4 Continuity

Continuity between chapters is built from the package, not from earlier
prose. A chapter package's `continuity` member holds:

-   `continuing`: the full records of developments that started in an
    earlier chapter and still run in this one, marked as already told, so
    the model picks them up briefly rather than introducing them again;
-   `earlier`: a short digest of the earlier chapters' developments at
    `major` and above (ID, type, span, the names in their roles), capped by
    a setting, so the model can refer back without inventing the past.

The opening situation report is the closing report of the previous chapter,
the save the two chapters share. No chapter's prose is ever input to
another: generated text is not a source (above), and an error in one
chapter must not become a premise of the next. Chapters are therefore
independent requests that can be re-run, resumed, cached or sent in
parallel.

The prompt reads the chapter fields as follows: only a `first` or `whole`
part opens the history; only a `last` or `whole` part ends with the closing
situation; for a later chapter, "before the first save" means before the
chapter's opening save, and what came earlier is known only from
`continuity`; `continuity` IDs may be cited like any other.

## 20.5 Providers

The narrator talks to a model through one provider-neutral request (system
prompt, user message, model, output limit, optional temperature) and one
neutral completion (text, a finish reason of `complete`, `length`,
`refused` or `other`, and the token counts when the provider reports them).
Adapters translate between that pair and each wire format:

-   `anthropic`: the Anthropic Messages API;
-   `openai`: the Chat Completions API; with a `base_url` it also serves the
    servers that implement that API (hosted gateways, LM Studio, vLLM);
-   `ollama`: Ollama's native chat API, because only it can set the context
    length per request; a context smaller than the request truncates the
    input silently, so the adapter sets it from the budget and the output
    limit.

The adapters use the standard library's HTTP client behind a small
transport interface, which tests replace with a fake; the project keeps
no runtime dependencies. Requests that fail with a rate limit or a server
error are retried a bounded number of times, honouring the provider's
retry hint. A completion that stops at its length limit, or is refused, is
a failed chapter, never a short one.

The model is always named by the user; the program carries no default model
ID, which would go stale. Provider, model, base URL and limits come from a
`[narrator]` settings table with named profiles (a hosted model, a local
one), chosen with `--profile` and overridden by flags. A profile may state
its model's context window, and a budget plus output limit that exceeds it
is rejected before anything is sent. API keys are read only from an
environment variable whose name the profile gives; they never appear in a
settings file, in the output or in a log. The narrator settings never
change what `events` builds.

## 20.6 Output, audit and reproducibility

A run writes into one output directory:

``` text
narration/
  requests/01.json …    # the neutral request of each chapter, byte-deterministic
  responses/01.json …   # each chapter's text, finish reason, reported model, token counts
  history.md            # the assembled history
  manifest.json         # the run record
```

`history.md` opens with a header naming the provider, the model as
reported, the prompt version (a hash of the prompt text, so it cannot drift
from the prompt), the campaign key, the period covered and the generation
time. The chapters follow in order. Footnotes are numbered per chapter by
the model and renumbered in sequence across the whole history, with their
definitions collected at the end.

The manifest records the program version, the package hash, the settings,
the request parameters, the chapter plan (per chapter its cover, estimate,
over-budget step and request hash), the token counts and the citation
audit. The audit checks every ID a footnote cites against the chapter
package it was written from (development, atomic event, continuity entry or
`situation <save-key>`) and lists citations that match nothing and listed
developments of `major` and above that no footnote cites. It reports; it
does not reject prose, since a wrong citation is a finding for the prompt,
not a reason to throw away a chapter.

A chapter whose stored response was made from an identical request (the
same request file, sent to the same provider and model with the same
limits) is not sent again, so an interrupted or partly failed run resumes
where it stopped, and changing one setting re-sends only the chapters it
changes. Assembly reads only the output directory, so a directory of stored
responses can be assembled again without sending anything.
The run log carries counts, sizes, estimates, chapter indexes, the provider
and HTTP status, and never a request, a response, a key or a string read
from a save.

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
