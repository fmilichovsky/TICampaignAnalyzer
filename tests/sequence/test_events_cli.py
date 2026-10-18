"""Golden-output and exit-code coverage for ``tinarrative events``."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.fixtures import FIXTURES_ROOT
from tinarrative.cli import EXIT_INPUT_ERROR, EXIT_SUCCESS, EXIT_UNSUPPORTED_INPUT, EXIT_USAGE_ERROR, main

FIXTURE_SET = "terra_invicta_json_v1"
FIXTURE_DIR = FIXTURES_ROOT / "io" / FIXTURE_SET
EXPECTED_DIR = FIXTURES_ROOT / "sequence" / FIXTURE_SET
SHUFFLED = ["politics_reverted.json", "politics_before.json", "politics_after.json"]
"""The three-save politics sequence, out of order on purpose."""
MARKDOWN_GOLDENS = [("md", []), ("inferred.md", ["--inferred"])]


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


@pytest.mark.fixture
def test_json_report_without_inferred_says_so(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)

    assert main(["events", "--format", "json", *SHUFFLED]) == EXIT_SUCCESS
    report = json.loads(capsys.readouterr().out)

    assert [interval["inferred"] for interval in report["intervals"]] == [None, None]


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
