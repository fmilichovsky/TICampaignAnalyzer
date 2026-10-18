# Save sequence

## Saves

1. `2032-01-01T00:00:00`: `politics_before.json`
2. `2032-04-01T00:00:00`: `politics_after.json`
3. `2032-07-01T00:00:00`: `politics_reverted.json`

3 saves given; ordered by serialized game time.

## Intervals

### 2032-01-01T00:00:00 to 2032-04-01T00:00:00

- 31 state changes

#### Inferred events

Reconstructed from the objective results below; never observed directly.

- nation:20 annexed 1 region of nation:21 (confidence: `medium`)
  - from `nation.relation_changed/wars/nation:20/nation:21/added@2032-04-01T00:00:00`: nation:20 and nation:21: wars entry added (listed by both)
  - from `region.nation_changed/region:42@2032-04-01T00:00:00`: region:42 nation: nation:21 -> nation:20
- nation:20 gained 1 region from nation:21 (confidence: `medium`)
  - from `region.nation_changed/region:42@2032-04-01T00:00:00`: region:42 nation: nation:21 -> nation:20
- nation:21 lost 1 region to nation:20 (confidence: `medium`)
  - from `region.nation_changed/region:42@2032-04-01T00:00:00`: region:42 nation: nation:21 -> nation:20

#### Objective analyzer results

Analyzer results:

- control point:10 (nation:20) controller: faction:15 -> null
- control point:9 (nation:20) controller: faction:16 -> faction:15; loss recorded by faction:16 on 2032-02-15T00:00:00
- control point:11 nation: nation:21 -> nation:20
- councilor:100 faction: faction:15 -> faction:16
- councilor:102 faction: faction:16 -> null
- region:42 nation: nation:21 -> nation:20

Councilor:

- councilor:100 (faction:16) detaining faction: null -> faction:16
- councilor:101 (null) location: region:40 -> space object:140
- councilor:100 (faction:16) status: "Available" -> "FixtureStatusB"

Faction:

- faction:16 records control point:9 as lost on 2032-02-15T00:00:00
- faction:15 councilors list: [councilor:100] -> unknown (unresolved_reference, raw=[{"value": 999}])

Nation:

- nation:20 records an executive change dated 2032-02-15T00:00:00: new executive faction:15 (previously faction:16)
- nation:22 breakaway parent: null -> nation:20
- nation:20 capital: region:40 -> region:41
- nation:22 controlPoints list: +control point:10
- nation:20 and nation:21: rivals entry removed (listed by nation:20 only)
- nation:20 and nation:21: wars entry added (listed by both)

### 2032-04-01T00:00:00 to 2032-07-01T00:00:00

- 10 state changes

#### Inferred events

Reconstructed from the objective results below; never observed directly.

- nation:21 gained 1 region from nation:20 (confidence: `medium`)
  - from `region.nation_changed/region:42@2032-07-01T00:00:00`: region:42 nation: nation:20 -> nation:21
- nation:20 lost 1 region to nation:21 (confidence: `medium`)
  - from `region.nation_changed/region:42@2032-07-01T00:00:00`: region:42 nation: nation:20 -> nation:21

#### Objective analyzer results

Analyzer results:

- control point:9 (nation:20) controller: faction:15 -> faction:16
- region:42 nation: nation:20 -> nation:21
