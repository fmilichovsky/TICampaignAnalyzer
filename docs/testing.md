# Testing and fixtures

Run the normal test suite locally, from an activated virtual environment (see
[Development](../README.md#development)), with:

```sh
python -m pip install -e ".[test]"
python -m pytest
```

Pytest discovers files named `test_*.py` below `tests/` and test functions or
`unittest.TestCase` methods whose names begin with `test_`. The same command is
run in CI. Tests marked `real_save` are excluded by default; they read a
private save from the `TINARRATIVE_REAL_SAVE` environment variable and run with
`python -m pytest -m real_save`.

## Fixture layout and naming

Fixtures live under `tests/fixtures/<area>/<format-or-game-version>/`. Use
lowercase `snake_case` names that describe the scenario, rather than an
implementation detail. A raw save fixture, for example, is named
`minimal_save.save`, with its metadata in `minimal_save.save.json` beside it.
Expected rendered output may use `*.expected.md`; structured expected data may
use `*.expected.json`.

Tests must locate fixture files through `tests.fixtures.fixture_path`, never through a
current-working-directory-relative path. This keeps local, CI, and IDE runs
equivalent:

```python
from tests.fixtures import fixture_path

save_path = fixture_path("io", "v0", "minimal_save.save")
```

## Fixture metadata

Every non-text fixture has a sidecar JSON file using the fixture filename plus
`.json`. It records at least:

- `kind`: the data type, such as `raw_save` or `normalized_snapshot`;
- `synthetic`: whether the fixture was created for the test;
- `source`: `generated` for synthetic data, otherwise a traceable provenance;
- `game_version`: a game version string or `null` when it does not apply;
- `purpose`: the behavior the fixture protects.

Do not put player names, machine paths, account identifiers, or other personal
data in fixture metadata.

## Versioned Terra Invicta JSON fixture sets

Versioned, save-shaped JSON fixtures live under
`tests/fixtures/io/terra_invicta_json_v1/`. Their `fixture_manifest.json` is
the canonical set-level metadata: it records the fixture-set version,
provenance, game-version status, expected loader outcome (`raw_save`, `malformed_save_error`,
`unsupported_shape_error`, or `unsupported_version_error`, checked against
`parse_raw_save` by `tests/parsing/test_raw_save.py`), JSON validity,
SHA-256 hashes, and a per-file size limit. Every entry also declares a
`format_assumption`, `format_documentation`, and `version_assumption`. The
format assumption must be a documented supported envelope identifier, and its
documentation path is verified; the version assumption explains
whether the fixture represents observed missing-version behavior or a
synthetic detector edge case. See `docs/game-data-notes/` before adding or
changing either field.

Validate the set after every edit:

```sh
python scripts/verify_fixture_manifest.py tests/fixtures/io/terra_invicta_json_v1/fixture_manifest.json
```

The representative document is complete as a JSON save envelope, not as a
game-loadable campaign. It is deliberately small and only preserves selected
wrapper and state-type shapes needed by tests.

## Expected `inspect` reports

`tests/fixtures/inspection/<fixture-set>/<fixture-name>.expected.txt` holds the
exact text that `tinarrative inspect` must print for the fixture of the same
name under `tests/fixtures/io/<fixture-set>/`. These files live outside the
manifest-governed directory on purpose; a test checks that every expected
report maps to an existing fixture.

When the report format changes deliberately, regenerate a golden by running
the command on the fixture, review the diff line by line, and commit both
together:

```sh
tinarrative inspect tests/fixtures/io/terra_invicta_json_v1/representative_campaign.json > tests/fixtures/inspection/terra_invicta_json_v1/representative_campaign.json.expected.txt
```

Real saves must never be added here. The opt-in `real_save` test reads the
save location from the `TINARRATIVE_REAL_SAVE` environment variable instead.

## Expected `diff` reports

`tests/fixtures/diff/<fixture-set>/<before-name>__<after-name>.expected.txt` and `.expected.json`
hold the exact text and JSON that `tinarrative diff` must print for the fixture pair of
those names under `tests/fixtures/io/<fixture-set>/`. The goldens are produced from
inside the fixture directory with bare file names, so they contain no machine paths:

```sh
cd tests/fixtures/io/terra_invicta_json_v1
tinarrative diff interval_before.json interval_after.json > ../../diff/terra_invicta_json_v1/interval_before.json__interval_after.json.expected.txt
tinarrative diff --format json interval_before.json interval_after.json > ../../diff/terra_invicta_json_v1/interval_before.json__interval_after.json.expected.json
```

Review a regenerated golden line by line and commit it with the change that altered it.
The pair is hand-authored so that each `ChangeKind` (value, membership, map, unknown,
appeared, disappeared) occurs at least once; a test asserts that.

The opt-in `real_save` diff test additionally needs `TINARRATIVE_REAL_SAVE_AFTER`, the later
save of a consecutive pair; it checks determinism and evidence only and prints nothing.

### Deriving a safe structural fixture

1. Inspect a real save locally; never copy it into the repository or a shared
   workspace.
2. Hand-author the smallest JSON document that preserves the needed envelope,
   wrapper shape, and state-type names.
3. Replace every name, ID, date, text value, and nested content with synthetic
   equivalents. Review the result before committing it.
4. Add its manifest entry, record its expected JSON validity and raw-loader
   outcome, update its SHA-256, and run the verifier and pytest.

Do not use an automated sanitizer for this work. The save format is
undocumented and version-dependent, so automatic redaction could miss private
or campaign-specific data and create false confidence.

## Synthetic and real-save policy

Prefer the smallest synthetic fixture that makes a test meaningful. Synthetic
fixtures, including hand-authored structural derivatives of a real save, are
checked in and run by default. They must not contain original campaign data.

Real saves are never committed, sanitized or not. Tests that need one are
tagged `@pytest.mark.real_save`, stay outside the default suite, and locate the
save through `TINARRATIVE_REAL_SAVE`.

## Unknowns registry

`docs/game-data-notes/unknowns/registry.json` is machine-written by
`tinarrative unknowns` from private saves and committed; it contains state-type
and field names, JSON shapes, counts and dates only (see
[its README](game-data-notes/unknowns/README.md)).
`tests/maintenance/test_committed_registry.py` runs in the default suite and
fails when the file is not canonical, holds an unsafe string, or lists an entry
the schema now covers. After extending `ENTITY_FIELDS`, `RECORD_FIELDS`,
`ACKNOWLEDGED_FIELDS` or `KNOWN_STATE_TYPES`, refresh it locally:

```sh
tinarrative unknowns /path/to/private/saves --registry docs/game-data-notes/unknowns/registry.json
```

Review the diff before committing; never edit entries by hand.
