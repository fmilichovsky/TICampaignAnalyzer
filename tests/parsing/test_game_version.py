import pytest

from tests.fixtures import fixture_path
from tinarrative.io.save_loader import load_raw_save
from tinarrative.parsing.game_version import (
    UnsupportedSaveFormatError,
    detect_game_version,
    require_supported_format,
)
from tinarrative.parsing.normalization import normalize


def test_unknown_save_format_fails_clearly() -> None:
    with pytest.raises(
        UnsupportedSaveFormatError,
        match="Unsupported save format 'terra_invicta_json_v999'",
    ):
        require_supported_format("terra_invicta_json_v999")


def test_documented_save_format_is_accepted() -> None:
    assert require_supported_format("terra_invicta_json_v1") == "terra_invicta_json_v1"


def _with_save_version(version: object, **envelope: object) -> dict[str, object]:
    value = {"latestSaveVersion": version}
    entry = {"Key": {"value": 7}, "Value": value}
    return {**envelope, "gamestates": {"PavonisInteractive.TerraInvicta.TIGlobalValuesState": [entry]}}


def test_global_values_save_version_is_detected() -> None:
    assert detect_game_version(_with_save_version("1.2.3")) == "1.2.3"


@pytest.mark.parametrize("version", [None, 3, ["1.2.3"]])
def test_non_string_save_version_is_not_detected(version: object) -> None:
    assert detect_game_version(_with_save_version(version)) is None


@pytest.mark.parametrize(
    "root",
    [{}, {"gamestates": []}, {"gamestates": {"PavonisInteractive.TerraInvicta.TIGlobalValuesState": {}}}],
)
def test_absent_or_malformed_singleton_detects_nothing(root: dict[str, object]) -> None:
    assert detect_game_version(root) is None


def test_a_loaded_save_carries_its_build_string() -> None:
    raw = load_raw_save(fixture_path("io", "terra_invicta_json_v1", "global_values_after.json"))
    assert raw.game_version == "fixture-build-2"
    assert normalize(raw).game_version == "fixture-build-2"
