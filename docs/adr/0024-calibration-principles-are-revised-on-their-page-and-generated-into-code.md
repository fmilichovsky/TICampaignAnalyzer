# Calibration principles are revised on their page and generated into code

A reason says why an event kind's base level or a scaling's shares sit where they do, and it rests on one
[calibration principle](../calibration-principles.md). When a principle changes, every reason resting on it may be
outdated, and nothing showed which ones did. Code has to name principles as typed values, but the dev reviews and
edits them as prose.

- **The page is the source.** Each principle's name, identifier and revision sit on the page, beside its wording.
  The code's principles are generated from the page, so code never declares a principle the page lacks. Everywhere
  else in the repository, documentation is generated from code; this is the one place where code is generated from
  documentation.
- **A revision per principle, not per page.** A reason records the revision of the principle it was judged under.
  A principle's revision rises when a reason judged under the old text could now be wrong; a clarification that
  changes no verdict keeps it. Raising a revision is the author's call, made on the line they are editing.
- **Stale is a state, not a fault.** A reason judged under an earlier revision is stale: listed for review like an
  unexamined one, never failing a build. A change to a principle is not held up by re-judging every kind it
  touches, which goes one kind at a time.
- **A removed principle breaks the build.** The reasons citing it stop resolving, and the change that removes it
  must re-point each one, or return it to unexamined. No retired principle lingers to keep them valid.

## Considered options

- **Code as the source, the page generated or checked against it.** A change to a principle would then be two
  edits in two files, and the revision would sit away from the words it versions. Generating the whole page from
  code would put paragraphs of prose, and the dev's review of them, into a data file.
- **The page read when the program runs.** The package would depend on its documentation folder being present.
- **A summary table of principles and revisions at the top of the page.** One file, but the revision sits away
  from the wording it versions, and is easy to leave behind.
- **One version for the whole page.** Any edit would mark every reason stale, including those resting on
  principles that did not change.
- **A revision computed from each principle's text.** A typo fix would mark reasons stale. A text hash is kept
  only to tell the author that the text changed while the revision did not.

Tracked in #711.
