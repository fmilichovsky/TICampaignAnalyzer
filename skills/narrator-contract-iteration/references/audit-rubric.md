# Narrator evidence audit rubric

Use this rubric only for an independent review of a produced narrator
chronicle.  The audit verifies fidelity to the supplied package; it does not
use save files, game lore, web knowledge, or prior conversation.

## Inputs and scope

Read the rendered narrative, the narrator package, its corresponding
`--inferred` audit package, and the exact narrator prompt.  Confirm the two
packages describe the same campaign, saves, and significance level before
reviewing prose.  If they do not, return a blocking audit-environment failure.

The narrative package supports narrative-level claims.  The audit package
resolves its narrative constituents to atomic or inferred events and their
save locations.  It does not license claims absent from the narrative package.

## Review procedure

1. Split the narrative into factual claims, explicitly marked interpretations,
   headings, footnotes, and the closing situation.  A compound sentence can
   contain several claims.
2. For every factual claim, find its required footnote when citations are on.
   Resolve each cited ID in the narrative package or, for a detail beyond the
   narrative event, in the audit package.  Verify that it supports the exact
   subject, relation, number, name, date precision, and status/confidence.
3. Check inference wording: objective evidence may be plain; inferred evidence
   must retain its confidence and be recognisable as reconstruction.  A
   conjecture must not become an established premise later.
4. Check contract-specific hazards: interval versus record dates; `open`
   developments; unknown versus zero; causal language; the meaning of control
   changes, vanished assets, battle outcomes, and global counters; public
   treatment of human-faction space assets; and facts introduced by headings
   or closing summaries.
5. Check coverage only against the visible `major` and
   `campaign_defining` narrative events.  Report a missing development when it
   is absent without a credible proportionality reason; do not demand a
   mention of every atomic event or filtered event.

## Severity and report format

Return a concise structured report with these sections:

```text
Audit environment: pass | block
Summary: critical N; major N; minor N; cautions N

Findings
- [severity] claim or sentence: problem
  Evidence: cited IDs / package fields / prompt rule
  Why it fails: ...
  Suggested layer: prompt | request builder | package/pipeline | narrator output

Coverage
- covered major developments: ...
- notable omissions: ...

Limits and cautions
- ...
```

- **critical**: invented campaign fact, a private-audience breach, or a claim
  whose cited evidence resolves to something materially different.
- **major**: unsupported or over-certain factual claim, wrong date precision,
  causation presented as fact, or a conspicuous omitted major development.
- **minor**: malformed/missing citation for an otherwise supported claim,
  imprecise but non-material phrasing, or a local contract/style concern.
- **caution**: an ambiguity or thin record that the auditor cannot resolve;
  it is not a violation.

Do not score prose quality, rewrite the narrative, treat an unmentioned
filtered event as proof of absence, or promote a faction brief into campaign
evidence.  A clean audit means only that the supplied package supports the
chronicle, not that the deterministic pipeline captured every real event.
