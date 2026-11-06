"""Golden-output and exit-code coverage for ``tinarrative events``."""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

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
from tinarrative.narrative.evidence import is_evidence
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
    ("narrative.major.md", ["--narrative", "--min-significance", "major"]),
    ("narrative.constituents.md", ["--narrative", "--constituents", "all"]),
    ("narrative.evidence.md", ["--narrative", "--constituents", "evidence"]),
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
    assert re.fullmatch(r"tinarrative events: parsing and processing took \d+\.\d+s\n", first.err)
    assert re.fullmatch(r"tinarrative events: parsing and processing took \d+\.\d+s\n", second.err)


@pytest.mark.fixture
def test_every_golden_report_has_a_test() -> None:
    narrator = "politics_sequence.expected.narrator_messages.json"  # tests/narrator/test_request.py
    assert sorted(path.name for path in EXPECTED_DIR.iterdir()) == sorted(
        [f"politics_sequence.expected.{suffix}" for suffix, _ in MARKDOWN_GOLDENS] + [narrator]
    )


@pytest.mark.fixture
@pytest.mark.parametrize("suffix", ["narrative.md", "narrative.constituents.md", "narrative.evidence.md"])
def test_narrative_implies_inferred_and_adds_its_section_above_the_intervals(suffix: str) -> None:
    inferred = (EXPECTED_DIR / "politics_sequence.expected.inferred.md").read_text(encoding="utf-8")
    narrative = (EXPECTED_DIR / f"politics_sequence.expected.{suffix}").read_text(encoding="utf-8")

    head = inferred.partition("\n## Intervals\n")[0]
    assert narrative.startswith(head + "\n## Narrative\n")
    assert narrative.count("#### Inferred events") == (0 if suffix == "narrative.md" else 2)


@pytest.mark.fixture
def test_without_constituents_the_narrative_report_lists_no_atomic_event(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    assert main(["events", "--narrative", *SHUFFLED]) == EXIT_SUCCESS

    intervals = capsys.readouterr().out.partition("## Intervals\n")[2]
    assert [line for line in intervals.splitlines() if line] == [
        "- `2032-01-01T00:00:00` to `2032-04-01T00:00:00`: nothing listed "
        "(33 state changes; 27 events omitted with --constituents none)",
        "- `2032-04-01T00:00:00` to `2032-07-01T00:00:00`: nothing listed "
        "(10 state changes; 7 events omitted with --constituents none)",
    ]


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
        "faction.takeover",
        "nation.claims_declared",
        "nation.cession",
        "world.ranking_changed",
    ]
    assert narrative["settings"] == {"narrative": DEFAULT_SETTINGS.to_dict()["narrative"]}
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


@pytest.mark.fixture
@pytest.mark.parametrize(
    ("suffix", "flags"),
    [("md", []), ("narrative.md", ["--narrative"]), ("changes.md", ["--changes"]), ("json", ["--format", "json"])],
)
def test_workers_write_the_golden_report_byte_for_byte(
    suffix: str, flags: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)
    monkeypatch.setattr("tinarrative.sequence.MIN_CHUNK_INTERVALS", 1)  # two chunks over the three fixture saves

    assert main(["events", *flags, "--jobs", "2", *SHUFFLED]) == EXIT_SUCCESS
    parallel = capsys.readouterr()
    assert main(["events", *flags, "--jobs", "1", *SHUFFLED]) == EXIT_SUCCESS
    serial = capsys.readouterr()

    assert parallel.out == serial.out
    if suffix != "json":
        assert parallel.out == (EXPECTED_DIR / f"politics_sequence.expected.{suffix}").read_text(encoding="utf-8")
    assert re.fullmatch(r"tinarrative events: parsing and processing took \d+\.\d+s\n", parallel.err)


@pytest.mark.fixture
@pytest.mark.parametrize("jobs", ["1", "2"])
def test_a_save_that_fails_in_a_worker_gives_the_code_and_message_of_one_process(
    jobs: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("tinarrative.sequence.MIN_CHUNK_INTERVALS", 1)
    saves = _directory(tmp_path, *SHUFFLED)
    planned = cli.plan_sequence

    def vanish(*args: Any) -> Any:
        plan = planned(*args)
        Path(plan.saves[-1].source).unlink()  # surveyed, then gone before its chunk loads it
        return plan

    monkeypatch.setattr(cli, "plan_sequence", vanish)

    assert main(["events", "--jobs", jobs, str(saves)]) == EXIT_INPUT_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    missing = saves / "politics_reverted.json"
    assert captured.err.splitlines()[0] == f"tinarrative events: cannot read {missing}: No such file or directory"


@pytest.mark.fixture
@pytest.mark.parametrize("name", ["missing.json", "malformed_truncated.json"])
def test_a_survey_failure_in_a_worker_gives_the_code_and_message_of_one_process(
    name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = str(FIXTURE_DIR / name) if name != "missing.json" else str(tmp_path / name)
    outcomes = []
    for jobs in ("1", "2"):
        code = main(["events", "--jobs", jobs, str(FIXTURE_DIR / "politics_after.json"), path])
        outcomes.append((code, capsys.readouterr()))

    (serial_code, serial), (parallel_code, parallel) = outcomes
    assert parallel_code == serial_code in (EXIT_INPUT_ERROR, EXIT_UNSUPPORTED_INPUT)
    assert parallel.err.splitlines()[0] == serial.err.splitlines()[0]
    assert parallel.out == serial.out == ""


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
    assert re.fullmatch(r"tinarrative events: parsing and processing took \d+\.\d+s\n", captured.err)
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


def _json(capsys: pytest.CaptureFixture[str], *flags: str) -> dict[str, Any]:
    assert main(["events", "--format", "json", *flags, *SHUFFLED]) == EXIT_SUCCESS
    return json.loads(capsys.readouterr().out)  # type: ignore[no-any-return]


def _references(node: Any, *, bare: bool = False) -> set[str]:
    """Every ``ref`` in a document, plus the faction IDs keying a nation's ``shares`` and its ``allies`` refs; with
    ``bare``, only the refs given somewhere without a name (those keys and strings, and ref objects without
    ``name``)."""
    found: set[str] = set()
    if isinstance(node, dict):
        if isinstance(node.get("ref"), str) and not (bare and "name" in node):
            found.add(node["ref"])
        for key, value in node.items():
            if key == "shares" and isinstance(value, dict):
                found.update(value)
            elif key == "allies" and isinstance(value, list):
                found.update(item for item in value if isinstance(item, str))
            else:
                found |= _references(value, bare=bare)
    elif isinstance(node, list):
        for item in node:
            found |= _references(item, bare=bare)
    return found


@pytest.mark.fixture
@pytest.mark.parametrize(
    "flags",
    [
        [],
        ["--min-significance", "major"],
        ["--min-significance", "campaign_defining"],
        ["--constituents", "all"],
        ["--constituents", "evidence", "--min-significance", "major"],
    ],
)
def test_the_glossary_holds_only_ids_referenced_without_a_name_and_renamed_entities(
    flags: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    document = _json(capsys, "--narrative", *flags)

    glossary = document["glossary"]
    listed = [entry["ref"] for entry in glossary]
    assert listed == sorted(set(listed), key=lambda text: (text.partition(":")[0], len(text), text))
    without = {key: value for key, value in document.items() if key != "glossary"}
    bare = _references(without, bare=True)
    assert set(listed) <= _references(without)
    assert all("former_names" in entry or entry["ref"] in bare for entry in glossary)
    assert all(entry["domain"] == entry["ref"].partition(":")[0] for entry in glossary)
    assert all(set(entry) <= {"ref", "domain", "name", "former_names"} for entry in glossary)


@pytest.mark.fixture
def test_the_glossary_names_share_holders_and_leaves_out_entities_named_inline(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    document = _json(capsys, "--narrative")

    entries = {entry["ref"]: entry for entry in document["glossary"]}
    assert entries["faction:15"] == {"ref": "faction:15", "domain": "faction", "name": "Fixture Resistance"}
    assert "nation:20" not in entries
    assert not any(ref.startswith("region:") for ref in entries)


@pytest.mark.fixture
def test_the_json_has_no_glossary_without_narrative(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    document = _json(capsys)

    assert document["glossary"] is None and document["narrative_omitted"] is None
    assert document["min_significance"] == "trivial" and document["constituents"] is None
    assert all(interval["omitted"] == {"objective": 0, "inferred": None} for interval in document["intervals"])


@pytest.mark.fixture
def test_the_json_drops_narrative_events_below_the_minimum_and_counts_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)
    everything = _json(capsys, "--narrative")

    major = _json(capsys, "--narrative", "--min-significance", "major")
    defining = _json(capsys, "--narrative", "--min-significance", "campaign_defining")

    assert major["min_significance"] == "major" and major["narrative_omitted"] == 0
    assert [event["event_type"] for event in defining["narrative"]] == ["faction.takeover"] * 2
    assert defining["narrative_omitted"] == len(everything["narrative"]) - 2


@pytest.mark.fixture
def test_without_narrative_the_json_drops_atomic_events_below_the_minimum_and_counts_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)
    everything = _json(capsys, "--inferred")

    major = _json(capsys, "--inferred", "--min-significance", "major")

    assert major["min_significance"] == "major" and major["narrative_omitted"] is None
    assert major["intervals"][0]["omitted"]["objective"] > 0
    for full, kept in zip(everything["intervals"], major["intervals"], strict=True):
        assert kept["omitted"]["objective"] == len(full["events"]) - len(kept["events"])
        assert kept["omitted"]["inferred"] == len(full["inferred"]) - len(kept["inferred"])
        assert {event["significance"] for event in kept["events"] + kept["inferred"]} <= {"major", "campaign_defining"}
        assert kept["state_changes"] == full["state_changes"]
        assert kept["changes"] == full["changes"]


@pytest.mark.fixture
@pytest.mark.parametrize(
    ("period", "headings"),
    [("year", ["### 2032"]), ("half", ["### 2032 H1"]), ("quarter", ["### 2032 Q1", "### 2032 Q2"])],
)
def test_period_groups_the_narrative_section(
    period: str, headings: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    assert main(["events", "--narrative", "--period", period, *SHUFFLED]) == EXIT_SUCCESS

    narrative = capsys.readouterr().out.partition("## Narrative")[2].partition("## Intervals")[0]
    assert [line for line in narrative.splitlines() if line.startswith("### ")] == headings


@pytest.mark.fixture
def test_intervals_with_nothing_at_the_minimum_are_one_line_each(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    assert main(["events", "--inferred", "--min-significance", "campaign_defining", *SHUFFLED]) == EXIT_SUCCESS

    intervals = capsys.readouterr().out.partition("## Intervals\n")[2]
    assert "###" not in intervals
    assert [line for line in intervals.splitlines() if line] == [
        "- `2032-01-01T00:00:00` to `2032-04-01T00:00:00`: nothing listed "
        "(33 state changes; 27 events below campaign_defining significance omitted)",
        "- `2032-04-01T00:00:00` to `2032-07-01T00:00:00`: nothing listed "
        "(10 state changes; 7 events below campaign_defining significance omitted)",
    ]


def _keys(node: Any) -> set[str]:
    if isinstance(node, dict):
        return set(node).union(*(_keys(value) for value in node.values()))
    if isinstance(node, list):
        return set().union(*(_keys(item) for item in node))
    return set()


def _ids(document: dict[str, Any]) -> list[str]:
    return [event["id"] for interval in document["intervals"] for event in interval["events"] + interval["inferred"]]


@pytest.mark.fixture
@pytest.mark.parametrize("flags", [[], ["--min-significance", "major"], ["--constituents", "all"]])
def test_the_narrator_package_carries_ids_but_no_provenance_or_paths(
    flags: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    package = _json(capsys, "--narrative", *flags)

    assert main(["events", "--format", "json", "--narrative", *flags, *SHUFFLED]) == EXIT_SUCCESS
    assert capsys.readouterr().out == json.dumps(package, indent=2, ensure_ascii=True) + "\n"
    text = json.dumps(package)
    assert ".json" not in text
    without = {key: value for key, value in package.items() if key != "glossary"}
    assert not _keys(without) & {"sources", "source", "aliases", "before_location", "after_location", "state_type"}
    assert all(set(interval) >= {"not_before", "date"} for interval in package["intervals"])
    assert all("before" not in interval and "after" not in interval for interval in package["intervals"])
    assert not _keys(package["glossary"]) & {"kind", "regions"}
    assert {entry["ref"] for entry in package["glossary"]} <= _references(without)


@pytest.mark.fixture
@pytest.mark.parametrize("level", ["trivial", "major"])
def test_every_narrator_package_id_resolves_in_the_audit_report(
    level: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    package = _json(capsys, "--narrative", "--constituents", "all", "--min-significance", level)
    audit = _json(capsys, "--inferred")

    assert set(_ids(package)) <= set(_ids(audit))
    assert [save["key"] for save in package["saves"]] == [save["key"] for save in audit["saves"]]
    assert all(save["source"] for save in audit["saves"])
    audited = {
        event["id"]: event for interval in audit["intervals"] for event in interval["events"] + interval["inferred"]
    }
    assert all(event["sources"] for event in audited.values())
    for event in package["narrative"]:
        assert set(event["constituents"]) <= set(audited) | {narrative["id"] for narrative in package["narrative"]}


@pytest.mark.fixture
@pytest.mark.parametrize("level", ["trivial", "major", "campaign_defining"])
def test_the_package_lists_exactly_the_constituents_of_its_narrative_events(
    level: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    package = _json(capsys, "--narrative", "--constituents", "all", "--min-significance", level)
    evidence = _json(capsys, "--narrative", "--constituents", "evidence", "--min-significance", level)
    without = _json(capsys, "--narrative", "--min-significance", level)
    audit = _json(capsys, "--inferred")

    by_id = {
        event["id"]: event for interval in package["intervals"] for event in interval["events"] + interval["inferred"]
    }
    by_id.update((event["id"], event) for event in package["narrative"])
    reached: set[str] = set()
    pending = [constituent for event in package["narrative"] for constituent in event["constituents"]]
    while pending:
        current = pending.pop()
        if current not in reached:
            reached.add(current)
            pending.extend(by_id[current]["constituents"])  # every citation resolves inside the package
    assert set(_ids(package)) == reached - {event["id"] for event in package["narrative"]}
    assert package["constituents"] == "all" and without["constituents"] == "none"
    assert evidence["constituents"] == "evidence" and evidence["narrative"] == package["narrative"]
    assert _ids(evidence) == [
        event["id"]
        for interval in package["intervals"]
        for event in interval["events"] + interval["inferred"]
        if is_evidence(event["event_type"])
    ]
    assert _ids(without) == [] and without["narrative"] == package["narrative"]
    for kept, empty, full in zip(package["intervals"], without["intervals"], audit["intervals"], strict=True):
        assert kept["omitted"]["objective"] == len(full["events"]) - len(kept["events"])
        assert kept["omitted"]["inferred"] == len(full["inferred"]) - len(kept["inferred"])
        assert empty["omitted"] == {"objective": len(full["events"]), "inferred": len(full["inferred"])}
        assert kept["changes"] == full["changes"]


@pytest.mark.fixture
@pytest.mark.parametrize("mode", ["all", "evidence"])
def test_constituents_change_nothing_without_narrative(
    mode: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    assert _json(capsys, "--inferred", "--constituents", mode) == _json(capsys, "--inferred")
    assert main(["events", "--inferred", "--constituents", mode, *SHUFFLED]) == EXIT_SUCCESS
    with_flag = capsys.readouterr().out
    assert main(["events", "--inferred", *SHUFFLED]) == EXIT_SUCCESS
    assert with_flag == capsys.readouterr().out


@pytest.mark.fixture
def test_the_narrator_package_leaves_out_nations_without_regions_that_nothing_references(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    def listed(document: dict[str, Any]) -> list[list[str]]:
        return [[nation["nation"]["ref"] for nation in save["situation"]["nations"]] for save in document["saves"]]

    audit = _json(capsys, "--inferred", "--min-significance", "major")
    everything = _json(capsys, "--narrative", "--constituents", "all")
    major = _json(capsys, "--narrative", "--min-significance", "major")

    assert listed(audit) == [["nation:20", "nation:21", "nation:22"]] * 3
    # nation:22 holds no region and only uncited events name it; nation:21 holds none in April but does elsewhere
    assert listed(everything) == listed(major) == [["nation:20", "nation:21"]] * 3
    assert [save["situation"]["world"] for save in major["saves"]] == [
        save["situation"]["world"] for save in audit["saves"]
    ]


@pytest.mark.fixture
def test_the_narrator_package_slims_the_situation_reports_and_the_audit_form_does_not(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    audit = _json(capsys, "--inferred")
    package = _json(capsys, "--narrative", "--min-significance", "major")

    def reports(document: dict[str, Any]) -> list[dict[str, Any]]:
        return [save["situation"] for save in document["saves"] if save["situation"] is not None]

    audited = [nation for report in reports(audit) for nation in report["nations"]]
    assert all({"seat_basis", "unresolved_points"} <= set(nation) for nation in audited)
    assert all(ally.get("ref") for nation in audited for ally in nation["allies"])
    assert all("other_bodies" not in faction for report in reports(audit) for faction in report["factions"])
    for nation in (nation for report in reports(package) for nation in report["nations"]):
        assert "seat_basis" not in nation
        assert nation.get("unresolved_points") != 0
        assert "allies" not in nation
    for faction in (faction for report in reports(package) for faction in report["factions"]):
        assert all(entry["habs"] > 1 for entry in faction["habs_by_body"])
        assert faction["habs"] >= sum(entry["habs"] for entry in faction["habs_by_body"]) + faction["other_bodies"]


@pytest.mark.fixture
def test_the_narrator_package_refuses_literal_changes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    assert main(["events", "--format", "json", "--narrative", "--changes", *SHUFFLED]) == EXIT_USAGE_ERROR

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "carries no state changes" in captured.err
