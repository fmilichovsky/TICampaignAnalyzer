# Testing

How to run and maintain the test suite. What a good test is, and the fixture rules, are in
[CONTRIBUTING.md](../CONTRIBUTING.md#tests).

## Running

`make check` runs the suite with formatting, linting and type checking; CI runs the same. Tests marked `real_save`
read private saves and are excluded by default; run them with `python -m pytest -m real_save` and these environment
variables:

- `TINARRATIVE_REAL_SAVE`: one save;
- `TINARRATIVE_REAL_SAVE_AFTER`: the later save of a consecutive pair;
- `TINARRATIVE_REAL_SAVE_SEQUENCE`: save paths separated by `os.pathsep`;
- `TINARRATIVE_REAL_SAVE_DIRECTORY`: a directory of saves, possibly of several campaigns.

## Fixtures

Fixtures live under `tests/fixtures/<area>/<format>/`, named in `snake_case` after the scenario they show. Locate
them with `tests.fixtures.fixture_path`, never with a path relative to the working directory:

```python
from tests.fixtures import fixture_path

save_path = fixture_path("io", "terra_invicta_json_v1", "representative_campaign.json")
```

Save-shaped fixtures are listed in `tests/fixtures/io/terra_invicta_json_v1/fixture_manifest.json` with their
purpose, hash, size limit, expected loader outcome and format assumptions. Shared builders for synthetic states,
snapshots and event streams live in `tests/<area>/support.py`.

### Deriving a fixture from a real save

1. Inspect the real save locally; never copy it into the repository or a shared workspace.
2. Hand-author the smallest JSON document that keeps the needed envelope, wrapper shape and state-type names.
3. Replace every name, ID, date, text value and nested content with synthetic equivalents, and review the result.
4. Add its manifest entry with its SHA-256, then run the verifier and the suite.

Redaction is manual because the save format is undocumented and changes between versions: an automated sanitizer
could miss private data and give false confidence.

## Checked-in expected outputs

Some tests compare against files that are generated, not written by hand. When a change alters one on purpose,
regenerate it, review the diff line by line, and commit it with the change.

- **Goldens** (`*.expected.*` under `tests/fixtures/`) hold a command's exact output on a fixture. Regenerate them
  all with `python -m pytest --update-goldens`, then review the diff. A golden without a test fails the suite.
- **The fixture manifest** records each fixture's hash. After editing a fixture, update its entry and run
  `python scripts/verify_fixture_manifest.py tests/fixtures/io/terra_invicta_json_v1/fixture_manifest.json`.
- **The unknowns registry** (`docs/game-data-notes/unknowns/registry.json`) is written by `tinarrative unknowns`.
  After extending `ENTITY_FIELDS`, `RECORD_FIELDS`, `ACKNOWLEDGED_FIELDS` or `KNOWN_STATE_TYPES`, refresh it from
  private saves:

  ```sh
  tinarrative unknowns /path/to/private/saves --registry docs/game-data-notes/unknowns/registry.json
  ```
