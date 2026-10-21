# Narrator system prompt

Use the following text as the system prompt for an LLM that renders a
`tinarrative` narrator package ([architecture 13.1](architecture.md#131-narrator-input)
and [20](architecture.md#20-llm-narration)). The prompt fixes a short
floor of facts (what happened, to whom, where, when, and every number come from
the package) and leaves everything above that floor to the model: how a change
was presented and received, what it may have meant, what an actor may have
wanted. The result should read as history, not as a report on the package.

Hand the model the JSON of `tinarrative events --narrative --include-constituents
--format json` with `--min-significance` at the level of the developments the
history should cover, and a request block as described in the prompt. That
package carries IDs but no provenance or file paths. Its atomic events are only
the constituents of the listed developments, whatever their significance, so
every cited ID resolves inside it; without `--include-constituents` it carries
developments, situations and glossary only. The audit form is the same command
with `--inferred` instead of `--narrative` and no `--min-significance`: it lists
every atomic and inferred event with its save locations, and a narrative event
is audited through its constituents
([events, narrator package](commands/events.md#narrator-package)). `major` is
the practical level for a whole campaign; `minor` adds developments such as
fleet buildups and technology milestones, and their constituents with them.
Citations are one footnote per
entry, so a sentence is audited through the entry it belongs to. A package
too large for one request is cut into chapters by
[`tinarrative narrate`](commands/narrate.md)
([architecture 20.3–20.4](architecture.md#203-token-budget-and-chapters)). The
prompt reads the chapter's `chapter`, `part` and `covers` keys and its
`continuity` member with a few rules: only a `whole` or `first` part introduces
the history, and only a `whole` or `last` part ends with where things stood. A
period cut by `covers` is written under its heading in both chapters. The
backstory rule counts from the chapter's opening save. `continuity` IDs are
citable. These rules keep chapters independent, because no chapter's prose is
input to another: the model learns the earlier story only from `continuity`, so
an error in one chapter cannot become a premise of the next.

The prompt carries its own short faction briefs, condensed from the game's
faction descriptions in [game-data-notes/factions](game-data-notes/factions/).
They leave out leaders, endgames and story spoilers on purpose; when those
descriptions change, update the briefs here to match.

The prompt was shaped by trial runs on a private campaign; the rules in "How to
read the fields" and "Facts" each answer a failure a trial produced (count
direction, invented backstory, game keys read as content, seats of government
derived from region names). Keep it short: a longer rulebook did not buy
accuracy on a mid-sized model, it only made the prose talk about the rules.

The prompt itself ships with the package, as
[`src/tinarrative/narrator/prompt.md`](../src/tinarrative/narrator/prompt.md),
so an installed wheel carries the text it sends. That file is the only copy:
edit it there, not here. Its SHA-256 is the prompt version
(`tinarrative.narrator.request.prompt_version`), and
`python scripts/narrator_prompt.py` prints the request it produces.
