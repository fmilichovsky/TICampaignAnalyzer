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

## Synthetic and real-save policy

Prefer the smallest synthetic fixture that makes a test meaningful. Synthetic
fixtures are checked in, run by default, and should isolate one parser, diff,
or analyzer behavior. Real saves are reserved for integration coverage of
format details that cannot be represented faithfully in a small fixture. They
must be sanitized, documented with provenance and game version, and tagged
`@pytest.mark.real_save`. Do not commit unsanitized saves or saves whose
redistribution is not permitted. The default suite must not require real-save
fixtures.
