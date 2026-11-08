import gzip
import json

import pytest

from tests.fixtures import fixture_path
from tinarrative.parsing.errors import (
    MalformedSaveError,
    SaveLoadError,
    UnsupportedSaveFormatError,
    UnsupportedSaveShapeError,
)
from tinarrative.parsing.raw_save import parse_raw_save

FIXTURE_PARTS = ("io", "terra_invicta_json_v1")
OUTCOME_ERRORS: dict[str, type[SaveLoadError] | None] = {
    "raw_save": None,
    "malformed_save_error": MalformedSaveError,
    "unsupported_shape_error": UnsupportedSaveShapeError,
}
VALID = b'{"currentID": {"value": 1}, "gamestates": {}}'


def test_every_fixture_matches_its_declared_loader_outcome() -> None:
    manifest = json.loads(fixture_path(*FIXTURE_PARTS, "fixture_manifest.json").read_text())
    for entry in manifest["fixtures"]:
        data = fixture_path(*FIXTURE_PARTS, entry["path"]).read_bytes()
        expected = OUTCOME_ERRORS[entry["expected_loader_outcome"]]
        if expected is None:
            assert parse_raw_save(data, source=entry["path"]).source == entry["path"]
        else:
            with pytest.raises(expected):
                parse_raw_save(data, source=entry["path"])


def test_supported_fixture_decodes_to_raw_save() -> None:
    data = fixture_path(*FIXTURE_PARTS, "representative_campaign.json").read_bytes()

    raw = parse_raw_save(data, source="saves/a.json")

    assert (raw.source, raw.format, raw.game_version, raw.size_bytes) == (
        "saves/a.json",
        "terra_invicta_json_v1",
        None,
        len(data),
    )
    assert list(raw.root) == ["currentID", "gamestates"]


def test_unknown_state_types_are_not_rejected() -> None:
    data = fixture_path(*FIXTURE_PARTS, "unknown_state_type.json").read_bytes()
    assert "Example.ModOrFutureState" in parse_raw_save(data, source="s").root["gamestates"]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (gzip.compress(VALID), "gzip"),
        (b"PK\x03\x04rest", "zip"),
        (VALID.decode().encode("utf-16"), "UTF-16"),
        (b"\xef\xbb\xbf" + VALID, "byte-order mark"),
        (b'{"currentID": \xff}', "not valid UTF-8"),
        (b'{"currentID": ', "line 1, column 15"),
    ],
)
def test_malformed_bytes_fail_with_specific_messages(data: bytes, message: str) -> None:
    with pytest.raises(MalformedSaveError, match=message):
        parse_raw_save(data, source="s")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"[]", "root is list"),
        (b'{"gamestates": {}}', "'currentID'"),
        (b'{"currentID": {}}', "'gamestates'"),
        (b'{"currentID": {}, "gamestates": []}', "not an object"),
    ],
)
def test_unsupported_shapes_fail_with_specific_messages(data: bytes, message: str) -> None:
    with pytest.raises(UnsupportedSaveShapeError, match=message):
        parse_raw_save(data, source="s")


def test_unsupported_format_is_a_typed_error() -> None:
    with pytest.raises(UnsupportedSaveFormatError):
        parse_raw_save(VALID, source="s", format="terra_invicta_json_v999")
