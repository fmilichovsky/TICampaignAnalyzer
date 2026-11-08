# The LLM narrates and never reconstructs

The deterministic half of the pipeline establishes the facts. An LLM only turns them into prose.

- **The narrator package is the only interface.**
  - The narrator half depends on the package's JSON form and its own settings, never on the parsing or model code.
    So a package can be narrated on another machine, or long after it was built.
  - The package holds the narrative events, a situation report per save, a glossary of entity names, and the
    constituent events for drill-down. Every entry carries its ID.
  - It drops sources and file paths. Provenance stays with the events report that built the package, and a cited
    ID reaches it.
- **The model phrases; it never decides facts.**
  - It may order and phrase. It may not merge narrative events that the rules kept apart, nor take the raw atomic
    stream as its primary input, nor supply a fact the package does not hold.
  - Its claims cite event IDs. A citation audit lists unmatched citations and uncited major events. It reports and
    never rejects prose: a wrong citation is a finding for the prompt.
  - Whatever the package cannot state, such as a motive or the public framing of a move, is worded as
    interpretation. It cites nothing and never becomes the premise of a later factual claim.
- **Requests are deterministic; prose is not.** Every request is a byte-for-byte function of the package and the
  settings. The run manifest records both requests and responses, so a history can be traced to its inputs even
  when it cannot be reproduced word for word.
- **Sending is explicit.** Without being asked to send, the narrator writes its requests and contacts nothing, so
  each one can be reviewed first. The package carries the campaign, which reaches a third party unless the provider
  is local.

The prompt and its rationale are in [narrator](../narrator.md).

## Considered options

- **An LLM reading saves or diffs directly.** It was rejected because its output cannot be audited, and it invents
  what the data does not say.
- **Letting the model group events into episodes.** It was rejected because grouping is a factual judgement, made
  by rules ([ADR-0009](0009-narrative-aggregation-uses-anchored-rules.md)).
