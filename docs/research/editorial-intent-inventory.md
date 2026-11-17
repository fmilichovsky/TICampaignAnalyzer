# Editorial intent: where the repo says what the campaign history emphasizes

Research note for the agent calibration framework map (#531), answering #535. It is not a decision record. Sources
are this repository at `main` `0d7e85d` and the issues and PRs named; line numbers point at that commit. Issue and PR
bodies are cited by number. Nothing here is drawn from private saves or untracked samples.

Each statement is sorted into one of three classes:

- **Direction (D):** what the history is for, or what it emphasizes or plays down.
- **Implementation detail (I):** how a direction is carried out; it could change without changing the intent.
- **Reactive rule (R):** steers the narrator towards or away from a particular phrase or structure, usually in answer
  to a failure a trial produced.

## Summary

- **No document states the editorial direction.** It is spread over the README, two prompts, ADR-0011, the
  `Significance` docstrings, one module docstring (`milestones.py`) and about ten code comments. The largest single
  body of editorial judgement, the 168 event kinds' base levels, carries almost no stated reason.
- **The direction the statements add up to:** a readable alternate history of the world, told as a well-informed
  public saw it, by a historian looking back. It is led by what moved the largest share of the world (large nations,
  wars, firsts, nuclear use, turning-point technology), groups or drops routine churn, tells an arc once, keeps
  space and politics in one story, and keeps the package's certainty without ever talking about its evidence. The
  deterministic half decides what matters, by impact only; perspective (the player's faction, the audience) is left
  to the narrator.
- **About two thirds of the narrator prompt is field-reading and reactive rules;** its direction is about 25 lines
  (`prompt.md:1-13`, `225-238`, `286-301`). `docs/narrator.md:47-55` says so itself: the rules "each answer a
  failure a trial produced".
- **Seven contradictions** are listed below. The sharpest: the level docstrings and the package disagree on whether
  `minor` is history; several `major` and `campaign_defining` atomic kinds can never reach the narrator package; the
  prompt re-judges weight that ADR-0011 says is judged once; and the player's faction has no home before the
  narrator although the map judges the package only.
- **Gaps:** no stated purpose in one place, no themes or priority among them, no episode density, no direction for
  alien activity on Earth, councilors or the player's perspective inside the package, and no reasons for most base
  levels.

## Inventory

### README and CONTEXT.md

| Where | Statement | Class |
| --- | --- | --- |
| `README.md:3-7` | A "readable campaign history"; the deterministic half builds a "filtered, ranked and partially interpreted package"; the LLM ties events together and shows "how the general public would realistically perceive the events". | D |
| `CONTEXT.md:3-4` | Keeps what the saves prove apart from what the analyzer infers. | D (evidence, not emphasis) |
| `CONTEXT.md:49-52` | A narrative event is "one episode a reader recognises, such as a takeover or a war's arc". | D |
| `CONTEXT.md:91-93` | Significance is "how much an event matters to a campaign history", independent of confidence. | D |
| `CONTEXT.md:147-150` | "The alien faction is the backdrop": its faction stake is its Earth share alone. | D |
| `CONTEXT.md:153-156` | Contested mass: "a large fleet swatting a scout contests little; the outcome never changes it". | D |
| `CONTEXT.md:173-176` | Narrative weight: top-level narrative events counted by significance, "trivial ones counting nothing"; members and continuing events add none. | D, with I (the counting) |
| `CONTEXT.md:179-192` | A councilor article is "neutral, public-perception"; a stance replaces the faction, and no faction name reaches an article request. | D |

### CONTRIBUTING.md

CONTRIBUTING.md holds no statement of emphasis. Two lines bear on where intent may live:

| Where | Statement | Class |
| --- | --- | --- |
| `CONTRIBUTING.md:13-14` | Evidence and inference never merge; every event keeps provenance. | D (evidence) |
| `CONTRIBUTING.md:32-37`, `52-55` | Each fact has one home; decisions live in ADRs; the system prompts exist once, in the package. | I (governs where an editorial stance could be written) |

### ADRs

| Where | Statement | Class |
| --- | --- | --- |
| `0003:18-19` | Rendering never rediscovers what happened; prose is never the authoritative source of a fact. | D |
| `0004:6-12`, `21-22` | Status, level, confidence and significance are independent: "a certain objective event can be trivial". | D |
| `0009:3-5` | Aggregation builds "the narrative events a history reports": a takeover and its consolidation, a war from declaration to peace, a federation's life. | D |
| `0009:7-9`, `29-30` | Anchors decide existence; grouping by proximity was rejected because nobody can explain its groups. | D (what may count as an episode) |
| `0009:18` | A narrative event's significance is never below its most significant constituent. | I |
| `0010:18`, `24` | A ledger event is `minor`, corroboration only; ledger-only narrative events are capped at medium confidence. | D for the level, I for the bounds |
| `0011:3-4` | "Not every state change belongs in a campaign history"; a reader can ask for "anything from a concise summary to a forensic log"; significance "measures impact, not certainty". | D |
| `0011:6-8` | One place judges impact; no threshold is tuned to one campaign. | D |
| `0011:9-11` | Evidence events and routine churn are `trivial`; leftover relation lists stay `minor` "so the unexplained residue is never hidden". | D |
| `0011:14-20` | A stake is a share, never a magnitude, so early and late events stay comparable; "only the types whose impact grows with the stake are scaled; movement and churn never are". | D, with I (log scale, clamp) |
| `0011:21-26` | Space totals count humans only, so the aliens are not "half the world from the start". | D, with I (floor, saturation) |
| `0011:27-28` | "A large fleet swatting a scout is a skirmish. The outcome never changes the stake." | D |
| `0011:29-33` | A nuclear arc scales by warheads moved; "a great power's token buildup does not inherit the power share". | D |
| `0011:34-36` | The maximum, never a sum: a sum "would rank events by how often they were recorded". | D |
| `0011:37` | "Perspective is not impact. The player's faction stays a concern of the narrator." | D |
| `0014:12-18` | The model orders and phrases; it may not merge narrative events the rules kept apart or supply a fact; motive and public framing are worded as interpretation and never become a premise. | D |
| `0014:15-16` | The citation audit lists uncited major events; it reports and never rejects prose. | I |
| `0014:32-33` | Letting the model group events into episodes was rejected: "grouping is a factual judgement". | D |
| `0015:19-20` | Narrative events are never dropped, and the significance cut is never raised behind the user's back. | D |
| `0018:7-9`, `22-23` | Sealed prose never changes under the reader. | D (about stability, not emphasis) |
| `0020:10-12`, `21-22` | What must never appear in an article is removed before the model sees it, not forbidden in the prompt: "a model quotes what it is shown". | D (a method for carrying intent) |
| `0021:7-8`, `18-19` | Every length scales with narrative weight; left alone, a model condenses and quotes the package. | D, with I (budgets) |

ADRs 0001, 0002, 0005 to 0008, 0012, 0013, 0016, 0017 and 0019 state nothing about emphasis.

### The history prompt (`src/tinarrative/narrator/prompt.md`)

| Lines | Statement | Class |
| --- | --- | --- |
| `1-6` | Write as "a historian or long-form journalist would, looking back: what happened, how the world experienced it, and what it meant"; "an alternate history, not a report on a data set". | D |
| `8-13` | The public never sees a faction act; it sees governments change course, economies lurch, wars start, consortia build stations. "Write from that vantage point unless the request says otherwise." | D |
| `19-30` | Request defaults: `public` audience, `chronicle` style, length "proportional to how much happened", focus on the player faction for an `insider` account only. | D for audience and focus, I for the rest |
| `36-82` | What each package member is and how to use the glossary and continuity. | I, with R at `68-73` (never print a key; leave an `event_*` label out) and `79-82` (no seats of government; never mention audit counts) |
| `62-64` | "Snapshots are background, not events"; the last snapshot's counts are where things stood. | D |
| `84-187` | How to read the fields: dates, `open`, causes, metric shifts, bands, each family's attributes, counts from the actor's side, what a control point, a region change or a completed technology is not. | I for the semantics; R for every "never", "not by itself" and worked example (`86-92`, `107-110`, `153-155`, `166-174`, `177-187`) |
| `103-104` | "Say what they mean ... and quote the number only when the number itself is the story." | D |
| `190-221` | Facts: the package is the only source; keep its certainty; no backstory before the first save. | D at `190-191` and `198-201` (certainty carried in the prose); R for the banned phrases at `202-206` and `218-220` and the derivation bans at `207-212` |
| `225-238` | "Everything else is yours, and it is what makes the history readable": presentation, reception, what a change enabled or foreclosed, what an actor may have wanted. Interpretation stays recognisable and general; briefs are background, never evidence. | D |
| `242-274` | Faction briefs: what each network wants and how it shows in public. | D (the public faces the history may use), I as content |
| `278-285` | One section per period; placement by start; chapter parts. | I |
| `286-294` | "Decide first what the period was about." Lead with the two or three developments that changed the most ("`campaign_defining` and `major` weight, large nations, wars, the player faction's fortunes") and give them room. "Group the rest: a run of small-state turnovers is one paragraph." "Leave out churn." Tell a long development once. "Space developments belong in the same story as the political ones; do not silo them." | D (the densest block in the repo) |
| `296-301` | Voice: concrete, sober, each section opened differently; no statistic lists, no control-point arithmetic, no "(record date)" asides; prefer "a new administration aligned with the Protectorate took office" to "gained the executive control point"; vary hedges. | D for the register at `296-297`, R for the rest |
| `303-314` | Citations; a closing section only for a `whole` or `last` part, with no prediction. | I, with R (no closing or summary paragraph in a `first` or `middle` part) |
| `316-322` | Final reread for five failures. | R |

### The councilor prompt (`src/tinarrative/narrator/councilor_prompt.md`)

| Lines | Statement | Class |
| --- | --- | --- |
| `1-6` | The article "a neutral reference work would carry": "an encyclopedia entry on a public figure, not ... a report on a data set and not ... an intelligence file". | D |
| `8-17` | The seven sides are "currents of opinion", a label the press attaches; write what a well-informed public would know "and no more": some are household names, others barely known. | D |
| `28-131` | How to read each field. | I, with R at `40-42` (pronouns), `48-52` (never a list of labels), `68-70` (covert skills as a professional background), `100-104` (one role, no "or"), `121-127` (never say that none are recorded) |
| `75-92` | Visibility frames the whole article: celebrity, private person, near-rumor; "guardedness is about how it is known, never invented secrets". | D |
| `105-109` | Name only the significant organizations, three or four; fold the rest into their kinds. | D (emphasis inside an article) |
| `135-154` | Facts: the dossier is the only source; public perception only, never loyalty or secret motives; banned words; never refer to the dossier. | D at `145-147`, R for `148-154` |
| `158-181` | Stance briefs. | D as public faces, I as content |
| `185-224` | Shape: lead with the single thing the person is best known for; four sections, each subject told once; `Controversy` reads across the others. | D for the lead and `Controversy`, I for the section order |
| `226-246` | One home per subject; neutral register "with neither praise nor blame"; "a thin dossier gives a shorter article, never padding"; final reread. | D for the register and length, R for the rest |

### `docs/narrator.md`

| Lines | Statement | Class |
| --- | --- | --- |
| `5-9` | The prompt fixes "a short floor of facts" and leaves everything above it to the model; "the result should read as history, not as a report on the package". | D |
| `14-18` | The package's atomic events are only narrator evidence: constituents that state a fact the narrative event does not carry; bookkeeping is left out. | D (what reaches the narrator), I for the flags |
| `25-27` | "`major` is the practical level for a whole campaign; `minor` adds narrative events such as fleet buildups and technology milestones." | D |
| `42-45` | Faction briefs leave out leaders, endgames and story spoilers on purpose. | D |
| `47-55` | The rules in "How to read the fields" and "Facts" each answer a trial failure. "Keep it short: a longer rulebook did not buy accuracy ..., it only made the prose talk about the rules. Prefer to sharpen an existing line or the final reread list over adding a paragraph." | D about the prompt itself; it labels the rest as R |
| `64-86` | The councilor prompt's rules "answer the brief's shape"; the faction reaches the model only as a stance; visibility frames the article. | D, restating the prompt |

### Event kinds: base levels and context rules

The base levels are the largest body of editorial judgement in the repo and the least explained. There are 168 kinds
(`src/tinarrative/kinds/registry.py:36`): 135 atomic and 33 narrative.

| Base level | Atomic | Narrative |
| --- | --- | --- |
| `campaign_defining` | 5 | 1 |
| `major` | 30 | 20 |
| `minor` | 77 | 9 |
| `trivial` | 23 | 3 |

What the levels mean is stated once, in `src/tinarrative/model/events.py:42-49`:

- `trivial`: "routine churn or bookkeeping that no history level shows". **D**
- `minor`: "worth a forensic log line, not a history entry; the default for an unclassified type". **D**
- `major`: "a narrative event a normal campaign history reports". **D**
- `campaign_defining`: "a narrative event even a concise summary keeps". **D**

Stated reasons for a base level, in full:

| Where | Statement | Class |
| --- | --- | --- |
| `kinds/campaign.py:133` | "Campaign-wide firsts, nuclear use and climate stages are what a history reports" (three atomic kinds at `campaign_defining`, lines `135-156`). | D |
| `kinds/campaign.py:162` | A game narrative event is "a once-per-campaign narrative event" (`major`). | D |
| `kinds/faction.py:19-20` | A ledger charge is corroboration, "never a narrative event on its own". | D |
| `kinds/nations.py:559` | Release, breakaway and claims are `trivial` as narrative kinds: "the independence or claims change they cite sets their level". | I |
| `kinds/technology.py:112` | The milestone's `minor` base is only a fallback; the curated tier sets the level. | I |
| `kinds/space.py:414` | A battle outcome is not scaled until combat attribution is settled (`TODO(#303)`). | I |
| `kinds/aliens.py:3` | No alien-presence kind is narrator evidence: "no narrative event cites them yet". | I (records a gap) |
| `model/kinds.py:85-91` | Evidence role: an event is evidence when it states a fact its narrative event does not carry; bookkeeping is already summed up. | D |

Every other base level is a bare `base=Significance.X` argument. The direction can only be read back from the
pattern:

- **`campaign_defining`:** a nation appearing or disappearing, a global first, nuclear strikes, a sea-level stage.
- **`major` narrative kinds:** takeover and takeover wave, war arc, federation lifecycle, expansion, cession,
  merger, military buildup and demobilization, first navy, nuclear arcs, population collapse, economic trajectory,
  diplomatic realignment, world ranking change, first space defences, space campaign, colonisation wave.
- **`minor` narrative kinds:** the six band shifts, space program growth, fleet buildup, technology milestone (each
  but fleet buildup with a context rule that can raise it).
- **`trivial`:** list bookkeeping, recruit-pool and organization churn, statistic shifts, band crossings, rank
  changes.

Context rules (`src/tinarrative/narrative/significance.py`):

| Lines | Statement | Class |
| --- | --- | --- |
| `1` | The module decides "which events a campaign history keeps and which are routine churn". | D |
| `4-5` | "Notification templates are never ranked: the game's own log is player-centric and open-ended." | D |
| `78-82` | Coup, regime change, independence and enthrallment "replace a government outside normal politics" (major); allies and rivals are "routine diplomacy" (minor), a war is major. | D |
| `140-156` | "Recruit-pool churn is trivial; a councilor with a faction that is gone is a narrative event" (major). | D |
| `168-170` | A population drop beyond territory is major, "since routine decline is far slower"; growth is minor. | D |
| `173-177` | A nation's first space defences are major, "they appear only late". | D |
| `180-182` | "Megafauna are rare, so their presence is major; regular army presence is routine." | D |
| `185-188` | "An unlisted completion is minor: many technologies and projects are routine unlocks." | D |
| `191-199` | The alien administration's claims are minor because they cover every region implicitly; a human nation's are major. | D |
| `202-222`, `analyzers/politics/bands.py:103-108` | Band shifts: democracy, education and military technology are always major; unrest into Insurgency, a cohesion extreme or two bands crossed is major. | D, unreasoned (no line says why these three statistics) |
| `225-230` | A population collapse after nuclear strikes is campaign defining. | D |
| `235-237` | Entering the top of a space measure is major. | D |
| `84-114` | Top-N promotion by GDP or strength, marked temporary (`TODO(#362)`). | I |

Other code that carries intent:

| Where | Statement | Class |
| --- | --- | --- |
| `narrative/milestones.py:1-6` | The curated list is "interpretation": each entry weighs how much of the tree it opens, "how much the concept means in the real world" and how concrete it is; "a named capability ranks above a vague stepping stone". Tiers at `40-57` (the two energy peaks and the seven faction endgames are campaign defining). | D. The only place that states criteria for a tier list. |
| `narrative/measures.py:35-79` | References: 1% of the world for most measures, an even seventh for a faction, 0.33% for a battle. | I (#537 covers their reasons) |
| `narrator/chapters.py:24-27` | Narrative weights 0, 1, 2, 4 by level; six words per point; recall from `major`. | I for the numbers; D for "trivial narrative events add detail, never length" |
| `narrator/assembly.py:21` | The citation audit expects every `major` event to be cited. | I |
| `config.py:66-75` | A takeover wave needs three nations, each taken by a takeover below `campaign_defining`. | I, carrying D (small takeovers are told as one episode; a defining one stands alone; also `CONTEXT.md:66-70`) |
| `config.py:187-189` | Situation reports keep the ten largest economies beyond the nations a chapter references. | I, carrying D (large economies are always context) |
| `config.py:220-228` | Councilors: a year's tenure; the player's councilors plus the most prominent of each other faction. | D (the one place the player's perspective enters selection) |
| `docs/commands/narrate.md:51-58` | Defaults: `major`, `public`; "insider centres on the player faction". | D |

### Closed issues and PRs

| Number | Statement | Class |
| --- | --- | --- |
| #70, PR #82 | Significance exists "so the narrative stages can drop routine churn"; first per-type levels, with counts as evidence; no threshold tuned to one campaign. | D |
| #101, #102 | The first catalogue: geopolitical rules first, space "secondary to #101 but cheap". | D (historic priority) |
| #104 | Target prose "geopolitics first, space milestones second"; "audit matters more than style here". | D (historic) |
| PR #120 | Milestone tiers by reach, real-world weight and concreteness; routine techs "leave the major history". | D |
| PR #123, #124 to #132 | Trial failures turned into package fixes and prompt lines. | R |
| #130 | Narrative events and the atomic stream get separate cut-offs, so `minor` narrative events can be told without the `minor` atomic stream. | D |
| #132 | Briefs stated as fact, factions named in public accounts, sentences about the record, game keys read as content. | R |
| PR #138 | The rewrite: a 2,900-word rulebook produced "an audit report rather than a history", with "every one-region takeover given the same weight as the United States changing hands". Genre, one footnote per entry, a softened public and insider split, three interpretation limits. | D, and the origin of most R |
| #144 | The less the package carries, the more narrative the model can chain; demote churn. | D |
| #163, #166 | A small state's turnover must not rank with a great power's; "a two-point nuclear state's government is never a footnote"; a wave keeps small takeovers visible at `major` as one entry. | D |
| #190 | A statistic shift is "the evidence other rules cite, not a development in itself". | D |
| PR #202, #196 to #200, #359, #360 | A coup in a micro-state should not rank with one in a leading power, nor a two-ship skirmish with a fleet action; aliens as backdrop. Recorded in ADR-0011. | D |
| #222, PR #244, #284 | Councilor articles are independent of the main narrative, "wikipedia-like"; made "less restricted, more inventive", with speculation on motives; visibility frames them. | D |
| #395, #396 | Remove what must not appear before the model sees it; one home per subject. | D (method), R (section rules) |
| #418 | Larger chapters come back shorter and quote the package; length must follow narrative weight. Recorded in ADR-0021. | D |

Open issues that state intent not yet in the repo: #201 (the prompt should lead by score, not judge weight itself),
#239 (one large body should count as a colonisation), #304 (the alien administration's founding should be a massive
shock), #315 (which prompt parts are per-type facts and which are editorial), #343 (plurality-influence campaigns as
episodes), #488 (a one-sided war against a defenceless nation should not be campaign defining).

## The direction they add up to

1. **Purpose.** A readable history of one campaign's world, an alternate history and not a report: what happened,
   how the world experienced it and what it meant (`README.md:3-7`, `prompt.md:1-6`).
2. **Vantage.** The well-informed public, looking back. Factions are clandestine and show only as the alignment of
   governments and consortia; councilors are public figures placed by stance (`prompt.md:8-13`,
   `councilor_prompt.md:8-17`). An `insider` account with the player's faction as protagonist is an option, never
   the default (`prompt.md:20-30`).
3. **What leads.** What changed the largest share of the world: large nations, wars, nation births and deaths,
   firsts, nuclear use, turning-point technology (`prompt.md:286-289`, `0011:14-20`, `kinds/campaign.py:133`,
   `milestones.py:1-6`).
4. **What is played down.** Routine churn, evidence events, small states one by one, one-sided fights, token
   moves by great powers, duplicate records (`0011:9-11`, `27-36`, `prompt.md:290-291`, #166).
5. **Episodes over events.** The unit is the narrative event a reader recognises, built by anchored rules, told
   once where it begins (`CONTEXT.md:49-52`, `0009:3-9`, `prompt.md:291-293`).
6. **One story.** Space and politics are not siloed; the aliens are the backdrop of the scale, not half of it
   (`prompt.md:293-294`, `0011:21-26`).
7. **Impact only, judged once.** Significance is impact, independent of certainty and of perspective, comparable
   across the campaign (`0011:3-8`, `37`, `0004:21-22`).
8. **Certainty in the prose, never beside it.** The history keeps the package's certainty and never refers to its
   own evidence; interpretation is free above the fact floor and stays recognisable (`prompt.md:198-206`,
   `225-234`, `0014:17-18`).
9. **Length follows what happened** (`0021:7-8`, `chapters.py:24-27`).

## Contradictions

1. **Is `minor` history?** The level docstring says `minor` is "worth a forensic log line, not a history entry"
   (`model/events.py:44-45`). But nine narrative kinds have a `minor` base, `docs/narrator.md:25-27` offers `minor`
   as a level to narrate at, and a `minor` narrative event adds a point of narrative weight, so it is asked for in
   words (`chapters.py:25`, `CONTEXT.md:173-176`). The same docstring calls `minor` "the default for an unclassified
   type", while every kind must now declare a base (`model/kinds.py:111`).
2. **Levels the package cannot honour.** `major` means "a normal campaign history reports" it, but the package lists
   an atomic event only as a constituent of a listed narrative event (`docs/narrator.md:14-18`). Alien crashdowns,
   landings and facilities (`major`, `kinds/aliens.py:24-45`), a sea-level stage (`campaign_defining`,
   `kinds/campaign.py:156`) and a game narrative event (`major`, `kinds/campaign.py:164`) are cited by no narrative
   rule, so they never reach the narrator at any cut-off. For the last one the prompt goes further and says to
   "leave the event out" (`prompt.md:71-73`). PR #123 added "a brief mention of stand-alone `major` atomic events"
   to the prompt; the current prompt has no such line.
3. **Impact judged once, then again.** ADR-0011 says one place judges impact (`0011:6-8`). The prompt then tells the
   model to decide what leads by "`campaign_defining` and `major` weight, large nations, wars, the player faction's
   fortunes" (`prompt.md:286-289`): large nations and wars are what stakes already scale, restated as a second,
   unscored judgement. #201 (open) proposes that the prompt read the score instead.
4. **The player's faction.** ADR-0011 keeps perspective out of significance (`0011:37`). The prompt makes the player
   faction's fortunes a lead criterion for every audience (`prompt.md:288-289`), while the default audience is
   `public`, where a faction is "never ... the subject of an action" (`prompt.md:20-24`) and the focus default
   applies to `insider` only (`prompt.md:29-30`). So the default history is asked to lead with fortunes it may not
   name an owner for. The map (#531) judges the package alone, where the player's perspective is absent by decision.
5. **Group and drop, or never merge and never drop.** The prompt says "group the rest" and "leave out churn"
   (`prompt.md:290-291`). ADR-0014 forbids the model to "merge narrative events that the rules kept apart"
   (`0014:13`) and the audit reports every uncited `major` event (`0014:15`, `assembly.py:21`); ADR-0015 never drops
   a narrative event (`0015:19-20`). Read strictly, churn at `major` is a calibration fault the prompt asks the
   narrator to absorb.
6. **Two publics.** In the history the public knows factions by name as alignments ("aligned with the Protectorate",
   `prompt.md:21-23`, `298-300`). In a councilor article no faction name exists; the public knows only stances
   (`councilor_prompt.md:8-17`, `0020:10-12`, #395). The two documents of one campaign describe different public
   knowledge.
7. **Stale or self-inconsistent statements.**
   - `prompt.md:227-228` announces "three limits" and lists two; PR #138 describes the third (explanatory, not
     supplementary), which is gone.
   - `docs/narrator.md:70-71` describes the councilor article as "a lead, then background, career and public
     profile"; the prompt's sections are Background, Interests and advocacy, Public life and Controversy
     (`councilor_prompt.md:197-224`, #396).
   - PR #138 softened the public and insider split ("front attribution is encouraged rather than enforced"); the
     current prompt enforces it and rereads for it (`prompt.md:20-24`, `320-321`), following #132.
   - #104 and #102 put geopolitics first and space second; the prompt says not to silo space (`prompt.md:293-294`)
     and the faction stake weighs space up to half (`config.py:154-156`). No document records the change.
   - PR #244 made councilor articles "more inventive" with speculation on motives; the prompt now bans "secret
     motives" (`councilor_prompt.md:145-147`) yet asks for "a plausible reason for the stance" (`203-204`) and a
     `Controversy` section inside a register of "neither praise nor blame" (`220-224`, `237`).

## Gaps

- **No single statement of purpose.** The nearest are `README.md:3-7` and `prompt.md:1-6`, and only the model reads
  the second. CONTRIBUTING.md's "each fact has one home" (`32`) has no home for editorial direction.
- **No themes and no priority among them.** Nothing says how geopolitics, space, technology, the aliens, economics
  and councilors should balance, or what a period "was about"; `prompt.md:286` leaves that to the model.
- **No density.** Nothing states how many episodes a year a history should hold or what share may be single events
  rather than arcs. The only numbers are words per point of narrative weight (`chapters.py:27`).
- **Base levels without reasons.** About ten of 168 kinds state why they hold their level. Nothing says what makes
  a kind `major` rather than `minor` beyond the four docstrings, and those describe atomic and narrative events in
  one sentence each (see contradiction 1). #537 takes this up.
- **Alien activity on Earth.** `major` at the atomic level and absent from the package (`kinds/aliens.py:3`); #304
  is open. The aliens are "the backdrop" for stakes (`CONTEXT.md:150`), and nothing says what of them the history
  must tell.
- **Councilors in the history.** Councilor events are narrator evidence and some are `major`
  (`kinds/control.py:149-163`), but no narrative kind is about a councilor; they appear only inside takeovers and in
  the separate articles (#222: "independent from the main narrative").
- **The player's perspective before the narrator.** Decided out of significance (`0011:37`); no package field marks
  what concerns the player's faction beyond `player_faction_name`, so a package judged on its own cannot show
  whether it serves an account centred on the player.
- **Arcs wider than a narrative event.** No rule or statement connects narrative events into a larger story; #343
  and the map's "higher-level connections" note are open.
- **Direction and reaction are not separated.** `docs/narrator.md:47-55` explains the reactive rules, but the
  prompt mixes them with direction in the same sections, and nothing records which trial each rule answers beyond
  one sentence and the issues #124 to #132.
- **Duration, recency and openness.** Nothing says whether a long or still-open episode matters more than a short,
  closed one.
