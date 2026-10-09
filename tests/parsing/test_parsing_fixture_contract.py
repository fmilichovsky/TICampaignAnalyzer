"""Current parser-boundary behavior exercised through structured fragments."""

import json

import pytest

from tests.fixtures import fixture_path
from tinarrative.model.values import Unknown
from tinarrative.parsing.game_version import detect_game_version
from tinarrative.parsing.normalization import normalize
from tinarrative.parsing.raw_save import RawSave

FIXTURE_PARTS = ("io", "terra_invicta_json_v1")


def read_fragment(fixture_name: str) -> dict[str, object]:
    return json.loads(fixture_path(*FIXTURE_PARTS, fixture_name).read_text())


@pytest.mark.fixture
@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [
        ("known_game_version.json", "fixture-1.0"),
        ("numeric_game_version.json", "42"),
        ("absent_game_version.json", None),
    ],
)
def test_detect_game_version_keeps_its_current_minimal_contract(fixture_name: str, expected: str | None) -> None:
    assert detect_game_version(read_fragment(fixture_name)) == expected


def test_normalize_carries_source_and_version_from_the_raw_save() -> None:
    root: dict[str, object] = {"currentID": {"value": 1}, "gamestates": {}}
    raw = RawSave(source="fixture.json", format="terra_invicta_json_v1", game_version="x", root=root, size_bytes=2)
    snapshot = normalize(raw)
    assert (snapshot.source, snapshot.game_version, snapshot.date) == ("fixture.json", "x", Unknown())
