# Save sequence

## Campaign

- key: `fixture-resistance`
- player faction: Fixture Resistance
- scenario: `FixtureMaster/FixtureScenario`
- real-world start: unknown

Grouped by matching human faction, faction name and scenario; no real-world start was found.

## Saves

1. `2032-01-01T00:00:00`: `politics_before.json`
2. `2032-04-01T00:00:00`: `politics_after.json`
3. `2032-07-01T00:00:00`: `politics_reverted.json`

3 saves given; ordered by serialized game time.

## Narrative

Aggregated from the events of every interval below.

### 2032

- `2032-01-01T00:00:00` to `2032-04-01T00:00:00`: Fixture Resistance (faction:15) took control of Fixture Northland (nation:20) from Fixture Servants (faction:16) (inferred, confidence `low`, significance `campaign_defining`)
  - roles: actor: Fixture Resistance (faction:15); target: Fixture Northland (nation:20); loser: Fixture Servants (faction:16)
  - attributes: cause: `"Politics"`
  - from `control_point.controller_changed/control point:9@2032-04-01T00:00:00`
  - from `councilor.detaining_faction_changed/councilor:100@2032-04-01T00:00:00`
  - from `councilor.faction_changed/councilor:100@2032-04-01T00:00:00`
  - from `councilor.faction_changed/councilor:102@2032-04-01T00:00:00`
  - from `faction.nation_control_changed/nation:20/executive@2032-04-01T00:00:00`
  - from `nation.executive_change_recorded/nation:20@2032-04-01T00:00:00`
  - from `nation.unrest_attempts_changed/nation:20/faction:15@2032-04-01T00:00:00`
- `2032-01-01T00:00:00` to `2032-07-01T00:00:00` (open): Fixture Servants (faction:16) took control of Fixture Northland (nation:20) from Fixture Resistance (faction:15) (inferred, confidence `low`, significance `campaign_defining`)
  - roles: actor: Fixture Servants (faction:16); target: Fixture Northland (nation:20); loser: Fixture Resistance (faction:15)
  - from `control_point.controller_changed/control point:9@2032-07-01T00:00:00`
  - from `faction.nation_control_changed/nation:20/executive@2032-07-01T00:00:00`
  - from `nation.unrest_attempts_changed/nation:20/faction:16@2032-04-01T00:00:00`
- `2032-01-01T00:00:00` to `2032-04-01T00:00:00`: Fixture Southland (nation:21) claimed regions of Fixture Northland (nation:20) (objective, confidence `high`, significance `major`)
  - roles: actor: Fixture Southland (nation:21); target: Fixture Northland (nation:20)
  - from `nation.claims_changed/nation:21@2032-04-01T00:00:00`
- `2032-04-01T00:00:00` to `2032-07-01T00:00:00`: Fixture Northland (nation:20) ceded 1 region to Fixture Southland (nation:21) (inferred, confidence `low`, significance `major`)
  - roles: actor: Fixture Northland (nation:20); beneficiary: Fixture Southland (nation:21); location: Fixture South (region:42)
  - attributes: region_count: `1`
  - from `nation.territory_gained/nation:21@2032-07-01T00:00:00`
  - from `nation.territory_lost/nation:20@2032-07-01T00:00:00`

## Intervals

### 2032-01-01T00:00:00 to 2032-04-01T00:00:00

- 34 state changes

#### Inferred events

Reconstructed from the objective results below; never observed directly.

- Fixture Northland (nation:20) executive control changed: Fixture Servants (faction:16) -> Fixture Resistance (faction:15) (confidence: `medium`)
  - from `control_point.controller_changed/control point:10@2032-04-01T00:00:00`: Fixture CP 10 (control point:10) (Fixture Northland (nation:20)) controller: Fixture Resistance (faction:15) -> null
  - from `control_point.controller_changed/control point:9@2032-04-01T00:00:00`: Fixture CP 9 (control point:9) (Fixture Northland (nation:20)) controller: Fixture Servants (faction:16) -> Fixture Resistance (faction:15); loss recorded by Fixture Servants (faction:16) on 2032-02-15T00:00:00
  - from `control_point.loss_recorded/faction:16/control point:9@2032-04-01T00:00:00`: Fixture Servants (faction:16) records Fixture CP 9 (control point:9) as lost on 2032-02-15T00:00:00
  - from `nation.executive_change_recorded/nation:20@2032-04-01T00:00:00`: Fixture Northland (nation:20) records an executive change dated 2032-02-15T00:00:00: new executive Fixture Resistance (faction:15) (previously Fixture Servants (faction:16))
- Fixture Northland (nation:20) plurality control changed: null -> Fixture Resistance (faction:15) (confidence: `medium`)
  - from `control_point.controller_changed/control point:10@2032-04-01T00:00:00`: Fixture CP 10 (control point:10) (Fixture Northland (nation:20)) controller: Fixture Resistance (faction:15) -> null
  - from `control_point.controller_changed/control point:9@2032-04-01T00:00:00`: Fixture CP 9 (control point:9) (Fixture Northland (nation:20)) controller: Fixture Servants (faction:16) -> Fixture Resistance (faction:15); loss recorded by Fixture Servants (faction:16) on 2032-02-15T00:00:00
  - from `control_point.loss_recorded/faction:16/control point:9@2032-04-01T00:00:00`: Fixture Servants (faction:16) records Fixture CP 9 (control point:9) as lost on 2032-02-15T00:00:00
  - from `nation.executive_change_recorded/nation:20@2032-04-01T00:00:00`: Fixture Northland (nation:20) records an executive change dated 2032-02-15T00:00:00: new executive Fixture Resistance (faction:15) (previously Fixture Servants (faction:16))
- Fixture Northland (nation:20) annexed 1 region of Fixture Southland (nation:21) (confidence: `medium`)
  - from `nation.relation_changed/wars/nation:20/nation:21/added@2032-04-01T00:00:00`: Fixture Northland (nation:20) and Fixture Southland (nation:21): wars entry added (listed by both)
  - from `region.nation_changed/region:42@2032-04-01T00:00:00`: Fixture South (region:42) nation: Fixture Southland (nation:21) -> Fixture Northland (nation:20)

2 inferred events below major significance omitted.

#### Objective analyzer results

Analyzer results:

- Fixture CP 10 (control point:10) (Fixture Northland (nation:20)) controller: Fixture Resistance (faction:15) -> null
- Fixture CP 9 (control point:9) (Fixture Northland (nation:20)) controller: Fixture Servants (faction:16) -> Fixture Resistance (faction:15); loss recorded by Fixture Servants (faction:16) on 2032-02-15T00:00:00
- Fixture Councilor 100 (councilor:100) faction: Fixture Resistance (faction:15) -> Fixture Servants (faction:16)
- Fixture Councilor 102 (councilor:102) faction: Fixture Servants (faction:16) -> null
- Fixture South (region:42) nation: Fixture Southland (nation:21) -> Fixture Northland (nation:20)

Councilor:

- Fixture Councilor 100 (councilor:100) (Fixture Servants (faction:16)) detaining faction: null -> Fixture Servants (faction:16)

Nation:

- Fixture Southland (nation:21) claims list: +[Fixture North (region:40)]
- Fixture Northland (nation:20) and Fixture Southland (nation:21): wars entry added (listed by both)

13 objective analyzer results below major significance omitted.

### 2032-04-01T00:00:00 to 2032-07-01T00:00:00

- 10 state changes

#### Inferred events

Reconstructed from the objective results below; never observed directly.

- Fixture Northland (nation:20) executive control changed: Fixture Resistance (faction:15) -> Fixture Servants (faction:16) (confidence: `medium`)
  - from `control_point.controller_changed/control point:9@2032-07-01T00:00:00`: Fixture CP 9 (control point:9) (Fixture Northland (nation:20)) controller: Fixture Resistance (faction:15) -> Fixture Servants (faction:16)
- Fixture Northland (nation:20) plurality control changed: Fixture Resistance (faction:15) -> Fixture Servants (faction:16) (confidence: `medium`)
  - from `control_point.controller_changed/control point:9@2032-07-01T00:00:00`: Fixture CP 9 (control point:9) (Fixture Northland (nation:20)) controller: Fixture Resistance (faction:15) -> Fixture Servants (faction:16)

2 inferred events below major significance omitted.

#### Objective analyzer results

Analyzer results:

- Fixture CP 9 (control point:9) (Fixture Northland (nation:20)) controller: Fixture Resistance (faction:15) -> Fixture Servants (faction:16)
- Fixture South (region:42) nation: Fixture Northland (nation:20) -> Fixture Southland (nation:21)
