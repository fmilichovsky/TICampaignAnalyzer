# Narrative rule order is derived from what rules declare they read

Each narrative rule declares the narrative event types it reads, whether it cites them, is explained away by them
or only consults them. The order rules run in is derived from those declarations, never numbered by hand. The
guarantees of [ADR-0002](0002-rule-order-enforces-exclusive-constituents-and-explainers.md) stay: exclusive
constituents and explainers are still enforced by order, and a rule still sees only narrative events built before
it ([ADR-0009](0009-narrative-aggregation-uses-anchored-rules.md)).

- **Every interaction between narrative kinds is declared.** A rule that reads a narrative type it did not declare
  fails the run. A hand number set too low made such a read silently empty, whatever the rule meant to do with it:
  a rule cannot cite what it cannot see, so citing out of order was as silent as consulting out of order.
- **Explainers stay a declaration of their own.** They are a read that can keep the rule's own narrative event
  from existing. An explainer is read, never consumed.
- **An exclusive constituent's owner runs before every rule that does not feed it,** so no other rule has to know
  about it. Two owners are ordered only where one declares that it reads the other.
- **Overlap between owners is not the order's job.** Where two owners exclude each other by definition, as a merger
  and a cession do, the yielding rule says so by the atomic evidence that decides it. The citation check of
  ADR-0002 and the rules' tests catch an overlap nobody declared.
- **Undeclared reads fail in tests, not in a user's run.** Every rule is run against an event of every known type.
- **A cycle is a code bug** and fails before any save is read.

## Considered options

- **Hand-numbered orders with each declaration checked against them,** as ADR-0002 did for explainers. It was
  rejected because the numbers still flatten the graph by hand: adding a rule renumbers rules elsewhere, and a
  number nobody can justify cannot safely be moved.
- **One declaration per purpose: cited, explaining, consulted.** It was rejected because the output already
  records what was cited, and the split adds no check. Only explaining changes what a rule emits.
- **Each reader declares the exclusive owners it runs after.** It was rejected because every new rule would have
  to predict which owners overlap its inputs, the duplication ADR-0002 removed.
- **Every pair of exclusive owners must be ordered.** It was rejected because owners that cannot overlap would
  need an arbitrary precedence, and a merger and a cession are already kept apart by evidence.
- **A priority among exclusive owners.** It was rejected because it brings back a hand number.

Tracked in #344.
