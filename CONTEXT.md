# Terra Invicta campaign history

Reconstructs a readable campaign history from Terra Invicta saves, keeping what the saves prove apart from what
the analyzer infers.

## Language

### Events

**Atomic event**:
The smallest meaningful unit of campaign history: one transition between two saves, one save-carried record
entry, or one tightly reconstructed action.
_Avoid_: change (a change is the literal diff beneath an event), raw event

**Narrative event**:
A higher-level event that groups related atomic events into one development a reader recognises, such as a
takeover or a war's arc.
_Avoid_: aggregate, summary event

**Event type**:
The stable identifier of what kind of thing an event records, such as `nation.annexation`; it appears in reports
and in the narrator package.
_Avoid_: event kind (that is the declaration, not the identifier)

**Event kind**:
The single declaration of one event type: its identifier, how an event of it is told, how much it matters, whether
the narrator treats it as evidence, and the attributes it carries.
_Avoid_: event type (that is only the identifier), template, event definition

### Significance

**Significance**:
How much an event matters to a campaign history, as a 0-100 score and the level whose band holds it; independent
of confidence.
_Avoid_: importance, priority, weight

**Base level**:
The significance an event kind starts from before any stake moves it; every atomic event kind declares one.
_Avoid_: default level

**Context rule**:
A named judgement that sets an event's level from what the event itself says, overriding its base level.
_Avoid_: override, special case

**Stake**:
What an event's score scales with: the share of a world total (its stake measure) held by the entities the event
concerns, in the same snapshot.
_Avoid_: magnitude, size, weight

**Stake measure**:
The world total a stake is a share of, such as nation power, population or organization strength.
_Avoid_: metric (a nation metric is a statistic, not a stake measure)
