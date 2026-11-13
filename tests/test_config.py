"""Public settings schema, defaults, partial overrides and strict validation."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from tinarrative.config import DEFAULT_SETTINGS, ConfigError, load_settings, override


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "settings.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_example_is_the_defaults() -> None:
    example = Path(__file__).resolve().parents[1] / "docs" / "configuration.example.toml"
    assert load_settings(example) == DEFAULT_SETTINGS
    assert tomllib.loads(example.read_text(encoding="utf-8")) == DEFAULT_SETTINGS.to_dict()


def test_grouped_settings_and_profile(tmp_path: Path) -> None:
    settings = load_settings(
        write(
            tmp_path,
            '[events]\nepisode_gap_days=500\ntop_nations=25\nrecalled_narrative_events=12\n[llm]\nmodel="cloud"\n[llm.profiles.local]\nmodel="local"\n[councilors]\nmin_tenure_days=200\narticle_words=420\n',
        )
    )
    assert settings.narrative.geopolitics.expansion_gap_days == 500
    assert settings.narrative.space.campaign_gap_days == 500
    assert settings.narrator.recalled_narrative_events == 12
    assert settings.narrator.with_profile("local").model == "local"
    assert settings.councilors.article_words == 420
    assert settings.councilors.min_tenure_days == 200
    assert set(settings.to_dict()) == {"events", "llm", "councilors", "processing"}


@pytest.mark.parametrize(
    "text,key",
    [
        ("[events]\nnope=1\n", "events.nope"),
        ("[llm]\nrecalled_narrative_events=40\n", "llm.recalled_narrative_events"),
        ("[llm]\nnope=1\n", "llm.nope"),
    ],
)
def test_unknown_and_misplaced_keys_are_rejected(tmp_path: Path, text: str, key: str) -> None:
    with pytest.raises(ConfigError, match=re.escape(key)):
        load_settings(write(tmp_path, text))


def test_event_value_validation(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="events.episode_gap_days"):
        load_settings(write(tmp_path, "[events]\nepisode_gap_days=-1\n"))
    with pytest.raises(ConfigError, match="events.top_nations"):
        load_settings(write(tmp_path, "[events]\ntop_nations=0\n"))
    with pytest.raises(ConfigError, match="events.recalled_narrative_events"):
        load_settings(write(tmp_path, "[events]\nrecalled_narrative_events=-1\n"))


def test_llm_profile_validation_and_inheritance(tmp_path: Path) -> None:
    settings = load_settings(
        write(
            tmp_path,
            '[llm]\nprovider="openai"\nmodel="main"\nrequests_per_minute=20\n[llm.profiles.local]\nprovider="ollama"\nmodel="small"\n',
        )
    )
    local = settings.narrator.with_profile("local")
    assert (local.provider, local.model, local.requests_per_minute) == ("ollama", "small", 20)
    with pytest.raises(ConfigError, match="llm.provider"):
        load_settings(write(tmp_path, '[llm]\nprovider="bad"\n'))


def test_top_nations_is_capped(tmp_path: Path) -> None:
    def ranking(top: int) -> int:
        return load_settings(write(tmp_path, f"[events]\ntop_nations={top}\n")).narrative.nation_metrics.ranking_top_n

    assert ranking(5) == 5
    assert ranking(25) == ranking(1000) < 25


def test_no_file_gives_the_defaults_and_an_override_replaces_one_field() -> None:
    assert load_settings(None) is DEFAULT_SETTINGS
    assert override(DEFAULT_SETTINGS.narrator, "max_input_tokens", 1000).max_input_tokens == 1000


def test_w_space_is_an_events_setting_between_zero_and_one(tmp_path: Path) -> None:
    assert load_settings(write(tmp_path, "[events]\nw_space=0.25\n")).narrative.significance.w_space == 0.25
    for bad in ("1.5", "-0.1", "true"):
        with pytest.raises(ConfigError, match="events.w_space"):
            load_settings(write(tmp_path, f"[events]\nw_space={bad}\n"))
