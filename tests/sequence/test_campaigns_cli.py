"""Output and exit-code coverage for ``tinarrative campaigns``."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from tests.fixtures import FIXTURES_ROOT
from tests.sequence.campaign_variants import write_campaign, write_variant
from tinarrative.cli import EXIT_INPUT_ERROR, EXIT_SUCCESS, EXIT_UNSUPPORTED_INPUT, main

FIXTURE_DIR = FIXTURES_ROOT / "io" / "terra_invicta_json_v1"


def _saves(root: Path) -> Path:
    directory = root / "saves"
    write_campaign(directory, "r", faction_name="The Resistance", started=datetime(2026, 1, 4, 11, 37, 51))
    write_campaign(directory, "p", faction_name="The Protectorate", started=datetime(2026, 10, 14, 15, 26, 24))
    shutil.copyfile(directory / "p_politics_after.json", directory / "p_copy.json")
    write_variant(directory, "odd.json", humans=2)
    shutil.copyfile(FIXTURE_DIR / "malformed_truncated.json", directory / "broken.json")
    return directory


@pytest.mark.fixture
def test_text_listing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _saves(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert main(["campaigns", "saves"]) == EXIT_SUCCESS
    captured = capsys.readouterr()

    assert captured.err == ""
    assert captured.out.startswith(
        "3 campaigns:\n"
        "\n"
        "1. resistance-20260104-113751\n"
        "   The Resistance, scenario FixtureMaster/FixtureScenario, started 2026-01-04 11:37:51\n"
        "   3 saves, 2032-01-01T00:00:00 to 2032-07-01T00:00:00\n"
        "\n"
        "2. protectorate-20261014-152624\n"
    )
    assert "3. fixture-resistance\n" in captured.out
    assert "   unclassified (2 human players); never grouped with another save\n" in captured.out
    assert "1 skipped (inside a given directory, not a usable save):\n- saves/broken.json: MalformedSaveError" in (
        captured.out
    )


@pytest.mark.fixture
def test_json_listing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _saves(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert main(["campaigns", "--format", "json", "saves"]) == EXIT_SUCCESS
    report = json.loads(capsys.readouterr().out)

    assert (report["inputs"], report["duplicates"]) == (8, 1)
    assert [skipped["source"] for skipped in report["skipped"]] == ["saves/broken.json"]
    assert report["campaigns"][1] == {
        "index": 2,
        "key": "protectorate-20261014-152624",
        "faction": "The Protectorate",
        "scenario": {"master": "FixtureMaster", "scenario": "FixtureScenario"},
        "started": "2026-10-14T15:26:24",
        "unclassified": False,
        "inputs": 4,
        "saves": 3,
        "first_date": "2032-01-01T00:00:00",
        "last_date": "2032-07-01T00:00:00",
        "sources": ["saves/p_politics_before.json", "saves/p_copy.json", "saves/p_politics_reverted.json"],
    }
    assert report["campaigns"][2]["unclassified"] is True


@pytest.mark.fixture
def test_a_single_save_is_listed(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["campaigns", str(FIXTURE_DIR / "politics_before.json")]) == EXIT_SUCCESS
    assert capsys.readouterr().out.startswith("1 campaign:\n\n1. fixture-resistance\n")


@pytest.mark.fixture
def test_a_missing_path_is_an_input_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["campaigns", str(tmp_path / "missing.json")]) == EXIT_INPUT_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("tinarrative campaigns: cannot read ")


@pytest.mark.fixture
def test_a_named_invalid_file_is_unsupported(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["campaigns", str(FIXTURE_DIR / "malformed_truncated.json")]) == EXIT_UNSUPPORTED_INPUT
    assert capsys.readouterr().out == ""


@pytest.mark.fixture
def test_logs_counts_and_no_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    directory = _saves(tmp_path)

    assert main(["--log-level", "debug", "campaigns", str(directory)]) == EXIT_SUCCESS
    err = capsys.readouterr().err

    assert "groups=3" in err
    assert str(tmp_path) not in err
    assert "Resistance" not in err
