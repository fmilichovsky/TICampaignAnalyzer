# One event envelope with independent dimensions

Every layer uses one event type. Four separate fields answer four questions about an event, and no field answers
two of them:

- **Status**, objective or inferred: how directly does the save support it? An objective event is a direct state
  transition or a literal record entry. An inferred event is a reconstructed action or cause, and may be strongly
  supported without being persisted in the save.
- **Level**, atomic or narrative: how much of the stream does it represent? A narrative event may contain both
  objective and inferred constituents.
- **Confidence**, high, medium or low: how strongly is the reconstruction supported?
- **Significance**: how much does it matter to the history ([ADR-0011](0011-significance-is-judged-once-and-scaled-by-stake.md))?

A narrative event is an event with a span, roles and constituents, not a parallel type. So significance,
rendering, the narrator package and citation all handle both levels the same way. The envelope carries no prose.

## Considered options

- **A type hierarchy per layer.** It was rejected because every consumer would need a code path per layer, and
  the citation chain would cross types.
- **Folding confidence into status**, so that "inferred" means "uncertain". It was rejected because an inferred
  event can be well supported, and a certain objective event can be trivial.
