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
- Fixture Northland (nation:20) gained 1 region from Fixture Southland (nation:21) (confidence: `medium`)
  - from `region.nation_changed/region:42@2032-04-01T00:00:00`: Fixture South (region:42) nation: Fixture Southland (nation:21) -> Fixture Northland (nation:20)
- Fixture Southland (nation:21) lost 1 region to Fixture Northland (nation:20) (confidence: `medium`)
  - from `region.nation_changed/region:42@2032-04-01T00:00:00`: Fixture South (region:42) nation: Fixture Southland (nation:21) -> Fixture Northland (nation:20)

#### Objective analyzer results

Analyzer results:

- Fixture CP 10 (control point:10) (Fixture Northland (nation:20)) controller: Fixture Resistance (faction:15) -> null
- Fixture CP 9 (control point:9) (Fixture Northland (nation:20)) controller: Fixture Servants (faction:16) -> Fixture Resistance (faction:15); loss recorded by Fixture Servants (faction:16) on 2032-02-15T00:00:00
- Fixture CP 11 (control point:11) nation: Fixture Southland (nation:21) -> Fixture Northland (nation:20)
- Fixture Councilor 100 (councilor:100) faction: Fixture Resistance (faction:15) -> Fixture Servants (faction:16)
- Fixture Councilor 102 (councilor:102) faction: Fixture Servants (faction:16) -> null
- Fixture South (region:42) nation: Fixture Southland (nation:21) -> Fixture Northland (nation:20)

Councilor:

- Fixture Councilor 100 (councilor:100) (Fixture Servants (faction:16)) detaining faction: null -> Fixture Servants (faction:16)
- Fixture Councilor 101 (councilor:101) (null) location: Fixture North (region:40) -> Fixture Hab 140 (space object:140)
- Fixture Councilor 100 (councilor:100) (Fixture Servants (faction:16)) status: "Available" -> "FixtureStatusB"

Faction:

- Fixture Servants (faction:16) records Fixture CP 9 (control point:9) as lost on 2032-02-15T00:00:00
- Fixture Resistance (faction:15) councilors list: [Fixture Councilor 100 (councilor:100)] -> unknown (unresolved_reference, raw=[{"value": 999}])

Nation:

- Fixture Northland (nation:20) records an executive change dated 2032-02-15T00:00:00: new executive Fixture Resistance (faction:15) (previously Fixture Servants (faction:16))
- Fixture Eastland (nation:22) breakaway parent: null -> Fixture Northland (nation:20)
- Fixture Northland (nation:20) capital: Fixture North (region:40) -> Fixture East (region:41)
- Fixture Southland (nation:21) claims list: +[Fixture North (region:40)]
- Fixture Eastland (nation:22) controlPoints list: +Fixture CP 10 (control point:10)
- Fixture Eastland (nation:22) hostile claims list: +[Fixture South (region:42)]
- Fixture Southland (nation:21) GDP rank: 2 -> unranked
- Fixture Northland (nation:20) and Fixture Southland (nation:21): rivals entry removed (listed by Fixture Northland (nation:20) only)
- Fixture Northland (nation:20) and Fixture Southland (nation:21): wars entry added (listed by both)
- Fixture Northland (nation:20) unrest attempts by Fixture Resistance (faction:15): null -> 1
- Fixture Northland (nation:20) unrest attempts by Fixture Servants (faction:16): 1 -> 2

### 2032-04-01T00:00:00 to 2032-07-01T00:00:00

- 10 state changes

#### Inferred events

Reconstructed from the objective results below; never observed directly.

- Fixture Northland (nation:20) executive control changed: Fixture Resistance (faction:15) -> Fixture Servants (faction:16) (confidence: `medium`)
  - from `control_point.controller_changed/control point:9@2032-07-01T00:00:00`: Fixture CP 9 (control point:9) (Fixture Northland (nation:20)) controller: Fixture Resistance (faction:15) -> Fixture Servants (faction:16)
- Fixture Northland (nation:20) plurality control changed: Fixture Resistance (faction:15) -> Fixture Servants (faction:16) (confidence: `medium`)
  - from `control_point.controller_changed/control point:9@2032-07-01T00:00:00`: Fixture CP 9 (control point:9) (Fixture Northland (nation:20)) controller: Fixture Resistance (faction:15) -> Fixture Servants (faction:16)
- Fixture Southland (nation:21) gained 1 region from Fixture Northland (nation:20) (confidence: `medium`)
  - from `region.nation_changed/region:42@2032-07-01T00:00:00`: Fixture South (region:42) nation: Fixture Northland (nation:20) -> Fixture Southland (nation:21)
- Fixture Northland (nation:20) lost 1 region to Fixture Southland (nation:21) (confidence: `medium`)
  - from `region.nation_changed/region:42@2032-07-01T00:00:00`: Fixture South (region:42) nation: Fixture Northland (nation:20) -> Fixture Southland (nation:21)

#### Objective analyzer results

Analyzer results:

- Fixture CP 9 (control point:9) (Fixture Northland (nation:20)) controller: Fixture Resistance (faction:15) -> Fixture Servants (faction:16)
- Fixture South (region:42) nation: Fixture Northland (nation:20) -> Fixture Southland (nation:21)

Nation:

- Fixture Southland (nation:21) GDP rank: unranked -> 2
