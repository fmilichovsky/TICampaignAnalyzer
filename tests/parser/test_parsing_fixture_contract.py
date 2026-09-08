"""Current parser-boundary behavior exercised through structured fragments."""

import json

import pytest

from tests.fixtures import fixture_path
from tinarrative.parsing.game_version import detect_game_version
from tinarrative.parsing.normalization import normalize


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
def test_detect_game_version_keeps_its_current_minimal_contract(
    fixture_name: str, expected: str | None
) -> None:
    assert detect_game_version(read_fragment(fixture_name)) == expected


@pytest.mark.fixture
def test_normalize_uses_current_date_and_missing_date_defaults() -> None:
    assert normalize(read_fragment("known_game_version.json"), source="fixture.json").date == "2030-01-01"
    assert normalize(read_fragment("absent_game_version.json"), source="fixture.json").date == "2030-01-03"
    assert normalize({}, source="fixture.json").date == "unknown"
