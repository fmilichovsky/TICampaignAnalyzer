# Testing and fixtures

Run the normal test suite locally with:

```powershell
python -m pip install -e ".[test]"
python -m pytest
```

Pytest discovers files named `test_*.py` below `tests/` and test functions or
`unittest.TestCase` methods whose names begin with `test_`. The same command is
run in CI. Tests marked `real_save` are excluded by default; use
`python -m pytest -m real_save` only when the optional, sanitized real-save
fixtures are present and you intentionally want to run those tests.

## Fixture layout and naming

Fixtures live under `tests/fixtures/<area>/<format-or-game-version>/`. Use
lowercase `snake_case` names that describe the scenario, rather than an
implementation detail. A raw save fixture, for example, is named
`minimal_save.save`, with its metadata in `minimal_save.save.json` beside it.
Expected rendered output may use `*.expected.md`; structured expected data may
use `*.expected.json`.

Tests must locate fixture files through `tests.fixture_path`, never through a
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
provenance, game-version status, expected raw-loader outcome, JSON validity,
SHA-256 hashes, and a per-file size limit.

Validate the set after every edit:

```powershell
python scripts/verify_fixture_manifest.py tests/fixtures/io/terra_invicta_json_v1/fixture_manifest.json
```

The representative document is complete as a JSON save envelope, not as a
game-loadable campaign. It is deliberately small and only preserves selected
wrapper and state-type shapes needed by tests.

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

Real complete saves are reserved for integration coverage of format details
that cannot be represented faithfully in a small fixture. Commit one only when
redistribution is explicitly permitted; document provenance, game version,
privacy review, and licensing; tag its tests `@pytest.mark.real_save`; and keep
it outside the default suite. Never commit unsanitized saves or saves whose
redistribution status is unclear.
