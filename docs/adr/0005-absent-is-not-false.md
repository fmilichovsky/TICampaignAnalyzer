# Absent is not false; nothing is dropped silently

Real saves are incomplete, depend on the game version and are partly undocumented. The analyzer treats absence of
evidence as normal:

- A field the save does not carry is `Unknown` with a reason, never false, zero or empty.
- A reference resolves only when its target exists in the same save under the expected domain. Otherwise it stays
  `Unknown` and keeps the raw ID.
- When either side is `Unknown`, the diff records an unknown change and infers nothing from the known side.
- Every structure outside the documented schema is reported to the
  [unknowns registry](../game-data-notes/unknowns/README.md) as a finding without save content. It is never
  coerced into a model value.

Further downstream the same rule reads: "not enough evidence to infer" is better than a confidently invented event.

## Considered options

- **Defaulting missing fields.** It was rejected because a default cannot be told apart from an observed value. It
  also turns a field that appears or disappears between game versions into a phantom transition.
