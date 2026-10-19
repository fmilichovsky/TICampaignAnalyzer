"""Golden-output and exit-code coverage for ``tinarrative events``."""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from tests.fixtures import FIXTURES_ROOT
from tests.sequence.campaign_variants import write_campaign, write_variant
from tinarrative import cli
from tinarrative.cli import (
    EXIT_CONFIG_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_SUCCESS,
    EXIT_UNSUPPORTED_INPUT,
    EXIT_USAGE_ERROR,
    main,
)
from tinarrative.config import CONFIG_ENV_VAR, DEFAULT_SETTINGS
from tinarrative.picker import PROMPT

FIXTURE_SET = "terra_invicta_json_v1"
FIXTURE_DIR = FIXTURES_ROOT / "io" / FIXTURE_SET
EXPECTED_DIR = FIXTURES_ROOT / "sequence" / FIXTURE_SET
SHUFFLED = ["politics_reverted.json", "politics_before.json", "politics_after.json"]
"""The three-save politics sequence, out of order on purpose."""
MARKDOWN_GOLDENS = [
    ("md", []),
    ("inferred.md", ["--inferred"]),
    ("changes.md", ["--changes"]),
    ("narrative.md", ["--narrative"]),
]


@pytest.mark.fixture
@pytest.mark.parametrize(("suffix", "flags"), MARKDOWN_GOLDENS)
def test_events_matches_the_golden_report(
    suffix: str, flags: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)  # bare file names keep machine paths out of the golden
    expected = (EXPECTED_DIR / f"politics_sequence.expected.{suffix}").read_text(encoding="utf-8")

    assert main(["events", *flags, *SHUFFLED]) == EXIT_SUCCESS
    first = capsys.readouterr()
    assert main(["events", *flags, *reversed(SHUFFLED)]) == EXIT_SUCCESS
    second = capsys.readouterr()

    assert first.out == expected
    assert second.out == first.out
    assert first.err == ""


@pytest.mark.fixture
def test_every_golden_report_has_a_test() -> None:
    assert sorted(path.name for path in EXPECTED_DIR.iterdir()) == sorted(
        f"politics_sequence.expected.{suffix}" for suffix, _ in MARKDOWN_GOLDENS
    )


@pytest.mark.fixture
def test_narrative_implies_inferred_and_adds_its_section_above_the_intervals() -> None:
    inferred = (EXPECTED_DIR / "politics_sequence.expected.inferred.md").read_text(encoding="utf-8")
    narrative = (EXPECTED_DIR / "politics_sequence.expected.narrative.md").read_text(encoding="utf-8")

    head, _, tail = inferred.partition("\n## Intervals\n")
    assert narrative.startswith(head + "\n## Narrative\n")
    assert narrative.endswith("\n## Intervals\n" + tail)


@pytest.mark.fixture
def test_non_default_settings_are_named_in_the_narrative_section(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)
    golden = (EXPECTED_DIR / "politics_sequence.expected.narrative.md").read_text(encoding="utf-8")
    config = tmp_path / "settings.toml"
    config.write_text("[narrative.geopolitics]\ntop_gdp_nations = 1\nledger_window_days = 0\n", encoding="utf-8")

    assert main(["events", "--narrative", "--config", str(config), *SHUFFLED]) == EXIT_SUCCESS

    line = (
        "Built with non-default settings: `narrative.geopolitics.ledger_window_days = 0`, "
        "`narrative.geopolitics.top_gdp_nations = 1`.\n\n"
    )
    assert capsys.readouterr().out == golden.replace("## Narrative\n\n", f"## Narrative\n\n{line}", 1)


@pytest.mark.fixture
def test_the_config_flag_wins_over_the_environment_and_a_bad_file_exits_with_the_config_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)
    good = tmp_path / "good.toml"
    good.write_text("[narrative.geopolitics]\ntop_gdp_nations = 3\n", encoding="utf-8")
    bad = tmp_path / "bad.toml"
    bad.write_text("[narrative.geopolitics]\ntop_gdp_nation = 3\n", encoding="utf-8")

    monkeypatch.setenv(CONFIG_ENV_VAR, str(bad))
    assert main(["events", "--format", "json", "--narrative", "--config", str(good), *SHUFFLED]) == EXIT_SUCCESS
    assert json.loads(capsys.readouterr().out)["settings"]["narrative"]["geopolitics"]["top_gdp_nations"] == 3

    assert main(["events", *SHUFFLED]) == EXIT_CONFIG_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unknown setting 'narrative.geopolitics.top_gdp_nation'" in captured.err

    assert main(["events", "--config", str(tmp_path / "missing.toml"), *SHUFFLED]) == EXIT_CONFIG_ERROR
    assert "cannot read settings" in capsys.readouterr().err


@pytest.mark.fixture
def test_json_report_lists_narrative_events_only_when_asked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    assert main(["events", "--format", "json", *SHUFFLED]) == EXIT_SUCCESS
    plain = json.loads(capsys.readouterr().out)
    assert main(["events", "--format", "json", "--narrative", *SHUFFLED]) == EXIT_SUCCESS
    narrative = json.loads(capsys.readouterr().out)

    assert plain["narrative"] is None and plain["settings"] is None
    assert [event["event_type"] for event in narrative["narrative"]] == [
        "faction.takeover",
        "nation.claims_declared",
        "nation.cession",
    ]
    assert narrative["settings"] == DEFAULT_SETTINGS.to_dict()
    assert all(interval["inferred"] is not None for interval in narrative["intervals"])


@pytest.mark.fixture
def test_json_report_lists_saves_and_intervals_with_unique_qualified_ids(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    assert main(["events", "--format", "json", "--inferred", *SHUFFLED]) == EXIT_SUCCESS
    report = json.loads(capsys.readouterr().out)

    assert [save["source"] for save in report["saves"]] == [
        "politics_before.json",
        "politics_after.json",
        "politics_reverted.json",
    ]
    assert [(interval["before"], interval["after"]) for interval in report["intervals"]] == [
        ("politics_before.json", "politics_after.json"),
        ("politics_after.json", "politics_reverted.json"),
    ]
    ids = [event["id"] for interval in report["intervals"] for event in interval["events"] + interval["inferred"]]
    assert len(ids) == len(set(ids))
    for interval in report["intervals"]:
        own = {event["id"] for event in interval["events"]}
        for event in interval["events"] + interval["inferred"]:
            assert event["id"].endswith("@" + interval["key"])
            assert set(event["constituents"]) <= own
    refs = [ref for interval in report["intervals"] for event in interval["events"] for ref in event["entities"]]
    assert refs and all(ref["name"].startswith("Fixture ") for ref in refs)
    attribute_refs = [
        value
        for interval in report["intervals"]
        for event in interval["events"]
        for value in event["attributes"].values()
        if isinstance(value, dict) and "ref" in value
    ]
    assert attribute_refs and all("name" in ref for ref in attribute_refs)
    dates = [save["situation"]["date"] for save in report["saves"]]
    assert dates == [save["date"] for save in report["saves"]]
    assert all(save["situation"]["nations"] for save in report["saves"])
    assert all("situation" not in interval for interval in report["intervals"])


@pytest.mark.fixture
def test_json_report_without_inferred_says_so(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    assert main(["events", "--format", "json", *SHUFFLED]) == EXIT_SUCCESS
    report = json.loads(capsys.readouterr().out)

    assert [interval["inferred"] for interval in report["intervals"]] == [None, None]


@pytest.mark.fixture
def test_json_report_carries_the_literal_changes_only_when_asked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    assert main(["events", "--format", "json", "--changes", *SHUFFLED]) == EXIT_SUCCESS
    report = json.loads(capsys.readouterr().out)
    assert main(["events", "--format", "json", *SHUFFLED]) == EXIT_SUCCESS
    plain = json.loads(capsys.readouterr().out)

    for interval in report["intervals"]:
        assert len(interval["state_changes"]) == interval["changes"] > 0
        for change in interval["state_changes"]:
            assert set(change) >= {"domain", "entity_id", "field", "kind", "description", "before_location"}
            assert change["after_location"]["save_id"] == interval["after"]
    assert [interval["state_changes"] for interval in plain["intervals"]] == [None, None]


@pytest.mark.fixture
def test_inferred_events_are_listed_apart_and_filtered_by_significance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)
    argv = ["events", "--inferred", "--min-significance", "major", "politics_before.json", "politics_after.json"]

    assert main(argv) == EXIT_SUCCESS
    out = capsys.readouterr().out

    inferred = out.split("#### Inferred events\n", 1)[1].split("\n#### Objective analyzer results\n", 1)[0]
    key = "@2032-04-01T00:00:00"
    assert (
        "- Fixture Northland (nation:20) annexed 1 region of Fixture Southland (nation:21) (confidence: `medium`)\n"
        in inferred
    )
    assert (
        f"  - from `region.nation_changed/region:42{key}`: Fixture South (region:42) nation: "
        f"Fixture Southland (nation:21) -> Fixture Northland (nation:20)\n" in inferred
    )
    assert "gained" not in inferred
    assert "2 inferred events below major significance omitted.\n" in inferred


@pytest.mark.fixture
def test_duplicates_are_merged_and_one_distinct_save_compares_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = tmp_path / "Exitsave.json"
    shutil.copyfile(FIXTURE_DIR / "politics_after.json", copy)

    assert main(["events", str(FIXTURE_DIR / "politics_after.json"), str(copy)]) == EXIT_SUCCESS
    out = capsys.readouterr().out

    assert "2 saves given, 1 byte-identical copy merged" in out
    assert "(identical: " in out
    assert "no interval was compared" in out

    assert main(["events", "--format", "json", str(FIXTURE_DIR / "politics_after.json"), str(copy)]) == EXIT_SUCCESS
    report = json.loads(capsys.readouterr().out)
    assert [save["situation"] for save in report["saves"]] == [None]
    assert report["intervals"] == []


@pytest.mark.fixture
def test_a_single_save_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["events", str(FIXTURE_DIR / "politics_after.json")]) == EXIT_USAGE_ERROR
    assert "at least two saves" in capsys.readouterr().err


@pytest.mark.fixture
def test_an_unreadable_save_stops_the_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing.json"

    assert main(["events", str(FIXTURE_DIR / "politics_after.json"), str(missing)]) == EXIT_INPUT_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "cannot read" in captured.err


@pytest.mark.fixture
@pytest.mark.parametrize(
    ("name", "message"), [("representative_campaign.json", "cannot be ordered"), ("malformed_truncated.json", "")]
)
def test_an_unorderable_or_unsupported_save_stops_the_run(
    name: str, message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["events", str(FIXTURE_DIR / "politics_after.json"), str(FIXTURE_DIR / name)]) == EXIT_UNSUPPORTED_INPUT
    captured = capsys.readouterr()
    assert captured.out == ""
    assert message in captured.err


def _directory(root: Path, *names: str) -> Path:
    directory = root / "saves"
    directory.mkdir()
    for name in names:
        shutil.copyfile(FIXTURE_DIR / name, directory / name)
    return directory


@pytest.mark.fixture
def test_a_directory_is_expanded_and_its_invalid_files_are_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _directory(tmp_path, *SHUFFLED, "malformed_truncated.json", "representative_campaign.json")
    monkeypatch.chdir(tmp_path)

    assert main(["events", "saves"]) == EXIT_SUCCESS
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "3 saves given, 2 skipped; ordered by serialized game time." in captured.out
    assert "\n- `saves/malformed_truncated.json`: MalformedSaveError: " in captured.out
    assert "\n- `saves/representative_campaign.json`: UnknownChronologyError: " in captured.out
    assert captured.out.count("\n### ") == 2

    assert main(["events", "--format", "json", "saves"]) == EXIT_SUCCESS
    report = json.loads(capsys.readouterr().out)
    assert report["inputs"] == 3
    assert [(skipped["source"], skipped["error_class"]) for skipped in report["skipped"]] == [
        ("saves/malformed_truncated.json", "MalformedSaveError"),
        ("saves/representative_campaign.json", "UnknownChronologyError"),
    ]
    assert [interval["after"] for interval in report["intervals"]] == [
        "saves/politics_after.json",
        "saves/politics_reverted.json",
    ]


@pytest.mark.fixture
def test_files_and_directories_mix_and_identical_copies_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _directory(tmp_path, "politics_before.json", "politics_after.json")
    shutil.copyfile(FIXTURE_DIR / "politics_after.json", tmp_path / "Exitsave.json")
    shutil.copyfile(FIXTURE_DIR / "politics_reverted.json", tmp_path / "reverted.json")
    monkeypatch.chdir(tmp_path)

    assert main(["events", "--format", "json", "reverted.json", "saves", "Exitsave.json"]) == EXIT_SUCCESS
    report = json.loads(capsys.readouterr().out)

    assert (report["inputs"], report["duplicates"], report["skipped"]) == (4, 1, [])
    assert [(save["source"], save["aliases"]) for save in report["saves"]] == [
        ("saves/politics_before.json", []),
        ("Exitsave.json", ["saves/politics_after.json"]),
        ("reverted.json", []),
    ]


@pytest.mark.fixture
def test_a_named_invalid_file_still_fails_beside_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = _directory(tmp_path, *SHUFFLED)

    assert main(["events", str(directory), str(FIXTURE_DIR / "malformed_truncated.json")]) == EXIT_UNSUPPORTED_INPUT
    assert capsys.readouterr().out == ""


@pytest.mark.fixture
@pytest.mark.parametrize(
    ("names", "message"),
    [((), "the directory holds no files"), (("malformed_truncated.json",), "the directory holds no usable save")],
)
def test_a_directory_without_a_usable_save_is_an_input_error(
    names: tuple[str, ...], message: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = _directory(tmp_path, *names)

    assert main(["events", str(directory), str(FIXTURE_DIR / "politics_before.json")]) == EXIT_INPUT_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert message in captured.err


@pytest.mark.fixture
@pytest.mark.parametrize("names", [("politics_after.json",), ("politics_after.json", "malformed_truncated.json")])
def test_fewer_than_two_usable_saves_after_expansion_is_a_usage_error(
    names: tuple[str, ...], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = _directory(tmp_path, *names)

    assert main(["events", str(directory)]) == EXIT_USAGE_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "at least two saves are required" in captured.err


@pytest.mark.fixture
def test_directory_runs_log_counts_and_no_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    directory = _directory(tmp_path, *SHUFFLED, "malformed_truncated.json")

    assert main(["--log-level", "debug", "events", str(directory)]) == EXIT_SUCCESS
    err = capsys.readouterr().err

    assert "skipped=1" in err
    assert str(tmp_path) not in err


def _two_campaigns(root: Path) -> Path:
    directory = root / "saves"
    write_campaign(directory, "r", faction_name="The Resistance", started=datetime(2026, 1, 4, 11, 37, 51))
    write_campaign(directory, "p", faction_name="The Protectorate", started=datetime(2026, 10, 14, 15, 26, 24))
    return directory


@pytest.mark.fixture
def test_one_campaign_needs_no_selector_and_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _directory(tmp_path, *SHUFFLED)
    monkeypatch.chdir(tmp_path)

    assert main(["events", "--format", "json", "saves"]) == EXIT_SUCCESS
    report = json.loads(capsys.readouterr().out)

    assert report["campaign"]["key"] == "fixture-resistance"
    assert report["campaign"]["saves"] == 3


@pytest.mark.fixture
def test_several_campaigns_without_a_selector_is_a_usage_error_with_the_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _two_campaigns(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert main(["events", "saves"]) == EXIT_USAGE_ERROR
    captured = capsys.readouterr()

    assert captured.out == ""
    assert "the input holds 2 campaigns; choose one with --campaign" in captured.err
    assert "1. resistance-20260104-113751\n" in captured.err
    assert "2. protectorate-20261014-152624\n" in captured.err


@pytest.mark.fixture
@pytest.mark.parametrize(("selector", "prefix"), [("protectorate", "p_"), ("1", "r_"), ("latest", "p_")])
def test_a_selected_campaign_reports_only_its_own_saves(
    selector: str,
    prefix: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    directory = _two_campaigns(tmp_path)
    for path in directory.iterdir():
        os.utime(path, (1_000_000, 2_000_000 if path.name == "p_politics_before.json" else 1_000_000))
    monkeypatch.chdir(tmp_path)

    assert main(["events", "--format", "json", "--campaign", selector, "saves"]) == EXIT_SUCCESS
    report = json.loads(capsys.readouterr().out)

    assert report["campaign"]["key"].startswith("protectorate" if prefix == "p_" else "resistance")
    assert all(Path(save["source"]).name.startswith(prefix) for save in report["saves"])
    assert len(report["intervals"]) == 2

    assert main(["events", "--campaign", selector, "saves"]) == EXIT_SUCCESS
    assert "3 given saves belong to other campaigns." in capsys.readouterr().out


@pytest.mark.fixture
def test_an_unknown_campaign_is_a_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _two_campaigns(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert main(["events", "--campaign", "academy", "saves"]) == EXIT_USAGE_ERROR
    captured = capsys.readouterr()

    assert captured.out == ""
    assert "no campaign matches 'academy'" in captured.err
    assert "2 campaigns:" in captured.err


@pytest.mark.fixture
def test_a_selected_campaign_with_one_save_is_a_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _directory(tmp_path, *SHUFFLED)
    write_variant(tmp_path / "saves", "odd.json", humans=0)
    monkeypatch.chdir(tmp_path)

    assert main(["events", "--campaign", "2", "saves"]) == EXIT_USAGE_ERROR
    assert "campaign fixture-resistance#2 has 1" in capsys.readouterr().err


@pytest.fixture
def interactive(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    """Make ``events`` treat the session as a terminal and answer the picker with ``answers``."""

    def answer(answers: str) -> None:
        monkeypatch.setattr(cli, "_interactive", lambda: True)
        monkeypatch.setattr(sys, "stdin", io.StringIO(answers))

    return answer


@pytest.mark.fixture
def test_several_campaigns_in_a_terminal_open_the_picker_and_continue(
    interactive: Callable[[str], None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _two_campaigns(tmp_path)
    monkeypatch.chdir(tmp_path)
    interactive("protector\n")

    assert main(["events", "--format", "json", "saves"]) == EXIT_SUCCESS
    captured = capsys.readouterr()

    report = json.loads(captured.out)  # the prompt never reaches the report
    assert report["campaign"]["key"].startswith("protectorate")
    assert len(report["intervals"]) == 2
    assert "2 campaigns:\n" in captured.err
    assert PROMPT in captured.err


@pytest.mark.fixture
def test_an_unmatched_selector_in_a_terminal_opens_the_picker(
    interactive: Callable[[str], None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _two_campaigns(tmp_path)
    monkeypatch.chdir(tmp_path)
    interactive("1\n")

    assert main(["events", "--format", "json", "--campaign", "academy", "saves"]) == EXIT_SUCCESS
    captured = capsys.readouterr()

    assert json.loads(captured.out)["campaign"]["key"].startswith("resistance")
    assert "no campaign matches 'academy'" in captured.err


@pytest.mark.fixture
@pytest.mark.parametrize("answers", ["\n", ""])
def test_a_cancelled_picker_is_a_usage_error(
    answers: str,
    interactive: Callable[[str], None],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _two_campaigns(tmp_path)
    monkeypatch.chdir(tmp_path)
    interactive(answers)

    assert main(["events", "saves"]) == EXIT_USAGE_ERROR
    captured = capsys.readouterr()

    assert captured.out == ""
    assert "tinarrative events: no campaign chosen" in captured.err
