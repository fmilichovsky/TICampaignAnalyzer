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

- `2032-01-01T00:00:00` to `2032-04-01T00:00:00`: nothing listed (34 state changes; 26 events omitted with --constituents none)
- `2032-04-01T00:00:00` to `2032-07-01T00:00:00`: nothing listed (10 state changes; 6 events omitted with --constituents none)
