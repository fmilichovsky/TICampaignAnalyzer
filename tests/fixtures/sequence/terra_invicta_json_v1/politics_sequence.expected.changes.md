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

- 31 state changes

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
- Fixture Eastland (nation:22) controlPoints list: +Fixture CP 10 (control point:10)
- Fixture Northland (nation:20) and Fixture Southland (nation:21): rivals entry removed (listed by Fixture Northland (nation:20) only)
- Fixture Northland (nation:20) and Fixture Southland (nation:21): wars entry added (listed by both)

#### State changes

Campaign:

- campaign campaign_day: 731 -> 822
- campaign campaign_quarter: 8 -> 9
- campaign date: "2032-01-01T00:00:00" -> "2032-04-01T00:00:00"
- campaign game_time_string: "1/1/2032 12:00:00 AM" -> "4/1/2032 12:00:00 AM"

Control Point:

- control point:9 faction: faction:16 -> faction:15
- control point:10 faction: faction:15 -> null
- control point:11 nation: nation:21 -> nation:20

Councilor:

- councilor:100 detainingFaction: null -> faction:16
- councilor:100 faction: faction:15 -> faction:16
- councilor:100 status: "Available" -> "FixtureStatusB"
- councilor:101 location: region:40 -> space object:140
- councilor:101 priorLocation: null -> region:40
- councilor:102 faction: faction:16 -> null

Faction:

- faction:15 controlPoints: +control point:9 -control point:10
- faction:15 councilors: [councilor:100] -> unknown (unresolved_reference, raw=[{"value": 999}])
- faction:16 controlPoints: -control point:9
- faction:16 councilors: +councilor:100 -councilor:102
- faction:16 lostControlPoints: +1 entries

Nation:

- nation:20 breakaways: +nation:22
- nation:20 capital: region:40 -> region:41
- nation:20 controlPoints: +control point:11
- nation:20 lastExecutiveChange: ~2 entries
- nation:20 regions: +region:42
- nation:20 rivals: -nation:21
- nation:20 wars: +nation:21
- nation:21 controlPoints: -control point:11
- nation:21 regions: -region:42
- nation:21 wars: +nation:20
- nation:22 breakawayParent: null -> nation:20
- nation:22 controlPoints: +control point:10

Region:

- region:42 nation: nation:21 -> nation:20

### 2032-04-01T00:00:00 to 2032-07-01T00:00:00

- 10 state changes

#### Objective analyzer results

Analyzer results:

- Fixture CP 9 (control point:9) (Fixture Northland (nation:20)) controller: Fixture Resistance (faction:15) -> Fixture Servants (faction:16)
- Fixture South (region:42) nation: Fixture Northland (nation:20) -> Fixture Southland (nation:21)

#### State changes

Campaign:

- campaign campaign_day: 822 -> 913
- campaign campaign_quarter: 9 -> 10
- campaign date: "2032-04-01T00:00:00" -> "2032-07-01T00:00:00"
- campaign game_time_string: "4/1/2032 12:00:00 AM" -> "7/1/2032 12:00:00 AM"

Control Point:

- control point:9 faction: faction:15 -> faction:16

Faction:

- faction:15 controlPoints: -control point:9
- faction:16 controlPoints: +control point:9

Nation:

- nation:20 regions: -region:42
- nation:21 regions: +region:42

Region:

- region:42 nation: nation:20 -> nation:21
