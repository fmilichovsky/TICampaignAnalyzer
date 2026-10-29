# Testing and fixtures

Run the suite from an activated virtual environment (see [Development](../README.md#development)):

```sh
python -m pip install -e ".[test]"
python -m pytest
```

CI runs the same command. Tests marked `real_save` read private saves and are excluded by default; run them
with `python -m pytest -m real_save` and these environment variables:

- `TINARRATIVE_REAL_SAVE`: one save;
- `TINARRATIVE_REAL_SAVE_AFTER`: the later save of a consecutive pair;
- `TINARRATIVE_REAL_SAVE_SEQUENCE`: save paths separated by `os.pathsep`;
- `TINARRATIVE_REAL_SAVE_DIRECTORY`: a directory of saves, possibly of several campaigns.

## Fixtures

Fixtures live under `tests/fixtures/<area>/<format-or-game-version>/`, named in `snake_case` after the scenario
they show. Locate them through `tests.fixtures.fixture_path`, never with a path relative to the working directory:

```python
from tests.fixtures import fixture_path

save_path = fixture_path("io", "v0", "minimal_save.save")
```

Every non-text fixture has a `<name>.json` sidecar with `kind`, `synthetic`, `source`, `game_version` and
`purpose`. A fixture's purpose is stated there or in its manifest entry, not in this document. Shared builders
for synthetic states, snapshots and event streams live in `tests/<area>/support.py`.

### Versioned JSON fixture set

`tests/fixtures/io/terra_invicta_json_v1/fixture_manifest.json` governs the save-shaped fixtures: hashes, size
limits, expected loader outcome and format/version assumptions (see `docs/game-data-notes/` before changing
those). Validate after every edit:

```sh
python scripts/verify_fixture_manifest.py tests/fixtures/io/terra_invicta_json_v1/fixture_manifest.json
```

### Golden outputs

Goldens hold the exact output of a command on a fixture. When a format changes on purpose, regenerate the golden,
review the diff line by line, and commit it with the change. Run the commands from inside the fixture directory
with bare file names, so the goldens hold no machine paths:

```sh
cd tests/fixtures/io/terra_invicta_json_v1
tinarrative save inspect representative_campaign.json \
  > ../../inspection/terra_invicta_json_v1/representative_campaign.json.expected.txt
tinarrative save diff interval_before.json interval_after.json \
  > ../../diff/terra_invicta_json_v1/interval_before.json__interval_after.json.expected.txt
tinarrative save diff --format json interval_before.json interval_after.json \
  > ../../diff/terra_invicta_json_v1/interval_before.json__interval_after.json.expected.json
tinarrative events politics_reverted.json politics_before.json politics_after.json --narrative \
  --constituents evidence --format json \
  | python ../../../../scripts/narrator_prompt.py --period quarter --audience public \
  | python -c "import json,sys; print(json.dumps(json.load(sys.stdin)['messages'], ensure_ascii=False, indent=2))" \
  > ../../sequence/terra_invicta_json_v1/politics_sequence.expected.narrator_messages.json
```

### Deriving a safe structural fixture

1. Inspect a real save locally; never copy it into a fixture or a shared workspace.
2. Hand-author the smallest JSON document that keeps the needed envelope, wrapper shape and state-type names.
3. Replace every name, ID, date, text value and nested content with synthetic equivalents, and review the result.
4. Add its manifest entry, update its SHA-256, and run the verifier and pytest.

Do not use an automated sanitizer. The save format is undocumented and changes between versions, so automatic
redaction could miss private data and give false confidence.

## Real saves

Real saves are never fixtures, sanitized or not. The only committed real saves are the benchmark samples in
`benchmarks/samples/`, used to measure package size; adding one follows
[benchmarks/README.md](../benchmarks/README.md#samples).

## Unknowns registry

`docs/game-data-notes/unknowns/registry.json` is machine-written and checked by
`tests/maintenance/test_committed_registry.py`. After extending `ENTITY_FIELDS`, `RECORD_FIELDS`,
`ACKNOWLEDGED_FIELDS` or `KNOWN_STATE_TYPES`, refresh it and review the diff:

```sh
tinarrative unknowns /path/to/private/saves --registry docs/game-data-notes/unknowns/registry.json
```
