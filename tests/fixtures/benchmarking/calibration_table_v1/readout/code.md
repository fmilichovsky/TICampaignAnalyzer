# Share calibration readout

## Calibration state

| Scaling | Measure | Rise share | Drop share | Code's |
| --- | --- | ---: | ---: | ---: |
| power | power | 0.1778279410038923 | default | 0.1778279410038923 / default |
| population | population | 0.1778279410038923 | default | 0.1778279410038923 / default |
| organization | organization | 0.1778279410038923 | default | 0.1778279410038923 / default |
| hab | hab | 0.2667419115058384 | default | 0.2667419115058384 / default |
| fleet | fleet | 0.1778279410038923 | default | 0.1778279410038923 / default |
| battle | battle | 0.058683220531284455 | default | 0.058683220531284455 / default |
| space_loss | space_loss | 0.1778279410038923 | default | 0.1778279410038923 / default |
| faction | faction | 2.540399157198461 | default | 2.540399157198461 / default |
| nuclear | nuclear | 0.1778279410038923 | default | 0.1778279410038923 / default |

Every event type is on its code scaling.

Every event type is at the code's base level.

- Campaigns: alpha, beta
- Types: all
- Cache key: `golden`
- State: the default (no hash)

## Summary

Scalings: every scaling at the code's. Kinds: every type on its code scaling. Base levels: every type at the code's. Campaigns: alpha, beta. Types: all. 0 events move level; the narrator package goes from 14 to 14 events at major or above (0); 0 events with members change. What moves: nothing. Drafts: held (#1) at base minor: 3 events (minor 2, major 1), 2 set by a cited event; moved (#2) at base trivial: 1 event (minor 1), 1 set by a cited event.

## Level counts

| Type | Reason | Level | Replay | Baseline | Change |
| --- | --- | --- | --- | --- | --- |
| atomic.far | unexamined | minor | 2 | 2 | 0 |
| atomic.land | unexamined | minor | 2 | 2 | 0 |
| atomic.near | unexamined | minor | 8 | 8 | 0 |
| atomic.other | The ordinary instance — the rise of a regional power | major | 1 | 1 | 0 |
| atomic.plain | unexamined | trivial | 1 | 1 | 0 |
| atomic.plain | unexamined | minor | 1 | 1 | 0 |
| atomic.scatter | Trivial is a role — scattered churn (stale r1→r2) | trivial | 9 | 9 | 0 |
| atomic.scatter | Trivial is a role — scattered churn (stale r1→r2) | minor | 11 | 11 | 0 |
| atomic.scatter | Trivial is a role — scattered churn (stale r1→r2) | major | 3 | 3 | 0 |
| atomic.scatter | Trivial is a role — scattered churn (stale r1→r2) | campaign_defining | 2 | 2 | 0 |
| atomic.spread | unexamined | trivial | 5 | 5 | 0 |
| atomic.spread | unexamined | minor | 9 | 9 | 0 |
| atomic.spread | unexamined | major | 5 | 5 | 0 |
| atomic.spread | unexamined | campaign_defining | 4 | 4 | 0 |
| atomic.thing | unexamined | minor | 4 | 4 | 0 |
| atomic.thing | unexamined | major | 2 | 2 | 0 |
| campaign.first_milestone | unexamined | minor | 1 | 1 | 0 |
| faction.takeover | unexamined | major | 10 | 10 | 0 |
| faction.takeover | unexamined | campaign_defining | 1 | 1 | 0 |
| faction.takeover_wave | unexamined | major | 3 | 3 | 0 |
| nation.cession | unexamined | minor | 1 | 1 | 0 |
| nation.expansion | unexamined | minor | 1 | 1 | 0 |

## Coverage

| Type | Coverage | Total | alpha | beta |
| --- | --- | --- | --- | --- |
| atomic.far | thin | 2 | 2 | 0 |
| atomic.land | thin | 2 | 1 | 1 |
| atomic.near | thin | 8 | 8 | 0 |
| atomic.other | thin | 1 | 1 | 0 |
| atomic.plain | thin | 2 | 1 | 1 |
| atomic.scatter | thin | 25 | 0 | 25 |
| atomic.spread | thin | 23 | 0 | 23 |
| atomic.thing | covered | 6 | 3 | 3 |
| campaign.first_milestone | thin | 1 | 1 | 0 |
| faction.takeover | thin | 11 | 11 | 0 |
| faction.takeover_wave | thin | 3 | 3 | 0 |
| nation.cession | thin | 1 | 1 | 0 |
| nation.expansion | thin | 1 | 1 | 0 |

| Measure | Coverage | Total | alpha | beta |
| --- | --- | --- | --- | --- |
| power | covered | 51 | 25 | 26 |
| population | covered | 27 | 1 | 26 |
| organization | thin | 1 | 1 | 0 |
| hab | thin | 0 | 0 | 0 |
| fleet | thin | 0 | 0 | 0 |
| battle | thin | 0 | 0 | 0 |
| space_loss | thin | 0 | 0 | 0 |
| faction | thin | 0 | 0 | 0 |
| nuclear | thin | 0 | 0 | 0 |

## What moves

No event moves.

## Member verdicts

Groups and candidates: keeps_members 3.

Every group keeps its members.

## Cut-offs

### power

Drop 2 levels at share 1.78e-06:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | beta | `spread-6` | atomic.spread | 6.15e-06 | 25 | minor | minor | own |
| above | beta | `spread-1` | atomic.spread | 9.41e-06 | 25 | minor | minor | own |
| above | beta | `spread-41` | atomic.spread | 1.6e-05 | 0 | trivial | trivial | own |
| above | beta | `spread-36` | atomic.spread | 2.07e-05 | 35 | minor | minor | own |
| above | beta | `spread-3` | atomic.spread | 2.69e-05 | 0 | trivial | trivial | own |

Drop share at share 0.000562:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `at-cut` | atomic.thing | 0.000562 | 25 | minor | minor | own |
| below | alpha | `near-0` | atomic.near | 0.000525 | 25 | minor | minor | own |
| below | alpha | `near-1` | atomic.near | 0.00049 | 25 | minor | minor | own |
| below | alpha | `near-2` | atomic.near | 0.000457 | 25 | minor | minor | own |
| below | alpha | `far-low` | atomic.far | 0.000447 | 25 | minor | minor | own |
| above | alpha | `inside` | atomic.near | 0.000589 | 25 | minor | minor | own |
| above | alpha | `deal` | nation.cession | 0.001 | 47 | minor | minor | `land` |
| above | beta | `spread-5` | atomic.spread | 0.00125 | 78 | campaign_defining | campaign_defining | own |
| above | beta | `spread-30` | atomic.spread | 0.00126 | 53 | major | major | own |
| above | beta | `lean` | atomic.thing | 0.00158 | 54 | major | major | own |

Rise share at share 0.178:

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

Rise 2 levels at share 56.2:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `outside` | faction.takeover | 0.316 | 77 | campaign_defining | campaign_defining | own |
| below | beta | `spread-9` | atomic.spread | 0.295 | 77 | campaign_defining | campaign_defining | own |
| below | beta | `spread-15` | atomic.spread | 0.241 | 76 | campaign_defining | campaign_defining | own |
| below | alpha | `far-high` | atomic.far | 0.224 | 26 | minor | minor | own |
| below | alpha | `gone-0` | faction.takeover | 0.158 | 74 | major | major | own |

Rise 3 levels at share 1.78e+04:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `outside` | faction.takeover | 0.316 | 77 | campaign_defining | campaign_defining | own |
| below | beta | `spread-9` | atomic.spread | 0.295 | 77 | campaign_defining | campaign_defining | own |
| below | beta | `spread-15` | atomic.spread | 0.241 | 76 | campaign_defining | campaign_defining | own |
| below | alpha | `far-high` | atomic.far | 0.224 | 26 | minor | minor | own |
| below | alpha | `gone-0` | faction.takeover | 0.158 | 74 | major | major | own |

### population

Drop 2 levels at share 1.78e-06:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | beta | `spread-11` | atomic.scatter | 3.65e-06 | 0 | trivial | trivial | own |
| above | beta | `spread-39` | atomic.scatter | 1.45e-05 | 25 | minor | minor | own |
| above | beta | `spread-20` | atomic.scatter | 1.46e-05 | 34 | minor | minor | own |
| above | beta | `spread-21` | atomic.scatter | 1.66e-05 | 25 | minor | minor | own |
| above | beta | `spread-16` | atomic.scatter | 2.05e-05 | 25 | minor | minor | own |

Drop share at share 0.000562:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | beta | `spread-34` | atomic.scatter | 0.000501 | 0 | trivial | trivial | own |
| below | beta | `spread-37` | atomic.scatter | 0.000417 | 0 | trivial | trivial | own |
| below | beta | `spread-46` | atomic.scatter | 0.000393 | 25 | minor | minor | own |
| below | beta | `spread-8` | atomic.scatter | 0.000202 | 45 | minor | minor | own |
| below | beta | `spread-24` | atomic.scatter | 7.27e-05 | 66 | major | major | own |
| above | beta | `spread-22` | atomic.scatter | 0.000648 | 0 | trivial | trivial | own |
| above | beta | `spread-40` | atomic.scatter | 0.000919 | 27 | minor | minor | own |
| above | beta | `spread-43` | atomic.scatter | 0.00323 | 7 | trivial | trivial | own |
| above | beta | `spread-45` | atomic.scatter | 0.00361 | 33 | minor | minor | own |
| above | beta | `spread-18` | atomic.scatter | 0.0038 | 8 | trivial | trivial | own |

Rise share at share 0.178:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `land` | atomic.land | 0.1 | 47 | minor | minor | own |
| below | beta | `spread-33` | atomic.scatter | 0.0569 | 95 | campaign_defining | campaign_defining | own |
| below | beta | `spread-4` | atomic.scatter | 0.0462 | 94 | campaign_defining | campaign_defining | own |
| below | beta | `land` | atomic.land | 0.03 | 42 | minor | minor | own |
| below | beta | `spread-7` | atomic.scatter | 0.0227 | 66 | major | major | own |
| above | beta | `spread-27` | atomic.scatter | 0.259 | 26 | minor | minor | own |

Rise 2 levels at share 56.2:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | beta | `spread-27` | atomic.scatter | 0.259 | 26 | minor | minor | own |
| below | alpha | `land` | atomic.land | 0.1 | 47 | minor | minor | own |
| below | beta | `spread-33` | atomic.scatter | 0.0569 | 95 | campaign_defining | campaign_defining | own |
| below | beta | `spread-4` | atomic.scatter | 0.0462 | 94 | campaign_defining | campaign_defining | own |
| below | beta | `land` | atomic.land | 0.03 | 42 | minor | minor | own |

Rise 3 levels at share 1.78e+04:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | beta | `spread-27` | atomic.scatter | 0.259 | 26 | minor | minor | own |
| below | alpha | `land` | atomic.land | 0.1 | 47 | minor | minor | own |
| below | beta | `spread-33` | atomic.scatter | 0.0569 | 95 | campaign_defining | campaign_defining | own |
| below | beta | `spread-4` | atomic.scatter | 0.0462 | 94 | campaign_defining | campaign_defining | own |
| below | beta | `land` | atomic.land | 0.03 | 42 | minor | minor | own |

### organization

Drop share at share 0.000562:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | alpha | `organized` | atomic.other | 0.004 | 58 | major | major | own |

Rise share at share 0.178:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `organized` | atomic.other | 0.004 | 58 | major | major | own |

### hab

No cut-off.

### fleet

No cut-off.

### battle

No cut-off.

### space_loss

No cut-off.

### faction

No cut-off.

### nuclear

No cut-off.

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

Drop 2 levels at share 1.78e-06:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | alpha | `draft:held:deal` | 0.001 | 47 | minor | minor | `land` | no |
| above | alpha | `draft:held:arc` | 0.00398 | 47 | minor | minor | `land` | no |
| above | alpha | `draft:held:grow` | 0.0158 | 64 | major | major | own | yes |

Drop share at share 0.000562:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | alpha | `draft:held:deal` | 0.001 | 47 | minor | minor | `land` | no |
| above | alpha | `draft:held:arc` | 0.00398 | 47 | minor | minor | `land` | no |
| above | alpha | `draft:held:grow` | 0.0158 | 64 | major | major | own | yes |

Rise share at share 0.178:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:held:grow` | 0.0158 | 64 | major | major | own | yes |
| below | alpha | `draft:held:arc` | 0.00398 | 47 | minor | minor | `land` | no |
| below | alpha | `draft:held:deal` | 0.001 | 47 | minor | minor | `land` | no |

Rise 2 levels at share 56.2:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:held:grow` | 0.0158 | 64 | major | major | own | yes |
| below | alpha | `draft:held:arc` | 0.00398 | 47 | minor | minor | `land` | no |
| below | alpha | `draft:held:deal` | 0.001 | 47 | minor | minor | `land` | no |

Rise 3 levels at share 1.78e+04:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:held:grow` | 0.0158 | 64 | major | major | own | yes |
| below | alpha | `draft:held:arc` | 0.00398 | 47 | minor | minor | `land` | no |
| below | alpha | `draft:held:deal` | 0.001 | 47 | minor | minor | `land` | no |

### held on population

Drop 2 levels at share 1.78e-06:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | alpha | `draft:held:arc` | 0.02 | 47 | minor | minor | `land` | no |

Drop share at share 0.000562:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | alpha | `draft:held:arc` | 0.02 | 47 | minor | minor | `land` | no |

Rise share at share 0.178:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:held:arc` | 0.02 | 47 | minor | minor | `land` | no |

Rise 2 levels at share 56.2:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:held:arc` | 0.02 | 47 | minor | minor | `land` | no |

Rise 3 levels at share 1.78e+04:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:held:arc` | 0.02 | 47 | minor | minor | `land` | no |

### moved on population

Drop 2 levels at share 1.78e-06:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | alpha | `draft:moved:deal` | 0.158 | 47 | minor | minor | `land` | no |

Drop share at share 0.000562:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | alpha | `draft:moved:deal` | 0.158 | 47 | minor | minor | `land` | no |

Rise share at share 0.178:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:moved:deal` | 0.158 | 47 | minor | minor | `land` | no |

Rise 2 levels at share 56.2:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:moved:deal` | 0.158 | 47 | minor | minor | `land` | no |

Rise 3 levels at share 1.78e+04:

| Side | Campaign | Event | Share | Score | Level | Own base level | Decided by | Ruled |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | alpha | `draft:moved:deal` | 0.158 | 47 | minor | minor | `land` | no |

## Snippet

```python
# Every scaling, kind's scaling and base level is the code's.
```
