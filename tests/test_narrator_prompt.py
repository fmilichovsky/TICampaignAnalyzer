"""Coverage for scripts/narrator_prompt.py: sampling and the command over the synthetic sequence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.narrator_prompt import main, sample, sample_bounds
from tests.fixtures import FIXTURES_ROOT
from tinarrative.cli import EXIT_SUCCESS
from tinarrative.cli import main as cli_main

FIXTURE_DIR = FIXTURES_ROOT / "io" / "terra_invicta_json_v1"
SAVES = ["politics_reverted.json", "politics_before.json", "politics_after.json"]


def _package(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    monkeypatch.chdir(FIXTURE_DIR)
    assert cli_main(["events", "--format", "json", "--narrative", "--include-constituents", *SAVES]) == EXIT_SUCCESS
    return json.loads(capsys.readouterr().out)  # type: ignore[no-any-return]


@pytest.mark.fixture
def test_the_command_writes_the_same_bytes_every_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "package.json"
    source.write_text(json.dumps(_package(monkeypatch, capsys)), encoding="utf-8")

    outputs = []
    for _ in range(2):
        assert main([str(source), "--audience", "insider", "--style", "headlines", "--sample", "2032-Q2"]) == 0
        outputs.append(capsys.readouterr().out)

    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0])["messages"][0]["content"].startswith(
        "audience: insider\nstyle: headlines\nsample: 2032-Q2 "
    )


@pytest.mark.parametrize(
    ("label", "bounds"),
    [
        ("2032", ("2032-01-01T00:00:00", "2033-01-01T00:00:00")),
        ("2032-H2", ("2032-07-01T00:00:00", "2033-01-01T00:00:00")),
        ("2032-Q2", ("2032-04-01T00:00:00", "2032-07-01T00:00:00")),
    ],
)
def test_sample_labels_are_half_open_periods(label: str, bounds: tuple[str, str]) -> None:
    assert sample_bounds(label) == bounds


@pytest.mark.fixture
def test_a_sample_keeps_what_overlaps_its_period(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    package = _package(monkeypatch, capsys)

    first = sample(package, "2032-Q1")
    second = sample(package, "2032-Q2")

    assert [interval["key"] for interval in first["intervals"]] == ["2032-04-01T00:00:00"]
    assert [save["key"] for save in first["saves"]] == ["2032-01-01T00:00:00", "2032-04-01T00:00:00"]
    assert [event["event_type"] for event in first["narrative"]] == [
        "faction.takeover",
        "faction.takeover",
        "nation.claims_declared",
    ]
    assert [interval["key"] for interval in second["intervals"]] == ["2032-07-01T00:00:00"]
    assert "nation.cession" in [event["event_type"] for event in second["narrative"]]
    listed = {entry["ref"] for entry in second["glossary"]}
    assert listed < {entry["ref"] for entry in package["glossary"]}
    assert sample(package, "2032") == {**package, "glossary": sample(package, "2032")["glossary"]}


def test_bad_input_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plain = tmp_path / "plain.json"
    plain.write_text(json.dumps({"narrative": None, "glossary": None}), encoding="utf-8")

    assert main([str(plain)]) == 2
    assert "not a narrator package" in capsys.readouterr().err
    with pytest.raises(ValueError, match="not YYYY"):
        sample_bounds("2032-Q5")
