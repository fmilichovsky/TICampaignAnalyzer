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

- Campaigns: beta
- Types: atomic.thing
- Cache key: `golden`
- State: `#campaigns=beta&types=atomic.thing`

## Summary

Scalings: every scaling at the code's. Kinds: every type on its code scaling. Base levels: every type at the code's. Campaigns: beta. Types: atomic.thing. 0 events move level; the narrator package goes from 0 to 0 events at major or above (0); 0 events with members change. What moves: nothing. Drafts: held (#1) at base minor: 0 events, 0 set by a cited event; moved (#2) at base trivial: 0 events, 0 set by a cited event.

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

Drop share at share 0.000562:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| above | beta | `lean` | atomic.thing | 0.00158 | 54 | major | major | own |
| above | beta | `judged` | atomic.thing | 0.0158 | 64 | major | major | own |
| above | beta | `atomic` | atomic.thing | 0.02 | 40 | minor | minor | own |

Rise share at share 0.178:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | beta | `atomic` | atomic.thing | 0.02 | 40 | minor | minor | own |
| below | beta | `judged` | atomic.thing | 0.0158 | 64 | major | major | own |
| below | beta | `lean` | atomic.thing | 0.00158 | 54 | major | major | own |

Rise 2 levels at share 56.2:

| Side | Campaign | Event | Type | Share | Score | Level | Code level | Decided by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| below | beta | `atomic` | atomic.thing | 0.02 | 40 | minor | minor | own |
| below | beta | `judged` | atomic.thing | 0.0158 | 64 | major | major | own |
| below | beta | `lean` | atomic.thing | 0.00158 | 54 | major | major | own |

### population

No cut-off.

### organization

No cut-off.

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
| held | Held share | #1 | power, population | minor | minor | 0 | 0 | 0 |
| moved | Moved share | #2 | population | trivial | trivial | 0 | 0 | 0 |

Level counts at each draft's base, against its own:

No draft rows.

### held on power

Drop share at share 0.000562:

No row of this draft has this share.

Rise share at share 0.178:

No row of this draft has this share.

Rise 2 levels at share 56.2:

No row of this draft has this share.

### held on population

No cut-off.

### moved on population

No cut-off.

## Snippet

```python
# Every scaling, kind's scaling and base level is the code's.
```
