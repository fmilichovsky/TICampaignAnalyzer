# `terra_invicta_json_v1` envelope

**Scope.** This identifier names the JSON envelope observed on 2026-09-08 in the private save directory. It does not identify, or imply compatibility with, a particular Terra Invicta release.

## Observed facts

- The three sampled files (`Resistsave00070_2041-5-1.json`, `Autosave.json`, and `Exitsave.json`) began with byte `0x7B` (`{`), with no byte-order mark. They decoded as JSON text with CRLF and indentation; all three parsed as JSON objects.
- The observed top-level keys, in order, were `currentID` and `gamestates`. `currentID` was an object with a `value` member.
- `gamestates` was an object keyed by fully-qualified state-type names. Each sampled file contained 76 such keys, including `PavonisInteractive.TerraInvicta.TIMetadataState`, `TITimeState`, `TIFactionState`, `TINationState`, `TIHabState`, and `TISpaceShipState`.
- The three samples had the same set of 76 `gamestates` keys. This is an observation about these samples, not a required universal key set.
- No sampled file contained a top-level `game_version` key. Consequently, their game build cannot be detected from that field.
- The files are approximately 73--84 MB. The loader must retain bytes exactly and must not assume small, one-line JSON input.

## Encoding and decompression assumptions

The supported v1 envelope is **uncompressed JSON bytes**. The loader does not apply gzip, zip, base64, or other decompression/decoding before JSON parsing. This is based on the leading bytes and successful direct JSON parsing above. Compressed files, a different character encoding, a byte-order mark, or a non-object JSON root are outside this format identifier and must receive a different, documented identifier before support is added.

## Version detection and support boundary

`game_version` is an optional serialized field, not an inferred build number. When absent, `detect_game_version` returns `None`; this is the expected outcome for the observed v1 samples. A string or number in a synthetic fragment is merely reported (numbers are converted to strings) so callers can give a useful diagnostic.

No real game build has been observed in serialized metadata, so no explicit game build is supported. `require_supported_game_version` rejects an explicit value clearly. `require_supported_format("terra_invicta_json_v1")` is the separate assertion that the caller selected this documented envelope; unknown format identifiers are rejected clearly.

## Hypotheses and open questions

- The pair-map convention is documented from one complete save in [the container notes](containers-and-references.md); its coverage in every possible state type and build remains unverified.
- The observed state-key count may be specific to this campaign era, installed content, or game build. Do not reject a future save solely because a state type is added or removed.
- A game build may be stored inside a nested metadata state or outside the save. That has not been established and is not used for version detection.

## Adding a format or build

1. Inspect permitted saves locally and record only structural observations.
2. Add a new documented format identifier (or a build identifier with direct evidence), clearly separating facts from hypotheses.
3. Add small synthetic fixtures and give every manifest entry a matching `format_assumption` and `version_assumption`.
4. Add that identifier to the relevant supported set and tests for acceptance and clear rejection of an unknown value.

## Related decoding notes

- [Containers, identity, and references](containers-and-references.md) documents the typed pair-map encoding, empty-container behavior, and ID invariant.
- [Domain field map](domain-field-map.md) maps observed state types and fields to the architecture's normalized domains without exposing campaign data.
- [State-type inventory](state-type-inventory.md) lists every exact state key in the observed three-save envelope.
