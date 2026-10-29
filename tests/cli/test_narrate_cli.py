"""Coverage for `tinarrative narrate`: package input, the written plan and requests, and exit codes."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from tests.fixtures import FIXTURES_ROOT
from tinarrative.cli import (
    EXIT_CONFIG_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_OUTPUT_ERROR,
    EXIT_SUCCESS,
    EXIT_UNSUPPORTED_INPUT,
    EXIT_USAGE_ERROR,
    main,
)

FIXTURE_DIR = FIXTURES_ROOT / "io" / "terra_invicta_json_v1"
SAVES = ["politics_reverted.json", "politics_before.json", "politics_after.json"]


def _files(directory: Path) -> dict[str, bytes]:
    return {str(path.relative_to(directory)): path.read_bytes() for path in sorted(directory.rglob("*.json"))}


def _package(tmp_path: Path, capsys: pytest.CaptureFixture[str], constituents: str = "evidence") -> Path:
    args = ["events", "--format", "json", "--narrative", "--constituents", constituents, "--min-significance", "major"]
    assert main([*args, *SAVES]) == EXIT_SUCCESS
    path = tmp_path / f"package.{constituents}.json"
    path.write_text(capsys.readouterr().out, encoding="utf-8")
    return path


def _settings(tmp_path: Path, budget: int) -> Path:
    path = tmp_path / "settings.toml"
    path.write_text(f"[narrator]\nmax_input_tokens = {budget}\n", encoding="utf-8")
    return path


@pytest.fixture
def in_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(FIXTURE_DIR)


@pytest.mark.fixture
@pytest.mark.usefixtures("in_fixtures")
def test_saves_a_package_file_and_stdin_give_the_same_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    package = _package(tmp_path, capsys)
    options = ["--audience", "insider", "--length", "1500", "--config", str(_settings(tmp_path, 10000))]

    assert main(["narrate", *SAVES, *options, "--output", str(tmp_path / "saves")]) == EXIT_SUCCESS
    assert main(["narrate", "--package", str(package), *options, "--output", str(tmp_path / "file")]) == EXIT_SUCCESS
    monkeypatch.setattr("sys.stdin", io.StringIO(package.read_text(encoding="utf-8")))
    assert main(["narrate", "--package", "-", *options, "--output", str(tmp_path / "stdin")]) == EXIT_SUCCESS
    out = capsys.readouterr().out

    written = _files(tmp_path / "saves")
    assert list(written) == ["plan.json", "requests/01.json", "requests/02.json"]
    assert written == _files(tmp_path / "file") == _files(tmp_path / "stdin")
    plan = json.loads(written["plan.json"])
    assert [chapter["part"] for chapter in plan["chapters"]] == ["first", "last"]
    assert plan["request"] == {
        "period": "quarter",
        "audience": "insider",
        "focus": "Fixture Resistance",
        "length": 1500,
    }
    request = json.loads(written["requests/02.json"])
    assert request["messages"][0]["content"].startswith(
        "chapter: 2 of 2\npart: last\ncovers: 2032-04-01 to 2032-07-01\n"
    )
    assert out.startswith("2 chapters by quarter, max_input_tokens 10000 at 3 characters per token:\n- 1 (first) ")


@pytest.mark.fixture
@pytest.mark.usefixtures("in_fixtures")
def test_constituents_choose_the_atomic_stream_of_the_package_built_from_saves(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = _package(tmp_path, capsys, "none")

    assert main(["narrate", *SAVES, "--constituents", "none", "--output", str(tmp_path / "saves")]) == EXIT_SUCCESS
    assert main(["narrate", "--package", str(package), "--output", str(tmp_path / "file")]) == EXIT_SUCCESS
    assert main(["narrate", *SAVES, "--output", str(tmp_path / "default")]) == EXIT_SUCCESS

    assert _files(tmp_path / "saves") == _files(tmp_path / "file") != _files(tmp_path / "default")
    assert '\\"constituents\\":\\"none\\"' in _files(tmp_path / "saves")["requests/01.json"].decode()


@pytest.mark.fixture
@pytest.mark.usefixtures("in_fixtures")
def test_a_rerun_rewrites_the_same_files_and_removes_stale_requests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "narration"
    (output / "requests").mkdir(parents=True)
    (output / "requests" / "07.json").write_text("{}", encoding="utf-8")
    (output / "requests" / "notes.json").write_text("{}", encoding="utf-8")

    assert main(["narrate", *SAVES, "--output", str(output)]) == EXIT_SUCCESS
    first = _files(output)
    assert main(["narrate", *SAVES, "--output", str(output)]) == EXIT_SUCCESS

    assert _files(output) == first
    assert sorted(first) == ["plan.json", "requests/01.json", "requests/notes.json"]
    assert json.loads(first["plan.json"])["chapters"][0]["part"] == "whole"
    assert "Wrote plan.json and 1 request to" in capsys.readouterr().out


@pytest.mark.fixture
@pytest.mark.usefixtures("in_fixtures")
def test_without_output_only_the_plan_is_printed(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["narrate", *SAVES]) == EXIT_SUCCESS

    out = capsys.readouterr().out
    assert out.startswith("1 chapter by quarter, max_input_tokens 200000 at 3 characters per token:\n- 1 (whole) ")
    assert out.endswith("Nothing written; give --output DIR for the plan and the requests.\n")


@pytest.mark.fixture
@pytest.mark.usefixtures("in_fixtures")
def test_an_interval_over_the_budget_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "narration"

    code = main(["narrate", *SAVES, "--config", str(_settings(tmp_path, 1000)), "--output", str(output)])

    captured = capsys.readouterr()
    assert code == EXIT_USAGE_ERROR
    assert captured.out == ""
    assert "needs about" in captured.err and "over max_input_tokens 1000" in captured.err
    assert not output.exists()


@pytest.mark.fixture
@pytest.mark.usefixtures("in_fixtures")
def test_saves_too_sparse_for_the_period_coarsen_it_unless_it_was_given(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = _package(tmp_path, capsys)
    sparse = json.loads(package.read_text(encoding="utf-8"))
    sparse["saves"][0]["date"] = sparse["intervals"][0]["not_before"] = "2031-07-01T00:00:00"
    package.write_text(json.dumps(sparse), encoding="utf-8")

    assert main(["narrate", "--package", str(package)]) == EXIT_SUCCESS
    captured = capsys.readouterr()
    assert "2031-07-01 to 2032-07-01, 2032 (saves too far apart for a quarter): " in captured.out
    assert captured.err == ""

    assert main(["narrate", "--package", str(package), "--period", "quarter"]) == EXIT_SUCCESS
    captured = capsys.readouterr()
    assert "2031-07-01 to 2032-07-01, 2032-Q2, 2032-Q3: " in captured.out
    assert "the saves are further apart than a quarter in 2032-Q2; --period quarter is kept" in captured.err


def test_usage_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    package = tmp_path / "package.json"
    package.write_text("{}", encoding="utf-8")

    assert main(["narrate"]) == EXIT_USAGE_ERROR
    assert main(["narrate", "--package", str(package), "--min-significance", "minor"]) == EXIT_USAGE_ERROR
    assert main(["narrate", "--package", str(package), "--constituents", "all"]) == EXIT_USAGE_ERROR
    assert main(["narrate", "--package", str(package), "save.json"]) == EXIT_USAGE_ERROR
    assert "give save paths or --package FILE" in capsys.readouterr().err


def test_a_package_without_intervals_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    package = tmp_path / "package.json"
    package.write_text(json.dumps({"saves": [], "intervals": [], "narrative": [], "glossary": []}), encoding="utf-8")

    assert main(["narrate", "--package", str(package)]) == EXIT_USAGE_ERROR
    assert "nothing to narrate" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("text", "message"),
    [("not json", "not valid JSON"), ('{"narrative": []}', "not a narrator package"), ("[]", "not a narrator package")],
)
def test_a_bad_package_is_unsupported_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str, message: str
) -> None:
    package = tmp_path / "package.json"
    package.write_text(text, encoding="utf-8")

    assert main(["narrate", "--package", str(package)]) == EXIT_UNSUPPORTED_INPUT
    captured = capsys.readouterr()
    assert message in captured.err and captured.out == ""


def test_a_missing_package_is_an_input_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["narrate", "--package", str(tmp_path / "absent.json")]) == EXIT_INPUT_ERROR
    assert "cannot read" in capsys.readouterr().err


def test_an_invalid_budget_is_a_config_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = _settings(tmp_path, 10)

    assert main(["narrate", "--package", "-", "--config", str(settings)]) == EXIT_CONFIG_ERROR
    assert "'narrator.max_input_tokens' must be at least 1000" in capsys.readouterr().err


@pytest.mark.fixture
@pytest.mark.usefixtures("in_fixtures")
def test_an_unwritable_output_is_an_output_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")

    assert main(["narrate", *SAVES, "--output", str(blocker)]) == EXIT_OUTPUT_ERROR
    captured = capsys.readouterr()
    assert "cannot write" in captured.err and captured.out == ""
