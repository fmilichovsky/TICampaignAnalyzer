import pytest

from tinarrative.parsing.game_version import (
    UnsupportedGameVersionError,
    UnsupportedSaveFormatError,
    detect_game_version,
    require_supported_format,
    require_supported_game_version,
)


def test_missing_game_version_is_the_documented_observed_case() -> None:
    assert require_supported_game_version({}) is None


@pytest.mark.parametrize("raw_save", [{"game_version": "future-build"}, {"game_version": 42}])
def test_explicit_unsupported_game_versions_fail_clearly(
    raw_save: dict[str, object],
) -> None:
    with pytest.raises(UnsupportedGameVersionError, match="Unsupported Terra Invicta game version"):
        require_supported_game_version(raw_save)


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


def test_global_values_save_version_is_detected_when_the_envelope_has_none() -> None:
    assert detect_game_version(_with_save_version("1.2.3")) == "1.2.3"


def test_envelope_game_version_wins_over_the_global_values_one() -> None:
    assert detect_game_version(_with_save_version("1.2.3", game_version="envelope-build")) == "envelope-build"


@pytest.mark.parametrize("version", [None, 3, ["1.2.3"]])
def test_non_string_save_version_is_not_detected(version: object) -> None:
    assert detect_game_version(_with_save_version(version)) is None


@pytest.mark.parametrize(
    "root",
    [{}, {"gamestates": []}, {"gamestates": {"PavonisInteractive.TerraInvicta.TIGlobalValuesState": {}}}],
)
def test_absent_or_malformed_singleton_detects_nothing(root: dict[str, object]) -> None:
    assert detect_game_version(root) is None


def test_global_values_save_version_is_reported_but_not_gated() -> None:
    assert require_supported_game_version(_with_save_version("1.2.3")) is None
