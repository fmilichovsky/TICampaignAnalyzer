# Chapters are independent requests

A long campaign does not fit one model request, so it is cut into chapters of whole periods, each its own request.
The plan comes from a local, deterministic estimate of the request size, never a provider's token count. So chapter
boundaries depend only on the package and the settings.

- **Continuity comes from the package, never from earlier prose.** A chapter receives three things:
  - the narrative events still running from earlier chapters, marked as already told;
  - a capped digest of the earlier chapters' major narrative events;
  - the previous chapter's closing situation as its opening.

  Generated text is not a source, and an error in one chapter must not become a premise of the next. So chapters
  can be re-run, resumed, reused or sent in parallel.
- **Slicing selects entries and never rewrites one.**
- **Over budget, facts are never dropped silently.** A period is reduced in a fixed, recorded order:
  1. drop the atomic stream;
  2. split at save boundaries;
  3. stop before sending and report the budget needed.

  Narrative events are never dropped, and the significance cut is never raised behind the user's back.

## Considered options

- **Passing earlier prose forward** as a rolling summary. It was rejected because errors propagate and the chapters
  must then run one after another.
- **Truncating to fit.** It was rejected because it removes facts without the reader knowing.
