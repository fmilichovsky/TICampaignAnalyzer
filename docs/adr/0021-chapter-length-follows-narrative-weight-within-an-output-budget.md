# Chapter length follows narrative weight within an output budget

[ADR-0015](0015-chapters-are-independent-requests.md) bounds a chapter by its request's input alone. The length a
chapter is asked for was then a by-product of how many chapters the budget made, and a larger input budget
silently meant a shorter, more condensed history.

- **Every length scales with narrative weight.** A chapter is always asked for a length in proportion to the narrative
  it is compelled to cover, also when the user gives none. A given length is shared out the same way.
- **Output is a second chapter budget.** A chapter must also leave its length room within one response, with a fixed
  part of the response kept for the model's reasoning. Periods that ask for more go to separate chapters.
- **An output split keeps the evidence.** Leaving out the atomic stream shortens the request, never the length, so a
  period split for output keeps its atomic stream wherever the input budget allows.
- **No per-provider rules.** A model that reasons at length gets a larger output budget in its profile; the planner
  does not know providers.

## Considered options

- **A length only when asked.** It was rejected because the model then sets the length, and with large chapters it
  condenses: the same campaign came out about a third as long in one chapter as in five, quoting the package.
- **Larger default input budgets for models with large context windows.** It was rejected for the same reason; one
  chapter saves little input over five and gives up sending chapters in parallel.
- **A per-profile reasoning allowance.** It was rejected as the provider-specific setting the output budget already
  covers.

Tracked in #418.
