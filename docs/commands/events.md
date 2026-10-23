# `tinarrative events`

```
tinarrative events <path> <path> [<path>...] [--campaign <selector>] [--format markdown|json] [--min-significance <level>] [--period year|half|quarter] [--inferred] [--narrative] [--constituents all|evidence|none] [--changes] [--config <file>]
```

Reads two or more saves, given as files, directories or both, groups them by campaign, orders one campaign's saves by game time, and reports the analyzer
results of every pair of consecutive saves (architecture section 15, Mode B). Each pair is
diffed as [`save diff`](diff.md) does, and the diff is run through every objective analyzer, the
significance rules and, with `--inferred`, the reconstruction rules. `events` is the only command
that reports analyzers, significance or reconstruction ([`narrate`](narrate.md) runs the same steps to build its
package); given two saves it is the analyzed view of
the pair, and with `--changes` it also lists the literal changes that `save diff` reports.

## Directory input

A directory contributes its files one level deep, in sorted order, as [`unknowns`](unknowns.md)
does; subdirectories are not entered. Files and directories can be mixed in any order. Only paths
named on the command line can fail the run:

- A named file that cannot be read or is not a usable save stops the run (exit 4 or 5).
- A file found inside a named directory that cannot be read, is not a supported save or has no
  parseable game time is skipped. It is listed in the report and never changes the exit code.
- A named directory that holds no files, or whose every file is skipped, is an input error
  (exit 4).

The "at least two saves" check applies after expansion: fewer than two candidate files, or fewer
than two usable saves once the skipped files are set aside, is a usage error (exit 2). A file
found in a directory and a file named on the command line with the same bytes are merged by the
rule below.

## Campaigns

Before ordering, the saves are grouped by campaign exactly as [`campaigns`](campaigns.md) lists them.
Saves belong to one campaign when the human player's faction, the faction name, the scenario and the
real-world campaign start all match. Grouping applies to files named on the command line as well as
to files found in directories.

- With one group, `events` reports it and `--campaign` is not needed.
- With several groups and no `--campaign`, `events` never picks a group silently or mixes groups.
  In a terminal it opens the [campaign picker](#campaign-picker). Otherwise the run stops with a
  usage error (exit 2) and prints
  `the input holds N campaigns; choose one with --campaign` and the `campaigns` listing to stderr.
- `--campaign <selector>` reports one group. The selector is a key or unique key prefix from the
  listing, the listing number, or `latest` (the group holding the most recently modified file;
  [selector keys](campaigns.md#selector-keys)). A selector that matches no group, or matches several,
  prints the reason, then opens the picker with the selector as its first search in a terminal, or
  prints the listing and exits 2 otherwise.

The "at least two saves" check also applies to the chosen campaign. A campaign with a single
distinct save, such as an unclassified save, is a usage error.

### Campaign picker

The picker opens only when both stdin and stderr are terminals. It writes the listing and its prompt
to stderr, so `events saves > report.md` still asks in the terminal and the file holds only the
report. Scripts and pipes keep the exit-2 behavior above. The prompt
`Campaign (number, key or search text; empty to cancel):` takes:

- anything `--campaign` accepts: a listing number, a key or unique key prefix, or `latest`;
- otherwise, fuzzy search text, matched against each group's key, faction name, scenario and
  real-world start (never against paths). Each whitespace-separated term must appear in order,
  not necessarily contiguously (`prot` matches `protectorate`), and case is ignored. A single match
  is chosen. With several, the listing narrows to them, best match first, keeping their listing
  numbers, and the prompt asks again. With none, the full listing is shown again.

An empty answer, end of input or Ctrl-C cancels the picker. The run prints
`no campaign chosen` and exits 2. Once a campaign is chosen, the run continues exactly as with
`--campaign`.

## Ordering and duplicates

The rules follow [chronology and duplicate snapshots](../game-data-notes/chronology-and-deduplication.md):

- Saves are ordered by their serialized game time (`TITimeState.currentDateTime`). File names,
  argument order and modification times are never used, so the saves can be given in any order.
- Byte-identical saves (same SHA-256), such as an `Exitsave.json` beside the manual save it copies,
  are one snapshot. The first path in sort order is its source and the others are listed as
  `identical:` aliases.
- Saves with the same game time but different bytes are all kept and ordered by path.
- A save without a parseable game time cannot be placed, and the run stops with exit code 5.

Each save is read twice: once to hash it and read its game time, and once to normalize it in
order. At most two normalized snapshots are held at a time.

## Intervals and event IDs

An interval is a pair of consecutive saves. Its key is the later save's game time; a second or
later save with the same game time adds `#2`, `#3`, and so on. A save's key does not change when
other saves are added before or after it.

An event ID names a type and a subject, so the same ID can recur in another interval: a region
that changes hands twice, a value that drifts every interval, a notification queue index that
holds a different entry in each save. Every event ID in this report is therefore qualified with
`@<interval key>`, for example `region.nation_changed/region:42@2032-07-01T00:00:00`. The same
suffix is applied to an inferred event's constituents and to its `alternatives`.

Consecutive intervals share their boundary save, so every state change, and every new entry of a
save-carried log, is reported in exactly one interval. Events are never merged across intervals.
Reconstruction rules see one interval at a time. Evidence that is split across a boundary, such
as a nation taking another nation's regions over two intervals, is reported as one
`territory_gained` per interval and never as one `unification`. Combining events across intervals
is left to narrative aggregation.

## Naming entities

The Markdown lines and the "affected entities" list name an entity as `Name (domain:key)`, for
example `Germany (nation:3857)`: the display name the save gives it, with the ID kept for audit.
An entity the save gives no name, or one that is not normalized (an orbit or a hab site), keeps the bare `domain:key`. A name-keyed entity whose name is its key, such as
a technology, is not repeated. This holds for the subject, the context in parentheses and any
reference an event carries as an attribute. The `#### State changes` section stays literal and
prints IDs only, as `save diff` does. Names are save content, so they appear in this report and
never in the diagnostic log.

## Markdown output

The default report lists:

- `## Campaign`: the chosen campaign's key, player faction, scenario and real-world start, and the
  signals it was grouped on. Grouping is inference, so the section names them. It also says how many
  given saves belong to other campaigns.
- `## Saves`: the distinct saves in chronological order, each with its key and source path, its
  identical aliases, and a note when it has the same game time as the previous save. A summary
  line follows with the number of usable saves given, the number of byte-identical copies merged
  and the number of skipped files. When files were skipped, a `Skipped` list follows, one line per
  file with its path, error class and the loader's message; the file's content is never shown.
- `## Intervals`: one `### <earlier date> to <later date>` section per interval, giving:
  - the number of state changes;
  - with `--inferred`, `#### Inferred events` (see below);
  - `#### Objective analyzer results`, grouped by category, each result with its affected entities;
  - with `--changes`, `#### State changes`: every literal change of the interval, grouped by
    domain, one line each in the form of `save diff`'s text report (a `records` change shows entry
    counts only). When the interval has none, the section says `No state changes were recorded.`

With fewer than two distinct saves, the report says that no interval was compared and the
command exits 0.

### Significance

Every analyzer result carries a significance (`trivial`, `minor`, `major` or
`campaign_defining`), assigned by the rules in `narrative/significance.py` (architecture
section 12). `--min-significance <level>` lists only the results at that level or above; the
default `trivial` lists every result. When results are dropped, one line after the interval's
objective results states how many were omitted and below which level, so the report never hides
the omission. State changes listed with `--changes` are never filtered. The JSON report is filtered
the same way (see [JSON output](#json-output)).

With `--narrative`, `--min-significance` filters the narrative events instead, and the objective and
inferred events are no longer filtered by significance: they are listed only as constituents of a
listed narrative event, as `--constituents` says. `all` and `evidence` follow constituents
transitively, whatever their significance: through a lower-order narrative event a listed one cites
(that event is then listed too, even below the level), and through an inferred event to the
objective results it rests on. `all` lists every event reached, so every constituent ID of a listed
narrative event resolves in the report. `evidence` lists the narrator evidence among them, the
events that state a fact their narrative event does not carry; for now that is every constituent,
as with `all`. `none`, the default, lists no objective or inferred event. The omitted lines then
read `N objective analyzer results omitted: not cited by a listed narrative event.`, `N objective
analyzer results omitted: not narrator evidence.` or `N objective analyzer results omitted with
--constituents none.`, one line per reason. `--constituents` is ignored without `--narrative`.

An interval with nothing to list (no listed inferred or objective event, and no `--changes`) is one
line instead of a section: its dates, its state change count and how many events were omitted and
why. This happens above `trivial` and with `--narrative`, so `events --narrative` reads as a digest
with `## Intervals` as its drill-down appendix, filled by `--constituents all` or `evidence`.

### Inferred events

`--inferred` also runs the reconstruction stage (`reconstruction.infer_events`, architecture
sections 5.2 and 10) on each interval's analyzer results and lists what it infers in a separate
`#### Inferred events` section before the objective results, so inferences never mix with the
results they rest on. Today the rules cover territory (`territory_gained` / `territory_lost`,
`independence` with its release reading, `unification` and `annexation`), nation control
(`faction.nation_control_changed` per `executive`, `plurality` and `sole` scope) and space
(`faction.first_hab_on_body`, `hab.destroyed`, `faction.battle_outcome`). Each line gives the event's reading and its `confidence`; an event whose evidence
fits several readings is prefixed `[ambiguous]` and followed by an `alternatives:` line naming the
competing event IDs. Below it, one `from` line per constituent names the objective result's ID and
its description as listed under `#### Objective analyzer results` (the ID alone if that result is
not among the analyzer results):

```
- nation:20 annexed 1 region of nation:21 (confidence: `medium`)
  - from `nation.relation_changed/wars/nation:20/nation:21/added@2032-04-01T00:00:00`: nation:20 and nation:21: wars entry added (listed by both)
  - from `region.nation_changed/region:42@2032-04-01T00:00:00`: region:42 nation: nation:21 -> nation:20
```

Inferred events get a significance by the same rules and `--min-significance` (or, with `--narrative`,
`--constituents`) filters them the same way; the section states its own omitted count (`N inferred events below <level>
significance omitted.`), separate from the objective one. When nothing was inferred the section
says `No events were inferred.`

## Narrative events

`--narrative` joins the events of the whole sequence into narrative events: developments that
span intervals, such as a takeover and its consolidation or a war from start to peace
([architecture 11](../architecture.md#11-narrative-aggregation)). It implies `--inferred`,
because rules build on inferred events. The geopolitical rules of
[architecture 11.3](../architecture.md#113-first-catalogue) are implemented: `faction.takeover`,
`war.arc`, `federation.lifecycle`, `nation.expansion`, `nation.cession`, `nation.release` /
`nation.breakaway`, `nation.claims_declared` and `nation.transformation`. Each carries the nation
statistic shifts of its span as the `metric_shifts` attribute, naming the shift events by ID.
A `metric_shifts` entry has `nation`, `statistic`, `key` (public opinion only), `before` (the earliest
shift's value), `after` (the latest's), the unsigned `relative_change`, `not_before` (the earlier save of the
earliest shift), `date` and `date_basis` (the later save of the latest shift: the net change happened between
`not_before` and `date`), the summed per-reason `causes` when the shifts carry them, and the shift `events` by ID.
`federation.lifecycle` counts a member's shifts only in the intervals in which it was a member at either end, so
the interval of a join or leave counts and earlier or later ones do not.
The space rules are implemented too: `faction.space_campaign`, `faction.colonisation_wave`,
`campaign.first_milestone`, `faction.fleet_buildup` and `technology.milestone` (the last from a curated
list of template names, which is interpretation; each name carries the significance tier of both the
milestone and the atomic `technology.completed` or `faction.project_completed`, and an unlisted completion
is minor).

Their thresholds and windows come from a settings file: `--config <file>`, else the file named by
`TINARRATIVE_CONFIG`, else the built-in defaults ([configuration](../configuration.md)). An empty
variable counts as unset. The file is read and validated on every run, with or without
`--narrative`.

The Markdown report gains `## Narrative` between `## Saves` and `## Intervals`. Events are grouped
under period headings, using the period each event starts in, with `### Undated` first.
`--period year` (the default) gives `### 2032`, `half` gives `### 2032 H1` and `quarter` gives
`### 2032 Q1`. Each
line gives the event's span, `(open)` when its anchor is still present in the last save, its
description, status, confidence and significance. A `roles:` line follows, then an `attributes:`
line with the event's key attributes (the number of `metric_shifts`, and, when present, the war,
shared federation, cause, mode, region count, duration, milestone, hull, count or template), then
one `from` line per constituent ID:

```
- `2032-01-01T00:00:00` to `2032-07-01T00:00:00` (open): <description> (inferred, confidence `medium`, significance `major`)
  - roles: actor: Fixture Faction (faction:7); target: Fixture Nation (nation:20)
  - attributes: metric_shifts: 2; region_count: `1`
  - from `faction.nation_control_changed/executive/nation:20@2032-04-01T00:00:00`
```

When the settings differ from the defaults, the section opens with
``Built with non-default settings: `narrative.geopolitics.top_gdp_nations = 3`.``, listing every
changed key. `--min-significance` filters the section and states how many events it omitted
(`N narrative events below <level> significance omitted.`); a lower-order event cited by a listed one
is kept below the level with `--constituents all` or `evidence`. When nothing was built the section says
`No narrative events were built.`

A narrative event's ID is qualified by its first interval. Its constituents keep their own
intervals' keys.

## JSON output

`--format json` prints one object:

- `campaign`: the chosen campaign, in the form `campaigns --format json` lists it;
- `inputs` (the chosen campaign's saves given, after directory expansion), `duplicates`;
- `skipped`: one object per file skipped inside a named directory, with `source`, `error_class` and
  `error` (empty when none);
- `saves`: one object per distinct save, with `key`, `source`, `aliases`, `sha256`, `date` and
  `situation` (its [situation report](#situation-report), or `null` when fewer than two distinct
  saves were given, because then no save is normalized);
- `intervals`: one object per interval, with `index`, `key`, `before` and `after` (source paths),
  `not_before` and `date` (their game times), `changes` (state change count), `events` (the
  objective events, serialized as `Event.to_dict`), `inferred` (the same for inferred events, or
  `null` without `--inferred`) and `state_changes` (the literal changes, each serialized exactly as
  a change in `diff --format json`, with values, detail and source locations, or `null` without
  `--changes`);
- `narrative`: the narrative events in order, or `null` without `--narrative`. Each is serialized
  as an event, plus `start` and `end` (game dates), `start_basis` and `end_basis` (`interval` or
  `record`), `open`, `intervals` (the keys of the intervals it spans) and `roles` (`{"role",
  "entity"}` pairs, the role being one of `actor`, `target`, `beneficiary`, `loser`, `assisting`,
  `location` or `body`). Atomic and inferred events never carry these fields;
- `settings`: the effective settings the narrative was built with, every key included, as nested
  tables (`{"narrative": {"geopolitics": {...}}}`), or `null` without `--narrative`;
- `min_significance`: the level the narrative events were filtered at, or without `--narrative` the
  objective and inferred events;
- `constituents`: which of the listed narrative events' constituents the objective and inferred
  events are (`all`, `evidence` or `none`), or `null` without `--narrative`;
- `narrative_omitted`: how many narrative events were not listed, or `null` without
  `--narrative`; each interval also has `omitted` (`{"objective": n, "inferred": n}`, `inferred`
  being `null` without `--inferred`);
- `glossary`: with `--narrative`, one entry per entity ID referenced anywhere in the document
  (`saves`, `intervals`, `narrative`), sorted by ID, or `null` without it. An entry has `ref`,
  `domain` and, where the save gives them, `name` and `kind` (the save's state type). When an entity's display name changes between saves (a control
  point's name includes its slot), `name` is the one the latest save or interval carries and
  `former_names` lists the others, oldest first. A nation entry
  also has `regions`, its regions' `ref` and `name`; those regions are entries themselves.

With `--narrative`, the document is the [narrator package](#narrator-package), which leaves out
provenance and paths. Outside it, every reference in `entities`, in `attributes` and in a source's `member` is an object with `ref`
(`domain:key`), `state_type`, `confidence` and, when the save gives the entity a display name,
`name`.

The JSON report drops what the Markdown does not list (see [Significance](#significance)): without
`--narrative`, objective and inferred events below `--min-significance`; with it, narrative events
below `--min-significance` and every objective and inferred event that is not a listed narrative
event's constituent that `--constituents` keeps. It counts them (`omitted`, `narrative_omitted`),
so an omission is never hidden; without `--narrative` the default `trivial` omits nothing.
`state_changes` and the situation reports are never filtered. `--period` only groups the Markdown.

### Narrator package

`events --format json --narrative` is the narrator package of architecture section 13.1: the
`narrative` events with roles, attributes and constituent IDs; one `situation` report per save in
`saves`; the `glossary`, so no name has to be invented; and, with `--constituents all` or
`evidence`, the atomic events of `intervals` that the listed narrative events are built from, for
drill-down and citation by ID (with the default `none`, `intervals` lists none). Package consumers read those members and ignore
the rest. It is meant to be handed to a reader, such as an LLM narrator
([narrator](../narrator.md)), so it carries IDs but no provenance and no file paths:

- no event, narrative or atomic, has `sources`;
- `campaign` has no `sources`, a `skipped` entry keeps only its `error_class`, a save has no
  `source` or `aliases`, and an interval has no `before` or `after`;
- a reference is `ref` and `name` (and `confidence` when the identity is not an in-save ID); its
  state type is the glossary entry's `kind`;
- a situation report leaves out the nations that hold no region in any save of the run and that no
  listed event references; `world` still counts every nation;
- a situation report's nations have no `seat_basis`, no `unresolved_points` when that is `0`, and
  `allies` as bare ref strings (`"nation:4"`), each a glossary entry; a faction's `habs_by_body`
  lists only the bodies with two or more habs, and `other_bodies` counts the bodies with one
  (`habs` still counts every hab);
- every float is rounded to 4 significant digits;
- `--changes` is a usage error (exit 2), since literal changes carry their source locations.

The audit form is the same run with `--inferred` instead of `--narrative` and no
`--min-significance`: the same saves and keys, and every atomic and inferred event, so every
atomic ID in the package and every constituent ID resolves there, each event with its `sources` and
the save paths. A narrative event is audited through its constituents there, whose sources include
all of its own.

`--changes` keeps every interval's changes, with their before and after values, in memory until
the report is written, so a long sequence uses more memory with it than without it.

### Situation report

A save's `situation` is the digest of that one save that narrative aggregation and the narrator
read as context ([architecture 11.4](../architecture.md#114-situation-reports)). It is read from
the save alone, states literal values and counts, and is not an event. A reference is an object
as above. A value the save does not establish is `{"unknown": <reason>}` (with `raw` when
something was serialized), never `0`, `[]` or `null`. `null` is a known null.

- `date`: the save's game time.
- `player_faction_name`: `playerFactionName` from the campaign metadata.
- `nations`: one object per nation, in ID order:
  - `nation`: the nation;
  - `executive`: the faction holding the nation's executive seat: its control point typed
    `Executive`, else the point at `positionInNation` 0. It is `null` when the seat is uncontrolled
    or the nation has no control points, and unknown when the point list is unknown, no point is
    typed `Executive` or sits at position 0, or the seat's controller is unresolved;
  - `seat_basis`: `executive_point` or `position_0` (the nation has no `Executive` point), `null`
    when no seat is found. `lastExecutiveChange` follows the `Executive` point only, so on
    `position_0` it can be a stale record;
  - `control_points`: the number of points; `shares`: points held per faction, keyed by faction ID
    (`faction:12`), without uncontrolled or unresolved points; `unresolved_points`: points whose
    controller is unresolved. All four are unknown when the point list is. The report never says
    which faction controls a nation; that is an inference (`faction.nation_control_changed`);
  - `federation`: the nation's federation, or `null`; `allies`: its `allies` list;
  - `wars`: `{"war", "side"}` for every war whose attacking or defending alliance lists the
    nation, `side` being `attacker` or `defender`, in war ID order;
  - `regions`: the number of regions; `population`: the summed `populationInMillions` of those
    regions (unknown when any region's value is);
  - `statistics`: `democracy`, `cohesion`, `unrest`, `inequality`, `GDP` and `spaceFunding_year`,
    as serialized.
- `federations`: `federation`, `name` (`federationName`) and `members`, in ID order.
- `wars`: `war`, `attacker`, `defender`, `attacking_alliance`, `defending_alliance`,
  `start_date` (`startDate`) and `last_fighting` (`dateOfLastFighting`), in ID order.
- `factions`: one object per faction, in ID order:
  - `faction`, and `kind` (`alien` or `human` by its template, `null` without one);
  - `habs`: every hab it owns; `habs_by_body`: `{"body", "habs"}` per space body (the hab's
    `barycenter`), in body ID order. A hab without a known body counts in `habs` only;
  - `fleets`: fleets whose `faction` it is; `ships`: ships whose `fleet` is one of those fleets;
  - `finished_projects`: the entries of `finishedProjectNames`, a repeated project counted per
    completion.
- `unattributed`: `habs`, `fleets` and `ships` whose owner is `null`, unresolved or not a faction
  of the save. They are counted here rather than dropped.
- `world`:
  - `nations`: the number of nation states, including those that hold no region;
    `nations_with_regions`: those whose region list is not empty (unknown when any nation's list
    is); `population`: the summed population of every region;
  - `finished_technologies`: the length of `finishedTechsNames`. Research is campaign-wide, so this
    count is not per faction;
  - `milestones`: `{"milestone", "faction"}` per `globalMilestones` entry, in serialized order;
  - `nuclear`: `nuclearStrikes`, `looseNukes`, `currentNuclearExchanges`;
  - `climate`: `earthAtmosphericCO2_ppm`, `earthAtmosphericCH4_ppm`, `earthAtmosphericN2O_ppm`,
    `stratosphericAerosols_ppm`, `globalSeaLevelAnomaly_cm`, `globalSeaLevelRise1Triggered`,
    `globalSeaLevelRise2Triggered`.

A report is built while its save is normalized, so it adds no third snapshot to memory. The
same save always gives the same report.

Failures print one message to stderr naming the path that failed and no traceback. With
`--log-level info`, the run logs the paths given and candidate files, the number of campaigns and
the selected campaign's number (with `interactive=True` when it was picked), the ordering summary
(usable saves, distinct saves, duplicates, skipped files, tied game times, intervals) and
per-interval event counts, and with `--narrative` the number of narrative events. `--log-level debug` adds one line per skipped file with its file name
and error class; directory paths are never logged.

## Exit codes

| Code | When |
| --- | --- |
| 0 | Every named path was used and every interval was analyzed (including when only one distinct save remained). Files skipped inside a named directory do not change it. |
| 2 | Usage error: fewer than two usable saves after directory expansion or in the chosen campaign; several campaigns without `--campaign`, or a `--campaign` that matches no campaign or several, when stdin or stderr is not a terminal; a cancelled campaign picker; an unknown `--format` or `--min-significance`; or `--changes` with `--narrative --format json`. |
| 4 | A named path cannot be read (missing or unreadable), or a named directory holds no files or no usable save. |
| 5 | A named file is not a supported save (malformed, wrong shape, or unsupported format or game version) or has no parseable game time. |
| 8 | The settings file (`--config` or `TINARRATIVE_CONFIG`) cannot be read, is not valid TOML, or names an unknown key or an invalid value. Nothing is printed on stdout. |
