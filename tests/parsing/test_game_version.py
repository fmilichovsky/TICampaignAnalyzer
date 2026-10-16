import pytest

from tinarrative.parsing.game_version import (
    UnsupportedSaveFormatError,
    detect_game_version,
    require_supported_format,
)


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


def test_a_top_level_game_version_member_is_ignored() -> None:
    assert detect_game_version(_with_save_version("1.2.3", game_version="envelope-build")) == "1.2.3"
    assert detect_game_version({"game_version": "envelope-build"}) is None


@pytest.mark.parametrize("version", [None, 3, ["1.2.3"]])
def test_non_string_save_version_is_not_detected(version: object) -> None:
    assert detect_game_version(_with_save_version(version)) is None


@pytest.mark.parametrize(
    "root",
    [{}, {"gamestates": []}, {"gamestates": {"PavonisInteractive.TerraInvicta.TIGlobalValuesState": {}}}],
)
def test_absent_or_malformed_singleton_detects_nothing(root: dict[str, object]) -> None:
    assert detect_game_version(root) is None
