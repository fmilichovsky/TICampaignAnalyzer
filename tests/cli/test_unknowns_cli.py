"""``tinarrative unknowns``: scanning, reporting, registry recording and exit codes."""

import json
import shutil
from pathlib import Path

import pytest

from tests.fixtures import fixture_path
from tinarrative.cli import (
    EXIT_INPUT_ERROR,
    EXIT_REGISTRY_ERROR,
    EXIT_SUCCESS,
    EXIT_UNSUPPORTED_INPUT,
    EXIT_USAGE_ERROR,
    main,
)
from tinarrative.maintenance import REGISTRY_ENV_VAR
from tinarrative.maintenance.registry import load_registry

FIXTURE_SET = ("io", "terra_invicta_json_v1")


@pytest.fixture
def save_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "saves"
    directory.mkdir()
    for name in ("political_control.json", "campaign_assets.json", "malformed_truncated.json"):
        shutil.copy(fixture_path(*FIXTURE_SET, name), directory / name)
    return directory


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(REGISTRY_ENV_VAR, raising=False)


def test_directory_scan_is_deterministic_and_lists_skipped_files(save_dir: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["unknowns", str(save_dir)]) == EXIT_SUCCESS
    first = capsys.readouterr()
    assert main(["unknowns", str(save_dir)]) == EXIT_SUCCESS
    second = capsys.readouterr()
    assert first.out == second.out and first.err == ""
    lines = first.out.splitlines()
    assert lines[0] == "tinarrative unknowns report"
    assert f"  {save_dir / 'campaign_assets.json'}: 0 unknown structures" in lines
    assert f"  {save_dir / 'political_control.json'}: 2 unknown structures" in lines
    assert any(
        line.startswith(f"  {save_dir / 'malformed_truncated.json'}: skipped (MalformedSaveError:") for line in lines
    )
    assert "findings: 2 across 2 saves" in lines
    assert "  unknown_field TINationState.fixtureOnlyUndocumentedField: 1 occurrence, 1 save" in lines
    assert "    shape: number" in lines
    assert "  unknown_state_type TIFixtureUnknownState: 1 entry, 1 save" in lines
    assert "    shape: object; keys $type, ID, archived, displayName, exists, templateName" in lines
    assert lines[-1] == "registry: not updated"


def test_json_report(save_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["unknowns", str(save_dir / "political_control.json"), "--format", "json"]) == EXIT_SUCCESS
    data = json.loads(capsys.readouterr().out)
    assert data["registry"] is None
    assert data["saves"] == [
        {
            "path": str(save_dir / "political_control.json"),
            "status": "scanned",
            "findings": 2,
            "game_version": None,
            "error": None,
            "error_class": None,
        }
    ]
    assert [finding["kind"] for finding in data["findings"]] == ["unknown_field", "unknown_state_type"]
    assert data["findings"][0]["saves"] == 1 and data["findings"][0]["shape"]["types"] == ["number"]


def test_registry_flag_writes_and_env_var_is_the_fallback(
    save_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    flagged = tmp_path / "flagged.json"
    from_env = tmp_path / "from-env.json"
    assert main(["unknowns", str(save_dir), "--registry", str(flagged)]) == EXIT_SUCCESS
    out = capsys.readouterr().out
    assert out.splitlines()[-1] == f"registry: {flagged}: 2 added, 0 updated, 0 pruned, 2 total"
    assert [str(entry.key) for entry in load_registry(flagged).entries] == [
        "unknown_field TINationState.fixtureOnlyUndocumentedField",
        "unknown_state_type TIFixtureUnknownState",
    ]
    monkeypatch.setenv(REGISTRY_ENV_VAR, str(from_env))
    assert main(["unknowns", str(save_dir)]) == EXIT_SUCCESS
    assert from_env.exists()
    assert main(["unknowns", str(save_dir), "--registry", str(flagged)]) == EXIT_SUCCESS
    assert capsys.readouterr().out.splitlines()[-1] == f"registry: {flagged}: 0 added, 2 updated, 0 pruned, 2 total"
    text = flagged.read_text(encoding="utf-8")
    assert str(tmp_path) not in text and "political_control" not in text


def test_exit_codes_follow_explicit_inputs_only(save_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["unknowns", str(tmp_path / "missing.json")]) == EXIT_INPUT_ERROR
    assert "skipped (FileNotFoundError:" in capsys.readouterr().out
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["unknowns", str(empty)]) == EXIT_INPUT_ERROR
    assert "skipped (EmptyDirectory: the directory holds no files)" in capsys.readouterr().out
    assert main(["unknowns", str(save_dir / "malformed_truncated.json")]) == EXIT_UNSUPPORTED_INPUT
    assert main(["unknowns", str(save_dir / "malformed_truncated.json"), str(tmp_path / "missing.json")]) == (
        EXIT_INPUT_ERROR
    )
    capsys.readouterr()
    assert main(["unknowns", str(save_dir), "--registry", str(tmp_path)]) == EXIT_REGISTRY_ERROR
    captured = capsys.readouterr()
    assert captured.out.startswith("tinarrative unknowns report") and "registry: not updated" in captured.out
    assert captured.err.startswith(f"tinarrative unknowns: cannot update registry {tmp_path}: cannot read registry")
    assert "Traceback" not in captured.err


def test_help_and_usage_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as result:
        main(["unknowns", "--help"])
    assert result.value.code == EXIT_SUCCESS
    with pytest.raises(SystemExit) as result:
        main(["unknowns"])
    assert result.value.code == EXIT_USAGE_ERROR
