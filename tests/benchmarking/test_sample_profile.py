"""Coverage of the sample profile: the settings and save cadence a sample campaign records in samples.json."""

from __future__ import annotations

import lzma
from pathlib import Path

from tests.fixtures import fixture_path
from tinarrative.benchmarking.profile import PROFILE_FIELDS, STANDARD, read_samples, sample_profile

STANDARD_SAVES = ["settings_standard_early.json", "settings_standard_late.json"]


def compressed(tmp_path: Path, *names: str) -> list[Path]:
    files = []
    for name in names:
        file = tmp_path / f"{name}.xz"
        file.write_bytes(lzma.compress(fixture_path("io", "terra_invicta_json_v1", name).read_bytes()))
        files.append(file)
    return files


def profile_of(tmp_path: Path, *names: str) -> dict[str, object]:
    return sample_profile(read_samples(compressed(tmp_path, *names)))


def test_a_standard_campaign_has_its_settings_and_cadence(tmp_path: Path) -> None:
    profile = profile_of(tmp_path, *STANDARD_SAVES)

    assert profile == {
        "player_faction": "ResistCouncil",
        "difficulty": "Normal",
        "custom_difficulty": False,
        "scenario": "FullScenario/2026Scenario",
        "mods": False,
        "alien_progression_speed": 1.0,
        "research_speed": 1.0,
        "first_save": "2026-02-13",
        "last_save": "2026-08-01",
        "saves": 2,
        "longest_gap_days": 169,
        "non_standard": [],
    }
    assert tuple(profile) == PROFILE_FIELDS


def test_a_non_standard_campaign_names_what_departs_from_the_standard(tmp_path: Path) -> None:
    profile = profile_of(tmp_path, "settings_custom.json")

    assert profile["non_standard"] == [
        "custom_difficulty",
        "scenario",
        "factions",
        "mods",
        "alien_progression_speed",
        "research_speed",
    ]
    assert (profile["mods"], profile["alien_progression_speed"], profile["research_speed"]) == (True, 1.5, 0.5)


def test_a_setting_that_changes_between_saves_is_unknown_and_non_standard(tmp_path: Path) -> None:
    profile = profile_of(tmp_path, STANDARD_SAVES[0], "settings_custom.json")

    assert profile["scenario"] is None
    assert "scenario changes" in profile["non_standard"]  # type: ignore[operator]
    assert profile["mods"] is True


def test_an_unreadable_save_counts_but_carries_no_settings(tmp_path: Path) -> None:
    files = compressed(tmp_path, *STANDARD_SAVES)
    unreadable = tmp_path / "unreadable.json.xz"
    unreadable.write_bytes(lzma.compress(b"{}"))

    profile = sample_profile(read_samples([*files, unreadable]))

    assert profile == {**profile_of(tmp_path, *STANDARD_SAVES), "saves": 3}


def test_a_campaign_whose_saves_carry_no_setting_has_it_unknown_and_is_not_standard(tmp_path: Path) -> None:
    unreadable = tmp_path / "unreadable.json.xz"
    unreadable.write_bytes(lzma.compress(b"{}"))

    profile = sample_profile(read_samples([unreadable]))

    assert {
        field: profile[field] for field in PROFILE_FIELDS if field not in ("saves", "non_standard")
    } == dict.fromkeys(set(PROFILE_FIELDS) - {"saves", "non_standard"})
    assert profile["non_standard"] == [f"{field} unknown" for field in STANDARD]
