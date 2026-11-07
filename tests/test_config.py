"""Runtime settings: defaults, partial overrides from TOML and strict validation."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from tinarrative.config import (
    DEFAULT_SETTINGS,
    ConfigError,
    GeopoliticsSettings,
    NarratorSettings,
    PowerSettings,
    Settings,
    SignificanceSettings,
    load_settings,
    override,
)


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
        (
            "[narrative.geopolitics]\nmetric_shifts_max = -1\n",
            "'narrative.geopolitics.metric_shifts_max' must be at least 0",
        ),
        ("[narrative.geopolitics\n", "not valid TOML"),
        ("[narrative.significance]\nscale_min = 1\n", "'narrative.significance.scale_min' must be at most 0"),
        ("[narrative.significance]\nscale_min = -101\n", "'narrative.significance.scale_min' must be at least -100"),
        ("[narrative.significance]\nscale_max = 101\n", "'narrative.significance.scale_max' must be at most 100"),
        ("[narrative.significance]\nscale_max = -1\n", "'narrative.significance.scale_max' must be at least 0"),
        ("[narrative.significance]\ntier_exponent = 0\n", "'narrative.significance.tier_exponent' must be at least 1"),
        ("[narrative.significance.power]\nw_gdp = -0.5\n", "'narrative.significance.power.w_gdp' must be at least 0"),
        ("[narrative.significance.power]\nw_gdp = 1\n", "'narrative.significance.power' weights must sum to 1"),
        ("[councilors]\nrivals_per_faction = -1\n", "'councilors.rivals_per_faction' must be at least 0"),
        ("[councilors]\narticle_words = 0\n", "'councilors.article_words' must be at least 1"),
        ("[councilors]\nmin_tenure_days = 1.5\n", "'councilors.min_tenure_days' must be an integer"),
        ("[councilors]\nloyalty = 1\n", "unknown setting 'councilors.loyalty'"),
        ("[processing]\njobs = 0\n", "'processing.jobs' must be at least 1"),
        ("[processing]\njobs = 'auto'\n", "'processing.jobs' must be an integer"),
        (
            "[narrator]\nprovider = 'gemini'\n",
            "'narrator.provider' must be one of: anthropic, openai, openrouter, ollama",
        ),
        ("[narrator]\nmodel = 3\n", "'narrator.model' must be a non-empty string"),
        ("[narrator]\nmodel = ''\n", "'narrator.model' must be a non-empty string"),
        ("[narrator]\ntemperature = true\n", "'narrator.temperature' must be a number"),
        ("[narrator]\ntemperature = '0.5'\n", "'narrator.temperature' must be a number"),
        ("[narrator]\nchars_per_token = true\n", "'narrator.chars_per_token' must be a number"),
        ("[narrator]\nchars_per_token = 0.9\n", "'narrator.chars_per_token' must be at least 1.0"),
        (
            "[narrator.profiles.local]\nchars_per_token = 0.9\n",
            "'narrator.profiles.local.chars_per_token' must be at least 1.0",
        ),
        ("[narrator]\ntemperature = -0.1\n", "'narrator.temperature' must be at least 0.0"),
        ("[narrator]\ncontext_window = 0\n", "'narrator.context_window' must be at least 1"),
        ("[narrator]\nrequests_per_minute = 0\n", "'narrator.requests_per_minute' must be at least 1"),
        ("[narrator]\ntokens_per_minute = true\n", "'narrator.tokens_per_minute' must be an integer"),
        (
            "[narrator.profiles.local]\ntokens_per_minute = 0\n",
            "'narrator.profiles.local.tokens_per_minute' must be at least 1",
        ),
        ("[narrator]\nprofiles = 3\n", "'narrator.profiles' must be a table"),
        ("[narrator.profiles]\nlocal = 3\n", "'narrator.profiles.local' must be a table"),
        ("[narrator.profiles.local]\ntop_economies = 3\n", "unknown setting 'narrator.profiles.local.top_economies'"),
        ("[narrator.profiles.local]\nmax_input_tokens = 10\n", "'narrator.profiles.local.max_input_tokens' must be at"),
        ("[narrator.profiles.local]\nprovider = 'x'\n", "'narrator.profiles.local.provider' must be one of"),
    ],
)
def test_invalid_settings_name_the_key(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ConfigError, match=re.escape(message)):
        load_settings(write(tmp_path, text))


def test_the_significance_scale_clamp_defaults_and_overrides(tmp_path: Path) -> None:
    assert DEFAULT_SETTINGS.narrative.significance == SignificanceSettings(scale_min=-20, scale_max=15)
    settings = load_settings(write(tmp_path, "[narrative.significance]\nscale_min = -100\nscale_max = 0\n"))
    assert settings.narrative.significance == SignificanceSettings(scale_min=-100, scale_max=0)
    assert settings.differences(DEFAULT_SETTINGS) == {
        "narrative.significance.scale_min": -100,
        "narrative.significance.scale_max": 0,
    }


def test_processing_jobs_is_unset_by_default_and_overridable(tmp_path: Path) -> None:
    assert DEFAULT_SETTINGS.processing.jobs is None
    settings = load_settings(write(tmp_path, "[processing]\njobs = 3\n"))
    assert settings.processing.jobs == 3
    assert settings.differences(DEFAULT_SETTINGS) == {"processing.jobs": 3}


def test_councilor_settings_override_the_defaults(tmp_path: Path) -> None:
    settings = load_settings(write(tmp_path, "[councilors]\nrivals_per_faction = 4\nmin_tenure_days = 0\n"))
    assert settings.differences(DEFAULT_SETTINGS) == {
        "councilors.rivals_per_faction": 4,
        "councilors.min_tenure_days": 0,
    }


def test_a_missing_file_is_an_os_error(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        load_settings(tmp_path / "absent.toml")


def test_provider_keys_and_profiles(tmp_path: Path) -> None:
    text = (
        "[narrator]\nprovider = 'anthropic'\nmodel = 'hosted'\napi_key_env = 'KEY_VAR'\ntemperature = 1\n"
        "[narrator.profiles.local]\nprovider = 'ollama'\nmodel = 'small'\nmax_input_tokens = 24000\n"
        "context_window = 32768\ntemperature = 0.25\n"
    )

    narrator = load_settings(write(tmp_path, text)).narrator
    local = narrator.with_profile("local")

    assert (narrator.provider, narrator.model, narrator.temperature) == ("anthropic", "hosted", 1.0)
    assert isinstance(narrator.temperature, float)
    assert (local.provider, local.model, local.max_input_tokens, local.context_window) == (
        "ollama",
        "small",
        24000,
        32768,
    )
    assert (local.api_key_env, local.temperature, local.top_economies) == ("KEY_VAR", 0.25, narrator.top_economies)
    assert local.profiles == narrator.profiles
    with pytest.raises(KeyError):
        narrator.with_profile("absent")


def test_profile_rate_limits_override_or_inherit_global_limits(tmp_path: Path) -> None:
    narrator = load_settings(
        write(
            tmp_path,
            "[narrator]\nrequests_per_minute = 20\ntokens_per_minute = 50000\n"
            "[narrator.profiles.local]\nrequests_per_minute = 4\n",
        )
    ).narrator

    local = narrator.with_profile("local")

    assert (local.requests_per_minute, local.tokens_per_minute) == (4, 50000)


def test_chars_per_token_accepts_fractional_and_integer_values(tmp_path: Path) -> None:
    fractional = load_settings(write(tmp_path, "[narrator]\nchars_per_token = 2.4\n"))
    integer = load_settings(write(tmp_path, "[narrator]\nchars_per_token = 2\n"))
    profile = load_settings(write(tmp_path, "[narrator.profiles.local]\nchars_per_token = 2.25\n"))

    assert DEFAULT_SETTINGS.narrator.chars_per_token == 2.4
    assert fractional.narrator.chars_per_token == 2.4
    assert integer.narrator.chars_per_token == 2.0
    assert integer.narrator.chars_per_token.__class__ is float
    assert profile.narrator.with_profile("local").chars_per_token == 2.25


def test_unset_keys_are_left_out_of_the_tables() -> None:
    narrator = DEFAULT_SETTINGS.to_dict()["narrator"]

    assert NarratorSettings().model is None
    assert not {"provider", "model", "base_url", "api_key_env", "context_window", "temperature"} & set(narrator)
    assert narrator["profiles"] == {}


def test_override_validates_like_a_settings_file() -> None:
    narrator = override(NarratorSettings(), "max_output_tokens", 500)

    assert narrator.max_output_tokens == 500
    with pytest.raises(ConfigError, match="'narrator.max_input_tokens' must be at least 1000"):
        override(narrator, "max_input_tokens", 10)


def test_the_power_weights_default_to_thirds_and_override_together(tmp_path: Path) -> None:
    significance = DEFAULT_SETTINGS.narrative.significance
    assert (significance.power, significance.tier_exponent) == (PowerSettings(1 / 3, 1 / 3, 1 / 3), 2)
    text = (
        "[narrative.significance]\ntier_exponent = 3\n"
        "[narrative.significance.power]\nw_gdp = 0.5\nw_pop = 0.25\nw_str = 0.25\n"
    )
    settings = load_settings(write(tmp_path, text))
    assert settings.narrative.significance.power == PowerSettings(0.5, 0.25, 0.25)
    assert settings.narrative.significance.tier_exponent == 3


def test_the_reference_shares_default_to_one_percent_and_override(tmp_path: Path) -> None:
    reference = DEFAULT_SETTINGS.narrative.significance.reference
    assert (reference.power, reference.population, reference.organization, reference.nuclear_bonus) == (
        0.01,
        0.01,
        0.01,
        5,
    )
    text = "[narrative.significance.reference]\npower = 0.02\nnuclear_bonus = 0\n"
    settings = load_settings(write(tmp_path, text))
    assert settings.differences(DEFAULT_SETTINGS) == {
        "narrative.significance.reference.power": 0.02,
        "narrative.significance.reference.nuclear_bonus": 0,
    }
    with pytest.raises(ConfigError, match="'narrative.significance.reference.power' must be at least"):
        load_settings(write(tmp_path, "[narrative.significance.reference]\npower = 0\n"))
