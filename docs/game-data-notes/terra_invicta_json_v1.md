# `terra_invicta_json_v1` envelope

**Scope.** This identifier names the JSON envelope observed on 2026-09-08 in the private save directory. It does not identify, or imply compatibility with, a particular Terra Invicta release.

## Observed facts

- The three sampled files (`Resistsave00070_2041-5-1.json`, `Autosave.json`, and `Exitsave.json`) began with byte `0x7B` (`{`), with no byte-order mark. They decoded as JSON text with CRLF and indentation; all three parsed as JSON objects.
- The observed top-level keys, in order, were `currentID` and `gamestates`. `currentID` was an object with a `value` member.
- `gamestates` was an object keyed by fully-qualified state-type names. Each sampled file contained 76 such keys, including `PavonisInteractive.TerraInvicta.TIMetadataState`, `TITimeState`, `TIFactionState`, `TINationState`, `TIHabState`, and `TISpaceShipState`.
- The three samples had the same set of 76 `gamestates` keys. This is an observation about these samples, not a required universal key set.
- No sampled file contained a top-level `game_version` key; saves do not serialize one. The game build is `TIGlobalValuesState.latestSaveVersion`.
- The files are approximately 73--84 MB. The loader must retain bytes exactly and must not assume small, one-line JSON input.

## Encoding and decompression assumptions

The supported v1 envelope is **uncompressed JSON bytes**. The loader does not apply gzip, zip, base64, or other decompression/decoding before JSON parsing. This is based on the leading bytes and successful direct JSON parsing above. Compressed files, a different character encoding, a byte-order mark, or a non-object JSON root are outside this format identifier and must receive a different, documented identifier before support is added.

## Version detection and support boundary

`detect_game_version` reports the string in `TIGlobalValuesState.latestSaveVersion` (see the [notes README](README.md)), or `None` when the singleton or the member is absent or not a string. It is not an inferred build number and not a compatibility boundary: no save is accepted or rejected because of its game build, since the format has changed additively between observed builds. A top-level `game_version` member is ignored.

`require_supported_format("terra_invicta_json_v1")` is the only support check: the assertion that the caller selected this documented envelope. Unknown format identifiers are rejected clearly.

## Loader validation

`parse_raw_save` (in `tinarrative.parsing`) turns bytes into a `RawSave` for this identifier. Its checks follow only the observations above: the bytes must be non-empty, uncompressed UTF-8 JSON without a byte-order mark, the root must be an object, and `currentID` and `gamestates` must be present with `gamestates` an object (observed in all three samples). The contents of `gamestates` are not validated, so unknown state types load. The error categories (`MalformedSaveError`, `UnsupportedSaveShapeError`, `UnsupportedSaveFormatError`) are a design choice, not format claims. Requiring `currentID` as an envelope member is a conservative reading of three samples (hypothesis for other builds). Each case is covered by a synthetic fixture whose manifest `expected_loader_outcome` states the result; gzip, zip, UTF-16, BOM, empty and invalid-UTF-8 inputs are built inline in tests.

## Hypotheses and open questions

- The pair-map convention is documented from one complete save in [the container notes](containers-and-references.md); its coverage in every possible state type and build remains unverified.
- The observed state-key count may be specific to this campaign era, installed content, or game build. Do not reject a future save solely because a state type is added or removed.
- A game build is stored inside the `TIGlobalValuesState` singleton (`latestSaveVersion`, observed 2026-10-16); it is reported, never gated on. Whether other builds store it elsewhere is not established.

## Adding a format

A new game build needs no parser change: run the [unknowns scan](unknowns/README.md) on its saves and triage what it reports. A new format identifier is only for an incompatible envelope (for example compressed saves).

1. Inspect permitted saves locally and record only structural observations.
2. Add a new documented format identifier, clearly separating facts from hypotheses.
3. Add small synthetic fixtures and give every manifest entry a matching `format_assumption` and `version_assumption`.
4. Add that identifier to the relevant supported set and tests for acceptance and clear rejection of an unknown value.

## Related decoding notes

- [Containers, identity, and references](containers-and-references.md) documents the typed pair-map encoding, empty-container behavior, and ID invariant.
- [Domain field map](domain-field-map.md) maps observed state types and fields to the architecture's normalized domains without exposing campaign data.
- [State-type inventory](state-type-inventory.md) lists every exact state key in the observed three-save envelope.
