---
name: narrator-contract-iteration
description: Evaluate and improve tinarrative's narrator prompt, deterministic narrator package, or narrative-event filtering with a private real-save campaign, an independent narrative pass, and an evidence audit. Use for deliberate narrator-contract iteration; not for ordinary save analysis or prose editing.
---

# Narrator-contract iteration

Use this skill to make one bounded, evidence-led iteration on the contract
between the narrator prompt (`src/tinarrative/narrator/prompt.md`, rationale in `docs/narrator.md`), the narrator package, and its narrative output.
The workflow is provider-neutral: a *narrator* and an *auditor* are independent
agents or separate fresh contexts.  Do not require a particular model, API,
system-message mechanism, or agent product.

Read `docs/adr/0014-the-llm-narrates-and-never-reconstructs.md`, `docs/narrator.md`, `src/tinarrative/narrator/prompt.md`,
`docs/commands/events.md`, and [the audit rubric](references/audit-rubric.md)
before starting.  Keep the distinction between objective evidence, inference,
narrative aggregation, and rendering intact.

## Privacy and boundaries

- Treat `real_saves/`, generated packages, audit reports, and prose as private
  campaign material.  Work in a temporary or explicitly user-approved private
  output directory.  Never commit, attach, paste into public artifacts, or turn
  any of it into a fixture.  Do not put save paths or save values in diagnostics.
- This skill evaluates one selected campaign, not a model matrix or benchmark.
  Do not call external services or create tracker issues unless the user asks.
- Use the repository's local CLI/environment.  Do not modify the prompt,
  configuration, or analyzers merely because one narrator preferred different
  prose; first establish the likely layer at fault.
- If no usable private sequence is available, say so and offer the synthetic
  `politics_sequence` only for request-shape or regression work.  It is not a
  substitute for validating real campaign coverage.

## Run one iteration

### 1. Select a campaign reproducibly

Run `tinarrative campaigns real_saves --format json`.  From the returned
classified campaigns, select one with at least two distinct saves.  Prefer the
largest chronological span; break a tie by more saves, then by the stable
campaign key.  This selects a contiguous sequence as `events` defines it: all
available snapshots of one grouped campaign, ordered by serialized game time.
Do not combine groups or use file timestamps to order saves.  Record only the
selected campaign key, save count, first date, and last date in the iteration
summary; do not expose paths.

If the selection would be surprising--for example, an unclassified group is
the only long sequence, or two candidates serve visibly different evaluation
purposes--ask the user to choose.  Otherwise use the deterministic rule above.

Create a private run directory and preserve these three named artifacts there:

```sh
tinarrative events real_saves --campaign <campaign-key> --narrative --include-constituents \
  --format json --min-significance major > package.json
tinarrative events real_saves --campaign <campaign-key> --inferred --format json \
  > audit-package.json
python scripts/narrator_prompt.py package.json --period year --audience public \
  --citations footnotes > narrator-request.json
```

The first command is the canonical deterministic reconstruction for this
skill.  The second is the audit view: it has every atomic and
inferred ID plus source locations, without narrative aggregation.  Check that
both commands succeed, that their campaign key and save keys agree, and that
every atomic and constituent ID of the package resolves in the audit before
handing either package to an agent.  `narrator-request.json`
is a transport-neutral representation of the exact system text and user
content; adapt it only to the receiving agent's documented message format.

### 2. Obtain an independent narrative

Give a fresh narrator only `narrator-request.json` (or its exact system and
user fields).  Do not supply conclusions from earlier runs, hidden save data,
or the audit package.  Ask it to return two clearly separated parts:

1. `Narrative`: the requested Markdown chronicle, with no commentary mixed in.
2. `Producer notes`: concise operational difficulties, if any.  Each note must
   identify whether the package was thin, ambiguous, hard to cite, missing a
   needed distinction, or the prompt's constraints made an otherwise supported
   treatment difficult.  It must not manufacture campaign facts to fill a gap.

Save the narrative and producer notes separately.  Producer notes are a lead
for investigation, not evidence that the contract is defective.

### 3. Audit independently

Give a fresh auditor the narrative, `package.json`, `audit-package.json`, and
the narrator prompt.  Do not give it the producer notes or a proposed fix.
Have it follow [the audit rubric](references/audit-rubric.md) and return a
structured report, not a rewritten chronicle.  It must distinguish:

- confirmed violations, with the exact sentence or claim, citation(s), package
  evidence, and severity;
- unsupported or over-certain claims (including dates, names, quantities,
  causation, and public-audience disclosure);
- citation or ID-resolution defects; and
- non-violating cautions and audit limits.

An audit finding is not automatically a prompt defect.  Resolve citation and
truth problems before evaluating voice or coverage.  If the auditor's reading
is itself unsupported, record that disagreement rather than treating it as a
failure.

### 4. Present a reviewable result

Show the user the narrative verbatim in the private working context, alongside
a compact audit summary: pass/fail counts by severity, unresolved findings,
and the narrator's producer notes.  Do not bury the narrative beneath the raw
package or audit trace.  Ask for feedback on content selection and voice after
they can read it.

### 5. Triage feedback before changing anything

Classify every confirmed audit finding and user observation.  One observation
may have more than one plausible layer; name the evidence for the choice.

| Signal | Likely first place to inspect | Usual response |
| --- | --- | --- |
| Unsupported fact, wrong certainty, wrong interval date, invalid citation, or audience leak | `src/tinarrative/narrator/prompt.md` and request construction (`narrator/request.py`) | Tighten or clarify the prompt; add a focused regression where practical. |
| Rigid, repetitive, overly long, or poorly structured prose while claims and coverage are sound | `src/tinarrative/narrator/prompt.md` | Make a small style instruction change; preserve evidence rules. |
| Important recorded narrative event absent from both package and prose | Analyzer, reconstruction, narrative aggregation, or significance rules | Trace the selected saves through the deterministic pipeline; propose a focused implementation issue or make a small, tested fix. |
| Important package narrative event omitted by otherwise compliant prose | `src/tinarrative/narrator/prompt.md` | Adjust prioritisation or shape guidance, then rerun the narrator and audit. |
| Too much low-value material present in the package | Significance or aggregation configuration/rules | Inspect thresholds and grouping; do not solve it by asking the narrator to conceal major evidence indiscriminately. |
| Correct package with disputed interpretation or desired editorial emphasis | Prompt and user request block | Treat as an editorial choice, not a detection bug. |

For a pipeline diagnosis, use the audit package and the narrative package first,
then inspect the minimum relevant normalized/event code.  Never infer missing
events from what the narrator "should know."  Preserve the
evidence/inference separation (`docs/adr/0003-pipeline-stages-keep-the-evidence-below-them.md`).

### 6. Resolve proportionately and close the loop

For a small, well-scoped fix, implement it with the repository's conventions:
update the relevant docs, add or adjust focused synthetic tests, and run the
relevant checks.  A prompt-only change should at least preserve the request
builder test; pipeline changes should satisfy the corresponding analyzer or
narrative tests.  Do not use real saves as test fixtures.

For a larger or uncertain change, write a proposed follow-up issue locally in
the handback: problem, observed symptom, likely layer, evidence, acceptance
criteria, and suggested tests.  Do not create an issue remotely without
authorization.

Whenever the prompt, request builder, package-producing pipeline, or filtering
settings change, regenerate both packages and repeat the independent narrator
and audit passes on the same selected campaign.  Stop after one verified
change-and-rerun cycle unless the user explicitly asks for another iteration.

## Handback

Report the campaign selection without paths, commands and artifact locations
without private contents, the narrative, audit outcome, producer notes,
feedback classification, changes made (if any), verification, and any proposed
follow-up issues.  State plainly when the evidence cannot distinguish a prompt
problem from a package problem.
