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
What an event's score scales with: the share of a world total (its stake measure) held or moved by the entities the
event concerns, in the same snapshot.
_Avoid_: magnitude, size, weight

**Stake measure**:
The world total a stake is a share of, such as nation power, population or organization strength.
_Avoid_: metric (a nation metric is a statistic, not a stake measure)

**Reference**:
The share of a stake measure at which a stake leaves an event's score at its base level; each tenfold share above or
below it moves the score ten points.
_Avoid_: reference value, baseline, target share

**Reference window**:
The shares a reference lets keep a minor or major base level, from the reference ÷ 17.8 to × 17.8; a reference
slides the window along the shares and never changes its width.
_Avoid_: band (a band is a level's score range)

**Nuclear share**:
The warheads a nuclear arc built or dismantled, net, as a share of the world's warheads: the larger world total of
the arc's two ends, so a share never exceeds one.
_Avoid_: arsenal share (an arsenal can mean every military asset), arsenal size

**Space share**:
A faction's share of human space holdings: the mean of its share of human habs, weighted by tier squared, and its
share of human ship dry mass. Each total has a floor, so a share stays defined before humans hold anything there.

**Saturation**:
The human space holdings at which space counts fully in a faction stake; below it, space counts in proportion.
_Avoid_: floor (the floor only keeps a share defined; it is far smaller for habs)

**Faction stake**:
A human faction's weight in the world: its Earth share (each nation's power share times the faction's share of that
nation's control points), blended with its space share in proportion to how far humans have reached the
saturation. The alien faction is the backdrop: its stake is its Earth share alone.
_Avoid_: faction power, faction strength

**Contested mass**:
How much of a combat was really fought: the smaller side's dry mass plus the larger side's, capped at a multiple of
the smaller one, with alien ships weighted up. A large fleet swatting a scout contests little; the outcome never
changes it.
_Avoid_: battle size, fleet size

**Dry mass**:
A ship's mass without its propellant; the save's current mass includes propellant, which swings with refuelling.

### Narration

**Narrator package**:
The campaign history as handed to a language model or a reader who wants facts without prose: narrative events,
the evidence they cite and the campaign's context.
_Avoid_: export, events JSON

**Chapter**:
A run of whole periods of the narrator package, small enough to be told in one model request.
_Avoid_: section (a section is one period inside a chapter), part

**Narrative weight**:
How much narrative a chapter is compelled to cover: its top-level narrative events, each counted by significance,
with trivial ones counting nothing. Members and developments continuing from an earlier chapter add none. Every
length a chapter is asked for scales with it.
_Avoid_: event count, chapter size (size is the request's tokens)

**Councilor article**:
A neutral, public-perception piece about one notable councilor, told from its councilor brief in one model
request.
_Avoid_: profile, biography

**Councilor brief**:
The model-facing rendering of the councilor dossier's header and one entry, embedded in the article request. The
only layer that omits, rewords or bands what the dossier holds; it is not a file of its own.
_Avoid_: summary, prompt data

**Stance**:
The public outlook a councilor brief gives in place of a faction, such as accommodationist for the Protectorate.
The councilor prompt explains each stance; no faction name reaches an article request.
_Avoid_: faction, ideology label

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
