"""Runtime settings: defaults, partial overrides from TOML and strict validation."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from tinarrative.config import DEFAULT_SETTINGS, ConfigError, GeopoliticsSettings, Settings, load_settings


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "settings.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_no_file_gives_the_defaults() -> None:
    assert load_settings(None) is DEFAULT_SETTINGS
    assert DEFAULT_SETTINGS.narrative.geopolitics == GeopoliticsSettings()
    assert DEFAULT_SETTINGS.to_dict()["narrative"]["geopolitics"]["top_gdp_nations"] == 10
    assert DEFAULT_SETTINGS.differences(Settings()) == {}


def test_the_example_file_names_every_key_at_its_default() -> None:
    example = Path(__file__).resolve().parents[1] / "docs" / "configuration.example.toml"

    assert load_settings(example) == DEFAULT_SETTINGS
    assert tomllib.loads(example.read_text(encoding="utf-8")) == DEFAULT_SETTINGS.to_dict()


def test_a_partial_file_overrides_only_the_keys_it_names(tmp_path: Path) -> None:
    settings = load_settings(write(tmp_path, "[narrative.geopolitics]\ntop_gdp_nations = 3\nledger_window_days = 0\n"))

    geopolitics = settings.narrative.geopolitics
    assert (geopolitics.top_gdp_nations, geopolitics.ledger_window_days) == (3, 0)
    assert geopolitics.expansion_gap_days == GeopoliticsSettings().expansion_gap_days
    assert settings.differences(DEFAULT_SETTINGS) == {
        "narrative.geopolitics.ledger_window_days": 0,
        "narrative.geopolitics.top_gdp_nations": 3,
    }


def test_an_empty_file_is_the_defaults(tmp_path: Path) -> None:
    assert load_settings(write(tmp_path, "")) == DEFAULT_SETTINGS


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[narrative.geopolitic]\ntop_gdp_nations = 3\n", "unknown setting 'narrative.geopolitic'"),
        ("[narrative.geopolitics]\ntop_gdp = 3\n", "unknown setting 'narrative.geopolitics.top_gdp'"),
        ("narrative = 3\n", "'narrative' must be a table"),
        ("[narrative.geopolitics]\ntop_gdp_nations = true\n", "must be an integer"),
        ("[narrative.geopolitics]\ntop_gdp_nations = '3'\n", "must be an integer"),
        ("[narrative.geopolitics]\ntop_gdp_nations = 2.5\n", "must be an integer"),
        (
            "[narrative.geopolitics]\ntop_gdp_nations = 0\n",
            "'narrative.geopolitics.top_gdp_nations' must be at least 1",
        ),
        ("[narrative.geopolitics]\nexpansion_gap_days = -1\n", "must be at least 0"),
        ("[narrative.geopolitics\n", "not valid TOML"),
    ],
)
def test_invalid_settings_name_the_key(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ConfigError, match=re.escape(message)):
        load_settings(write(tmp_path, text))


def test_a_missing_file_is_an_os_error(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        load_settings(tmp_path / "absent.toml")
