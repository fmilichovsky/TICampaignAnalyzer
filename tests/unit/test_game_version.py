from tinarrative.parsing.game_version import detect_game_version


def test_detect_game_version_returns_a_string_for_numeric_values() -> None:
    assert detect_game_version({"game_version": 42}) == "42"
