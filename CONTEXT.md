# Terra Invicta campaign history

Reconstructs a readable campaign history from Terra Invicta saves, keeping what the saves prove apart from what
the analyzer infers.

## Language

### Campaigns and saves

**Survey**:
The quick first read of a save that gives its game time and campaign identity, without analysing it.
_Avoid_: scan, probe

**Skipped save**:
A file inside a given directory that is not a usable save; it is reported and never fails the run. A save the
user named directly that is unusable fails the run instead.
_Avoid_: ignored file, bad save

**Campaign**:
The saves of one playthrough, inferred from their shared campaign identity because the format carries no
campaign ID.
_Avoid_: group (how a campaign is formed, not what it is), game

**Campaign selector**:
What the user gives to choose one campaign among several: its key, its name, or `latest`.
_Avoid_: campaign filter

**Interval**:
The span between two consecutive saves of a campaign, analysed as one unit and keyed by its later save.
_Avoid_: pair, step

**Situation report**:
The state of the world at one save, summarised for narrative rules and the narrator.
_Avoid_: snapshot (the parsed save beneath it), world state

**Campaign analysis**:
One campaign's saves analysed in game-time order: its intervals, their events and, when asked for, its narrative
events.
_Avoid_: session, run (a run is one command invocation), sequence

### Events

**Atomic event**:
The smallest meaningful unit of campaign history: one transition between two saves, one save-carried record
entry, or one tightly reconstructed action.
_Avoid_: change (a change is the literal diff beneath an event), raw event, inferred event (inferred is a status
any event can have, not a tier between atomic and narrative)

**Narrative event**:
A higher-level event that groups related atomic events into one episode a reader recognises, such as a
takeover or a war's arc.
_Avoid_: aggregate, summary event, development

**Constituent**:
An event a narrative event cites as part of what it tells: an atomic event, or a smaller narrative event. A
narrative event that includes a smaller one cites it whole, never that one's own constituents.
_Avoid_: member (a member is one particular constituent), child, part

**Exclusive constituent**:
A constituent no narrative event of another kind may cite, because the citing event's kind declares what it cites
as its own, as a merger's kind does. Events of the same kind may share it: one territory gain with several
counterparts belongs to each cession.
_Avoid_: carried event, claimed event, consumed event, absorbed event (an absorbed nation is what a merger takes
in)

**Member**:
A narrative event that a larger one groups, as a takeover wave groups takeovers, because the larger event's kind
declares it. When nothing else cites it, the narrator package tells it only inside the larger event, as a digest.
_Avoid_: child, sub-event, wave member ("wave" is part of some event type names, not a term of its own)

**Explained event**:
An event that is not reported as a narrative event of its own because another event already accounts for it,
without citing it: a nation's unrest crossing a band in the interval of its takeover, or a territory gain that an
annexation reading covers.
_Avoid_: carried event, absorbed event, consumed event (the event that explains it is read, never consumed)

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

### Narration

**Narrator package**:
The campaign history as handed to a language model or a reader who wants facts without prose: narrative events,
the evidence they cite and the campaign's context.
_Avoid_: export, events JSON

**Chapter**:
A run of whole periods of the narrator package, small enough to be told in one model request.
_Avoid_: section (a section is one period inside a chapter), part

**Councilor article**:
A neutral, public-perception piece about one notable councilor, told from the councilor dossier in one model
request.
_Avoid_: profile, biography

**Run directory**:
The folder a narration writes and later reads back: its plan or dossier, one request per chapter or article, one
response record per completed one, and the assembled document with its manifest.
_Avoid_: output directory, DIR

**Response record**:
The stored answer to one request, together with the settings it was sent with.
_Avoid_: response file, completion

**Kept response**:
A response record reused by a later run because its request and the settings it was sent with are unchanged.
_Avoid_: cached response, stored response
