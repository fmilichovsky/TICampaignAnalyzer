# The councilor brief is the only layer that rewords

A councilor article is told from a councilor brief, not from the dossier. The dossier stays the audit artifact;
the brief is what the model reads.

- **The dossier holds game names, measurements and classifications.** It stays close to the game data, so a
  reader can check an article against the save it came from.
- **Classification stays in the dossier.** Organization category and origin, trait groups and the groups withheld,
  policy shares and mission counting are judgements about the data, made once and auditable.
- **The brief is the only place where wording, banding and omission happen.** Labels become plain phrases, numbers
  become words, and fields the article must not use are left out before the model sees them. What must never
  appear in an article is removed rather than forbidden by the prompt.
- **The brief is not a file of its own.** It is what the request embeds, so it is inspectable in the run
  directory's requests, and the requests stay a function of the dossier alone.

The cost is accepted: once the existing translations and bands move into the brief, `dossier.json` reads less
plainly to a person.

## Considered options

- **Forbidding audit fields in the prompt.** It was rejected because a model quotes what it is shown, budget
  models most of all, and every forbidden field costs prompt lines.
- **Rewording inside the dossier.** It was rejected because the audit artifact would drift from the game data, and
  modifications would be split between two layers.
- **A separate brief file in the run directory.** It was rejected because the request already holds the brief, and
  a second copy could disagree with it.

Tracked in #395.
