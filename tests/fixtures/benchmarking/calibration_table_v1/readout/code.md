# Share calibration readout

## Calibration state

| Measure | Reference | Code's |
| --- | ---: | ---: |
| power | 0.01 | 0.01 |
| population | 0.01 | 0.01 |
| organization | 0.01 | 0.01 |
| hab | 0.015 | 0.015 |
| fleet | 0.01 | 0.01 |
| battle | 0.0033 | 0.0033 |
| space_loss | 0.01 | 0.01 |
| faction | 0.14285714285714285 | 0.14285714285714285 |
| nuclear | 0.01 | 0.01 |

Every event type is at the code's base level.

- Campaigns: alpha, beta
- Types: all
- Cache key: `golden`
- State: the default (no hash)

## Summary

References: every measure at the code's. Base levels: every type at the code's. Campaigns: alpha, beta. Types: all. 0 events move level; the narrator package goes from 14 to 14 events at major or above (0); 0 events with members change. What moves: nothing. Drafts: held (#1) at base minor: 3 events (minor 2, major 1), 2 set by a cited event; moved (#2) at base trivial: 1 event (minor 1), 1 set by a cited event.

## Level counts

| Type | Level | Replay | Baseline | Change |
| --- | --- | --- | --- | --- |
| atomic.far | trivial | 1 | 1 | 0 |
| atomic.far | minor | 1 | 1 | 0 |
| atomic.near | trivial | 7 | 7 | 0 |
| atomic.near | minor | 1 | 1 | 0 |
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
| faction.takeover | major | 10 | 10 | 0 |
| faction.takeover | campaign_defining | 1 | 1 | 0 |
| faction.takeover_wave | major | 3 | 3 | 0 |
| nation.cession | minor | 1 | 1 | 0 |
| nation.expansion | minor | 1 | 1 | 0 |

## What moves

No event moves.

## Member verdicts

Groups and candidates: keeps_members 3.

Every group keeps its members.

## Cut-offs

### power

Cut-off at share 0.000562 (offset -1.25):

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `near-0` | atomic.near | 0.000525 | 24 | trivial | trivial | own |
| below | alpha | `near-1` | atomic.near | 0.00049 | 24 | trivial | trivial | own |
| below | alpha | `near-2` | atomic.near | 0.000457 | 24 | trivial | trivial | own |
| below | alpha | `far-low` | atomic.far | 0.000447 | 23 | trivial | trivial | own |
| below | alpha | `near-3` | atomic.near | 0.000427 | 23 | trivial | trivial | own |
| above | alpha | `at-cut` | atomic.thing | 0.000562 | 25 | minor | minor | own |
| above | alpha | `inside` | atomic.near | 0.000589 | 25 | minor | minor | own |
| above | alpha | `deal` | nation.cession | 0.001 | 47 | minor | minor | `land` |
| above | beta | `spread-5` | atomic.spread | 0.00125 | 78 | campaign_defining | campaign_defining | own |
| above | beta | `spread-30` | atomic.spread | 0.00126 | 53 | major | major | own |

Cut-off at share 0.178 (offset 1.25):

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `gone-0` | faction.takeover | 0.158 | 74 | major | major | own |
| below | alpha | `shrunk-0` | faction.takeover | 0.158 | 74 | major | major | own |
| below | beta | `spread-19` | atomic.spread | 0.139 | 98 | campaign_defining | campaign_defining | own |
| below | beta | `spread-13` | atomic.spread | 0.107 | 47 | minor | minor | own |
| below | beta | `spread-35` | atomic.spread | 0.0912 | 22 | trivial | trivial | own |
| above | alpha | `far-high` | atomic.far | 0.224 | 26 | minor | minor | own |
| above | beta | `spread-15` | atomic.spread | 0.241 | 76 | campaign_defining | campaign_defining | own |
| above | beta | `spread-9` | atomic.spread | 0.295 | 77 | campaign_defining | campaign_defining | own |
| above | alpha | `outside` | faction.takeover | 0.316 | 77 | campaign_defining | campaign_defining | own |

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

No event has this share.

Cut-off at share 0.267 (offset 1.25):

No event has this share.

### fleet

Cut-off at share 0.000562 (offset -1.25):

No event has this share.

Cut-off at share 0.178 (offset 1.25):

No event has this share.

### battle

Cut-off at share 0.000186 (offset -1.25):

No event has this share.

Cut-off at share 0.0587 (offset 1.25):

No event has this share.

### space_loss

Cut-off at share 0.000562 (offset -1.25):

No event has this share.

Cut-off at share 0.178 (offset 1.25):

No event has this share.

### faction

Cut-off at share 0.00803 (offset -1.25):

No event has this share.

Cut-off at share 2.54 (offset 1.25):

No event has this share.

### nuclear

Cut-off at share 0.000562 (offset -1.25):

No event has this share.

Cut-off at share 0.178 (offset 1.25):

No event has this share.

## Draft shares

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

Cut-off at share 0.000562 (offset -1.25):

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | alpha | `draft:held:deal` | 0.001 | 47 | minor | minor | `land` | no |
| above | alpha | `draft:held:arc` | 0.00398 | 47 | minor | minor | `land` | no |
| above | alpha | `draft:held:grow` | 0.0158 | 64 | major | major | own | yes |

Cut-off at share 0.178 (offset 1.25):

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:held:grow` | 0.0158 | 64 | major | major | own | yes |
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
# Every reference and base level is the code's.
```
