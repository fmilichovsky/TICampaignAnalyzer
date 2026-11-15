# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

The product is a Python CLI (`tinarrative`, Python 3.11+). No HTML surface exists yet.

Delegated for HTML surfaces: plain HTML, CSS and JavaScript that Python generates or serves. No build step and no
npm runtime dependencies. Node is used only for parity checks such as `make browser-replay-check`. A small library
may be vendored into a page when a surface really needs one, never loaded from a CDN. This fits a Python-only
install, works offline, and lets JS logic stay under parity with its Python twin.

- Maintainer dev aids (the stake calibration page, #446/#464): a generated static page opened from disk
  (`file://`). No server, no network, no hosting.
- Player surfaces: the CLI may run a local server on localhost. Provider calls go through the Python process, so
  API keys never reach the page.

## Users

- **Primary: Terra Invicta players.** They point the tool at their save directory and want a readable history of
  their campaign: a chronicle or headlines, for the public or an insider audience, plus articles about the notable
  councilors. Many play long campaigns over weeks and come back between sessions. Design decisions are made for
  them first.
- **Secondary: the maintainer, and coding agents.** They use dev aids such as the stake calibration dashboard to
  tune the pipeline against the benchmark campaigns. Agents read the same numbers from the CLI that humans see in
  the browser.

## Product Purpose

`tinarrative` reconstructs a readable campaign history from Terra Invicta save files. A deterministic, local
pipeline turns save snapshots into a filtered, ranked and partly interpreted narrator package. An LLM then writes
the story from that package and explains how the public would plausibly perceive the events. Success means a player
reads a history that is true to their saves, worth reading, and traceable back to the evidence.

## Positioning

What the saves prove stays separate from what the analyzer infers, and both stay separate from how the story is
told (ADR-0003, ADR-0014). The LLM narrates and never reconstructs: every claim in a history cites event IDs that
lead back to literal save changes. Most of the work runs locally without an LLM. Narration works with several
providers (Anthropic, OpenAI, OpenRouter, local Ollama).

## Operating Context

- Input: a directory of Terra Invicta saves. Campaigns are inferred from shared identity, and a directory can hold
  several. Saves are ordered by game time and analysed per interval.
- Outputs today: Markdown reports and JSON packages (`events`, `save diff`), one LLM request per chapter, and an
  assembled, footnoted `history.md` plus councilor articles.
- Narration with `--send` hands the campaign to a third party unless the provider runs locally, and can take a
  while.
- Planned: continuous capture (`tinarrative watch`) records every save during play and narrates a growing campaign
  in sealed installments (ADR-0016–0018).

## Capabilities and Constraints

- Commands: `campaigns`, `narrate`, `councilors`, `events`, `save diff|parse|inspect`, `unknowns`, `benchmark`.
- Domain terms are defined in `CONTEXT.md` (campaign, interval, atomic event, narrative event, constituent,
  significance, situation report, and so on). Surfaces use these terms, not synonyms.
- Significance levels: trivial, minor, major, campaign defining.
- Pages that make network calls (for example a background narration) must stay responsive while the call runs and
  keep the data they already have when offline.
- **Undecided:** what the player-facing surface is (a campaign app, a history reader, or something else). Left for
  `shape`/new-work. A local server is allowed for it.

## Brand Commitments

- Name: `tinarrative`, long form "Terra Invicta Narrative Save Analyzer". MIT licensed.
- An unofficial fan tool: no Terra Invicta or Pavonis Interactive art, logos or trade dress.
- Voice, as in the docs: plain, precise and unhyped; the domain vocabulary is used consistently.
- Dark theme is a requirement, not an option. Players use the tool beside the game or at night.

## Evidence on Hand

- Real sample campaigns in `benchmarks/` (Protectorate, Protectorate-short, Resist) with package-size and runtime
  measurements.
- Generated narrator packages, histories and councilor articles can be produced from those samples.
- There are no testimonials, user counts, press or screenshots. Do not invent any.

## Product Principles

1. **Evidence first.** Every surface keeps the line between what the saves prove, what the analyzer infers and
   what the narrator says, and lets the reader follow a claim back to its events.
2. **The story is the product for players.** Analysis serves the reading. Tooling detail stays one step away
   unless the reader asks for it.
3. **Local by default; sending is explicit.** Nothing leaves the machine without the user choosing to send it, and
   the surface says when it does.
4. **Same numbers for people and agents.** What a page shows, the CLI can report too.
5. **Resilient while waiting.** Long or networked work never freezes a page or throws away what it already shows.
