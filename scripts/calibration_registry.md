# The calibration registry

The registry of calibration work is the issue tracker itself: every issue and pull request labelled `calibration`.
No file in the repository holds it. `calibration_registry.py` reads it once at the start of a review, so no agent
parses the lines below by hand.

Only registry members carry the `calibration` label: reviews, value proposals, scoring proposals and structural
findings. The framework's own build issues and PRs never do, or they would flood the registry.

## The two lines

Every `calibration` issue and PR carries two lines in its body, each on a line of its own and outside any code
block:

```text
Calibration: value proposal
Touches: types=war.arc,war.declared; measures=power; scalings=power; themes=Wars; principles=both-ways
```

- **`Calibration:`** names the item's kind, exactly one of `review`, `value proposal`, `scoring proposal` or
  `structural finding` ([CONTEXT.md](../CONTEXT.md) defines them).
- **`Touches:`** names what the item is about, as `;`-separated groups of `,`-separated values:
  - `types=`: event types, as the catalog spells them (`war.arc`);
  - `measures=`: measures (`power`, `fleet`);
  - `scalings=`: scalings, including a split-off one named only in the calibration state;
  - `themes=`: theme names, exactly as `benchmarks/themes.toml` spells them (`Wars`);
  - `principles=`: [calibration principle](../docs/calibration-principles.md) identifiers, as the marker beside each
    principle spells them, without a revision (`trivial-is-a-role`). A change to a principle lists the open items
    standing on it with `--principle`.

  Any group may be absent, but a Touches line has at least one. Values may be wrapped in backticks. A review's
  Touches line is its scope.

A line inside a fenced code block, like the example above, is never read as the item's own.

## Where reviews go

The long-lived parent issue titled exactly
[**Calibration reviews**](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/705) holds every review as a
sub-issue. Each proposal and finding a review raises is a sub-issue of that review. Items that predate the framework
stay outside any review; the script finds them by the label.

## Running the script

It needs Python 3.11 or later and an authenticated `gh`; it uses the standard library only.

```sh
python scripts/calibration_registry.py                         # everything open, and closed in the last 90 days
python scripts/calibration_registry.py --type war.arc          # what touches war arcs
python scripts/calibration_registry.py --theme Wars --measure power --json
python scripts/calibration_registry.py --principle trivial-is-a-role   # what stands on a principle
python scripts/calibration_registry.py --since 365             # a year of closed items
```

It prints three sections:

- **Items**: open and recently closed members with both lines, their kind and Touches.
- **Open reviews**: the parent's open sub-issues whose scope overlaps the filter. A review with no usable Touches
  line is always listed.
- **No Touches line or Calibration line**: members missing a line or carrying a malformed one, with the problem, so
  they get fixed. They are listed whatever the filter.

`--type`, `--measure`, `--scaling`, `--theme` and `--principle` each repeat or take comma-separated values, and ignore case. An
item matches when any of its Touches groups overlaps its filter. `--json` prints the same sections for agents.
`--repo OWNER/NAME` reads another repository than the one `gh` infers.

Exit codes: `0` on success, `2` when `gh` fails or is missing.
