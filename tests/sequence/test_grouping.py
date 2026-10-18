"""Campaign grouping and selection over synthetic variants of the politics saves."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from tests.sequence.campaign_variants import OTHER_FACTION, POLITICS, write_campaign, write_variant
from tinarrative.grouping import CampaignGroup, group_saves, render_listing, select_campaign, slug
from tinarrative.sequence import survey

START_A = datetime(2026, 1, 4, 11, 37, 51)
START_B = datetime(2026, 10, 14, 15, 26, 24)


def grouped(*paths: Path) -> tuple[CampaignGroup, ...]:
    return group_saves(survey(path) for path in paths)


def sources(group: CampaignGroup) -> list[str]:
    return [Path(save.source).name for save in group.saves]


@pytest.mark.fixture
def test_one_campaign_forms_one_group_with_its_signals(tmp_path: Path) -> None:
    paths = write_campaign(tmp_path, "a", started=START_A)

    (group,) = grouped(*reversed(paths))

    assert group.key == "fixture-resistance-20260104-113751"
    assert (group.index, group.unclassified, group.started) == (1, False, START_A)
    assert group.scenario == ("FixtureMaster", "FixtureScenario")
    assert sources(group) == [f"a_{name}" for name in POLITICS]
    assert (group.first_date, group.last_date) == ("2032-01-01T00:00:00", "2032-07-01T00:00:00")


@pytest.mark.fixture
@pytest.mark.parametrize(
    "signals",
    [
        {"faction_name": "The Protectorate"},
        {"faction": OTHER_FACTION},
        {"started": START_B},
        {"scenario": "OtherScenario"},
    ],
    ids=["faction-name", "faction-ref", "real-world-start", "scenario"],
)
def test_a_differing_signal_separates_campaigns(signals: dict[str, object], tmp_path: Path) -> None:
    first = write_campaign(tmp_path, "a", started=START_A)
    second = write_campaign(tmp_path, "b", **{"started": START_A, **signals})

    groups = grouped(*first, *second)

    assert [sources(group) for group in groups] == [
        [f"a_{name}" for name in POLITICS],
        [f"b_{name}" for name in POLITICS],
    ]


@pytest.mark.fixture
def test_a_missing_real_world_start_is_not_merged_with_a_known_one(tmp_path: Path) -> None:
    known = write_campaign(tmp_path, "a", started=START_A)
    unknown = write_variant(tmp_path, "b.json", POLITICS[1])

    groups = grouped(*known, unknown)

    assert [group.key for group in groups] == ["fixture-resistance-20260104-113751", "fixture-resistance"]
    assert groups[1].started is None
    assert "grouped by faction and scenario only" in render_listing(groups)


@pytest.mark.fixture
@pytest.mark.parametrize("humans", [0, 2])
def test_an_unclassified_save_is_kept_apart_even_with_the_same_signals(humans: int, tmp_path: Path) -> None:
    campaign = write_campaign(tmp_path, "a")
    odd = write_variant(tmp_path, "odd.json", POLITICS[1], humans=humans)
    copy = tmp_path / "odd_copy.json"
    shutil.copyfile(odd, copy)

    groups = grouped(*campaign, odd, copy)

    assert [(group.key, group.unclassified, len(group.saves), len(group.members)) for group in groups] == [
        ("fixture-resistance", False, 3, 3),
        ("fixture-resistance#2", True, 1, 2),
    ]
    assert f"unclassified ({humans} human players)" in render_listing(groups)


@pytest.mark.fixture
def test_groups_are_ordered_by_real_world_start_unknown_last(tmp_path: Path) -> None:
    unknown = write_campaign(tmp_path, "u", faction_name="Academy")
    late = write_campaign(tmp_path, "l", faction_name="The Protectorate", started=START_B)
    early = write_campaign(tmp_path, "e", started=START_A)

    groups = grouped(*unknown, *late, *early)

    assert [(group.index, group.key) for group in groups] == [
        (1, "fixture-resistance-20260104-113751"),
        (2, "protectorate-20261014-152624"),
        (3, "academy"),
    ]


@pytest.mark.parametrize(
    ("name", "expected"),
    [("The Resistance", "resistance"), ("Humanity First", "humanity-first"), ("  ", "unknown"), (None, "unknown")],
)
def test_slug(name: str | None, expected: str) -> None:
    assert slug(name) == expected


@pytest.fixture
def two_campaigns(tmp_path: Path) -> tuple[CampaignGroup, ...]:
    resistance = write_campaign(tmp_path, "r", faction_name="The Resistance", started=START_A)
    protectorate = write_campaign(tmp_path, "p", faction_name="The Protectorate", started=START_B)
    return grouped(*resistance, *protectorate)


def never(path: str) -> float:
    raise AssertionError(f"file time read for {path}")


@pytest.mark.fixture
@pytest.mark.parametrize(
    ("selector", "index"),
    [("resistance-20260104-113751", 1), ("protectorate", 2), ("p", 2), ("2", 2), ("1", 1)],
)
def test_select_by_key_prefix_or_index(selector: str, index: int, two_campaigns: tuple[CampaignGroup, ...]) -> None:
    selected = select_campaign(two_campaigns, selector, never)

    assert isinstance(selected, CampaignGroup)
    assert selected.index == index


@pytest.mark.fixture
def test_select_latest_by_the_newest_file_time(two_campaigns: tuple[CampaignGroup, ...]) -> None:
    newest = Path(two_campaigns[0].saves[0].source).name

    selected = select_campaign(two_campaigns, "latest", lambda path: 2.0 if Path(path).name == newest else 1.0)

    assert isinstance(selected, CampaignGroup)
    assert selected.index == 1


@pytest.mark.fixture
@pytest.mark.parametrize(
    ("selector", "message"),
    [("academy", "no campaign matches 'academy'"), ("3", "there is no campaign 3"), ("0", "there is no campaign 0")],
)
def test_an_unknown_selector_is_reported(selector: str, message: str, two_campaigns: tuple[CampaignGroup, ...]) -> None:
    selected = select_campaign(two_campaigns, selector, never)

    assert isinstance(selected, str)
    assert message in selected


@pytest.mark.fixture
def test_an_ambiguous_prefix_is_reported(tmp_path: Path) -> None:
    groups = grouped(
        *write_campaign(tmp_path, "a", faction_name="The Resistance", started=START_A),
        *write_campaign(tmp_path, "b", faction_name="The Resistance", started=START_B),
    )

    selected = select_campaign(groups, "resistance", never)

    assert selected == (
        "campaign 'resistance' is ambiguous; it matches resistance-20260104-113751, resistance-20261014-152624"
    )
