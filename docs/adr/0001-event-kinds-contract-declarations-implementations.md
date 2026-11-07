# Event kinds: contract in `model`, declarations in `kinds`, implementations in `significance`

Each event type is declared once, as an event kind. The pieces of a kind live in three places, one per role:

- **`model/kinds.py`** holds the contract: the `EventKind` type and the `Rule`, `Stake` and `StakeMeasure` enums.
- **`tinarrative/kinds/`** holds the declarations with their templates, one module per family. It sits after `diff` and before `analyzers`.
- **`narrative/significance.py`** holds the one exhaustive mapping from each `Rule` and `Stake` to its implementation.

Every stage reads the kinds: analyzers, reconstruction, narrative rules, rendering and the narrator package. Only a package below the analyzers can be imported by all of them without breaking stage order. Kinds name their context rules and stakes instead of holding the functions, because those functions work on narrative-stage types. The templates stay out of `model`, which carries no prose.

A related rule: a kind check fails only on a code bug, never on save content. Types whose names come from the save go through the one prefix kind, `notification.*`. An attribute whose presence depends on the save is optional. A required attribute is always passed, though its value may be `Unknown`. Under that rule, a failed check raises.

## Considered options

- **Declaring each kind next to its emitter.** This gives the best locality: a new type touches one file. It was rejected because rendering and significance would have to import from every stage to find all the kinds, and the narrative-event kinds sit downstream of the analyzers that render them.
- **One flat catalogue module** for about 180 kinds. It was rejected for its size.
- **Registering rule and stake implementations at import time.** It was rejected for import-order effects; a static mapping is in one place to read.
- **Logging an undeclared attribute or type instead of raising.** It was rejected because drift could slip through. The save-content rule above is what makes raising safe.

Tracked in #316.
