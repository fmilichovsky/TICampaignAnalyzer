import pytest

from tinarrative.parsing.game_version import (
    UnsupportedGameVersionError,
    UnsupportedSaveFormatError,
    detect_game_version,
    require_supported_format,
    require_supported_game_version,
)


def test_detect_game_version_returns_a_string_for_numeric_values() -> None:
    assert detect_game_version({"game_version": 42}) == "42"


def test_missing_game_version_is_the_documented_observed_case() -> None:
    assert require_supported_game_version({}) is None


@pytest.mark.parametrize("raw_save", [{"game_version": "future-build"}, {"game_version": 42}])
def test_explicit_unsupported_game_versions_fail_clearly(raw_save: dict[str, object]) -> None:
    with pytest.raises(UnsupportedGameVersionError, match="Unsupported Terra Invicta game version"):
        require_supported_game_version(raw_save)


def test_unknown_save_format_fails_clearly() -> None:
    with pytest.raises(UnsupportedSaveFormatError, match="Unsupported save format 'terra_invicta_json_v999'"):
        require_supported_format("terra_invicta_json_v999")


def test_documented_save_format_is_accepted() -> None:
    assert require_supported_format("terra_invicta_json_v1") == "terra_invicta_json_v1"
