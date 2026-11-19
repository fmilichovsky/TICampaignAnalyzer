# Stake calibration readout

## Calibration state

| Measure | Reference | Code's |
| --- | ---: | ---: |
| power | 0.01 | 0.01 |
| population | 0.01 | 0.01 |
| organization | 0.01 | 0.01 |
| hab | 0.015 | 0.015 |
| fleet | 0.01 | 0.01 |
| battle | 0.0033 | 0.0033 |
| faction | 0.14285714285714285 | 0.14285714285714285 |
| nuclear | 0.01 | 0.01 |

Every event type is at the code's base level.

- Campaigns: beta
- Types: atomic.thing
- Cache key: `golden`
- State: `#campaigns=beta&types=atomic.thing`

## Summary

References: every measure at the code's. Base levels: every type at the code's. Campaigns: beta. Types: atomic.thing. 0 events move level; the narrator package goes from 0 to 0 events at major or above (0); 0 events with members change. What moves: nothing. Drafts: held (#1) at base minor: 0 events, 0 set by a cited event; moved (#2) at base trivial: 0 events, 0 set by a cited event.

## Level counts

| Type | Level | Replay | Baseline | Change |
| --- | --- | --- | --- | --- |
| atomic.thing | minor | 1 | 1 | 0 |
| atomic.thing | major | 2 | 2 | 0 |

## What moves

No event moves.

## Member verdicts

Groups and candidates: none.

Every group keeps its members.

## Cut-offs

### power

Cut-off at share 0.000562 (offset -1.25):

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | beta | `lean` | atomic.thing | 0.00158 | 54 | major | major | own |
| above | beta | `judged` | atomic.thing | 0.0158 | 64 | major | major | own |
| above | beta | `atomic` | atomic.thing | 0.02 | 40 | minor | minor | own |

Cut-off at share 0.178 (offset 1.25):

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | beta | `atomic` | atomic.thing | 0.02 | 40 | minor | minor | own |
| below | beta | `judged` | atomic.thing | 0.0158 | 64 | major | major | own |
| below | beta | `lean` | atomic.thing | 0.00158 | 54 | major | major | own |

### population

Cut-off at share 0.000562 (offset -1.25):

No event has this stake.

Cut-off at share 0.178 (offset 1.25):

No event has this stake.

### organization

Cut-off at share 0.000562 (offset -1.25):

No event has this stake.

Cut-off at share 0.178 (offset 1.25):

No event has this stake.

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

Cut-off at share 0.00803 (offset -1.25):

No event has this stake.

Cut-off at share 2.54 (offset 1.25):

No event has this stake.

### nuclear

Cut-off at share 0.000562 (offset -1.25):

No event has this stake.

Cut-off at share 0.178 (offset 1.25):

No event has this stake.

## Draft stakes

| Draft | Label | Issue | Measures | Base | Own base | Events | Ruled | Set by a cited event |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| held | Held share | #1 | power, population | minor | minor | 0 | 0 | 0 |
| moved | Moved share | #2 | population | trivial | trivial | 0 | 0 | 0 |

Level counts at each draft's base, against its own:

No draft rows.

### held on power

Cut-off at share 0.000562 (offset -1.25):

No row of this draft has this stake.

Cut-off at share 0.178 (offset 1.25):

No row of this draft has this stake.

### held on population

Cut-off at share 0.000562 (offset -1.25):

No row of this draft has this stake.

Cut-off at share 0.178 (offset 1.25):

No row of this draft has this stake.

### moved on population

Cut-off at share 0.000562 (offset -1.25):

No row of this draft has this stake.

Cut-off at share 0.178 (offset 1.25):

No row of this draft has this stake.

## Snippet

```python
# Every reference and base level is the code's.
```
