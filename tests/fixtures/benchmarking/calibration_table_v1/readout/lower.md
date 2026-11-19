# Stake calibration readout

## Calibration state

| Measure | Reference | Code's |
| --- | ---: | ---: |
| power | 0.006309573444801933 (changed) | 0.01 |
| population | 0.01 | 0.01 |
| organization | 0.01 | 0.01 |
| hab | 0.015 | 0.015 |
| fleet | 0.01 | 0.01 |
| battle | 0.0033 | 0.0033 |
| faction | 0.0000001 (changed) | 0.14285714285714285 |
| nuclear | 0.01 | 0.01 |

Every event type is at the code's base level.

- Campaigns: alpha, beta
- Types: all
- Cache key: `golden`
- State: `#ref=power:0.006309573444801933,faction:0.0000001`

## Summary

References: power 0.006309573444801933 (code 0.01), faction 0.0000001 (code 0.14285714285714285); every other measure at the code's. Base levels: every type at the code's. Campaigns: alpha, beta. Types: all. 9 events move level; the narrator package goes from 14 to 13 events at major or above (-1); 2 events with members change. What moves: atomic.near trivial -> minor 6; faction.takeover major -> campaign_defining 2; atomic.far trivial -> minor 1. Drafts: held (#1) at base minor: 3 events (minor 2, major 1), 2 set by a cited event; moved (#2) at base trivial: 1 event (minor 1), 1 set by a cited event.

## Level counts

| Type | Level | Replay | Baseline | Change |
| --- | --- | --- | --- | --- |
| atomic.far | trivial | 0 | 1 | -1 |
| atomic.far | minor | 2 | 1 | +1 |
| atomic.near | trivial | 1 | 7 | -6 |
| atomic.near | minor | 7 | 1 | +6 |
| atomic.other | minor | 1 | 1 | 0 |
| atomic.other | major | 1 | 1 | 0 |
| atomic.plain | trivial | 1 | 1 | 0 |
| atomic.plain | minor | 1 | 1 | 0 |
| atomic.spread | trivial | 23 | 23 | 0 |
| atomic.spread | minor | 11 | 11 | 0 |
| atomic.spread | major | 8 | 8 | 0 |
| atomic.spread | campaign_defining | 6 | 6 | 0 |
| atomic.thing | trivial | 1 | 1 | 0 |
| atomic.thing | minor | 5 | 5 | 0 |
| atomic.thing | major | 2 | 2 | 0 |
| campaign.first_milestone | minor | 1 | 1 | 0 |
| faction.takeover | major | 8 | 10 | -2 |
| faction.takeover | campaign_defining | 3 | 1 | +2 |
| faction.takeover_wave | major | 2 | 3 | -1 |
| nation.cession | minor | 1 | 1 | 0 |
| nation.expansion | minor | 1 | 1 | 0 |

## What moves

| Type | From | To | Count | Via a cited event |
| --- | --- | --- | --- | --- |
| atomic.near | trivial | minor | 6 | 0 |
| faction.takeover | major | campaign_defining | 2 | 0 |
| atomic.far | trivial | minor | 1 | 0 |

## Member verdicts

Groups and candidates: falls_apart 1, keeps_members 1, loses_members 1.

| Campaign | Event | Type | Verdict | Kept | Lost | Distinct / minimum | Stale stake |
| --- | --- | --- | --- | --- | --- | --- | --- |
| alpha | `shrunk-group` | faction.takeover_wave | loses_members | 3 | `shrunk-0` | 3 / 3 | yes |
| alpha | `gone-group` | faction.takeover_wave | falls_apart | 2 | `gone-0` | 2 / 3 | yes |

## Cut-offs

### power

Cut-off at share 0.000355 (offset -1.25):

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `near-6` | atomic.near | 0.000347 | 24 | trivial | trivial | own |
| below | beta | `spread-42` | atomic.spread | 0.000256 | 73 | major | major | own |
| below | beta | `spread-38` | atomic.spread | 0.000161 | 21 | trivial | trivial | own |
| below | beta | `spread-44` | atomic.spread | 0.000139 | 20 | trivial | trivial | own |
| below | beta | `spread-12` | atomic.spread | 0.000119 | 45 | minor | minor | own |
| above | alpha | `near-5` | atomic.near | 0.000372 | 25 | minor | trivial | own |
| above | alpha | `near-4` | atomic.near | 0.000398 | 25 | minor | trivial | own |
| above | alpha | `near-3` | atomic.near | 0.000427 | 25 | minor | trivial | own |
| above | alpha | `far-low` | atomic.far | 0.000447 | 25 | minor | trivial | own |
| above | alpha | `near-2` | atomic.near | 0.000457 | 26 | minor | trivial | own |

Cut-off at share 0.112 (offset 1.25):

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | beta | `spread-13` | atomic.spread | 0.107 | 49 | minor | minor | own |
| below | beta | `spread-35` | atomic.spread | 0.0912 | 24 | trivial | trivial | own |
| below | beta | `spread-47` | atomic.spread | 0.0791 | 23 | trivial | trivial | own |
| below | beta | `spread-17` | atomic.spread | 0.0507 | 21 | trivial | trivial | own |
| below | beta | `spread-14` | atomic.spread | 0.0455 | 71 | major | major | own |
| above | beta | `spread-19` | atomic.spread | 0.139 | 100 | campaign_defining | campaign_defining | own |
| above | alpha | `gone-0` | faction.takeover | 0.158 | 76 | campaign_defining | major | own |
| above | alpha | `shrunk-0` | faction.takeover | 0.158 | 76 | campaign_defining | major | own |
| above | alpha | `far-high` | atomic.far | 0.224 | 27 | minor | minor | own |
| above | beta | `spread-15` | atomic.spread | 0.241 | 77 | campaign_defining | campaign_defining | own |

### population

Cut-off at share 0.000562 (offset -1.25):

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | beta | `spread-34` | atomic.spread | 0.000501 | 0 | trivial | trivial | own |
| below | beta | `spread-37` | atomic.spread | 0.000417 | 0 | trivial | trivial | own |
| below | beta | `spread-46` | atomic.spread | 0.000393 | 23 | trivial | trivial | own |
| below | beta | `spread-8` | atomic.spread | 0.000202 | 45 | minor | minor | own |
| below | beta | `spread-24` | atomic.spread | 7.27e-05 | 67 | major | major | own |
| above | beta | `spread-22` | atomic.spread | 0.000648 | 0 | trivial | trivial | own |
| above | beta | `spread-40` | atomic.spread | 0.000919 | 27 | minor | minor | own |
| above | beta | `spread-43` | atomic.spread | 0.00323 | 7 | trivial | trivial | own |
| above | beta | `spread-45` | atomic.spread | 0.00361 | 33 | minor | minor | own |
| above | beta | `spread-18` | atomic.spread | 0.0038 | 8 | trivial | trivial | own |

Cut-off at share 0.178 (offset 1.25):

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `both` | atomic.thing | 0.1 | 47 | minor | minor | own |
| below | alpha | `land` | atomic.thing | 0.1 | 47 | minor | minor | own |
| below | beta | `spread-33` | atomic.spread | 0.0569 | 95 | campaign_defining | campaign_defining | own |
| below | beta | `spread-4` | atomic.spread | 0.0462 | 94 | campaign_defining | campaign_defining | own |
| below | beta | `land` | atomic.other | 0.03 | 42 | minor | minor | own |
| above | beta | `spread-27` | atomic.spread | 0.259 | 26 | minor | minor | own |

### organization

Cut-off at share 0.000562 (offset -1.25):

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | alpha | `organized` | atomic.other | 0.004 | 58 | major | major | own |

Cut-off at share 0.178 (offset 1.25):

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `organized` | atomic.other | 0.004 | 58 | major | major | own |

### hab

Cut-off at share 0.000844 (offset -1.25):

No event has this stake.

Cut-off at share 0.267 (offset 1.25):

No event has this stake.

### fleet

Cut-off at share 0.000562 (offset -1.25):

No event has this stake.

Cut-off at share 0.178 (offset 1.25):

No event has this stake.

### battle

Cut-off at share 0.000186 (offset -1.25):

No event has this stake.

Cut-off at share 0.0587 (offset 1.25):

No event has this stake.

### faction

Cut-off at share 5.62e-09 (offset -1.25):

No event has this stake.

Cut-off at share 1.78e-06 (offset 1.25):

No event has this stake.

### nuclear

Cut-off at share 0.000562 (offset -1.25):

No event has this stake.

Cut-off at share 0.178 (offset 1.25):

No event has this stake.

## Draft stakes

| Draft | Label | Issue | Measures | Base | Own base | Events | Ruled | Set by a cited event |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| held | Held share | #1 | power, population | minor | minor | 3 | 1 | 2 |
| moved | Moved share | #2 | population | trivial | trivial | 1 | 0 | 1 |

Level counts at each draft's base, against its own:

| Draft | Level | Replay | Own base | Change |
| --- | --- | --- | --- | --- |
| held | minor | 2 | 2 | 0 |
| held | major | 1 | 1 | 0 |
| moved | minor | 1 | 1 | 0 |

### held on power

Cut-off at share 0.000355 (offset -1.25):

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | alpha | `draft:held:deal` | 0.001 | 47 | minor | minor | `land` | no |
| above | alpha | `draft:held:arc` | 0.00398 | 47 | minor | minor | `land` | no |
| above | alpha | `draft:held:grow` | 0.0158 | 66 | major | major | own | yes |

Cut-off at share 0.112 (offset 1.25):

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:held:grow` | 0.0158 | 66 | major | major | own | yes |
| below | alpha | `draft:held:arc` | 0.00398 | 47 | minor | minor | `land` | no |
| below | alpha | `draft:held:deal` | 0.001 | 47 | minor | minor | `land` | no |

### held on population

Cut-off at share 0.000562 (offset -1.25):

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | alpha | `draft:held:arc` | 0.02 | 47 | minor | minor | `land` | no |

Cut-off at share 0.178 (offset 1.25):

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:held:arc` | 0.02 | 47 | minor | minor | `land` | no |

### moved on population

Cut-off at share 0.000562 (offset -1.25):

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | alpha | `draft:moved:deal` | 0.158 | 47 | minor | minor | `land` | no |

Cut-off at share 0.178 (offset 1.25):

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:moved:deal` | 0.158 | 47 | minor | minor | `land` | no |

## Snippet

```python
StakeMeasure.POWER: MeasureSpec(reference=0.006309573444801933, ...),  # code: 0.01
StakeMeasure.FACTION: MeasureSpec(reference=0.0000001, ...),  # code: 0.14285714285714285
```
