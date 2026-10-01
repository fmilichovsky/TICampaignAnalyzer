"""Golden-output and exit-code coverage for ``tinarrative inspect``."""

import json
from pathlib import Path

import pytest

from tests.fixtures import FIXTURES_ROOT, fixture_path
from tinarrative.cli import (
    EXIT_INPUT_ERROR,
    EXIT_PATH_NOT_FOUND,
    EXIT_SUCCESS,
    EXIT_UNSUPPORTED_INPUT,
    EXIT_USAGE_ERROR,
    main,
)

EXPECTED_ROOT = FIXTURES_ROOT / "inspection"
REPRESENTATIVE = ("io", "terra_invicta_json_v1", "representative_campaign.json")

GOLDEN_CASES = [
    (("io", "terra_invicta_json_v1", "representative_campaign.json"), EXIT_SUCCESS),
    (("io", "terra_invicta_json_v1", "unknown_state_type.json"), EXIT_SUCCESS),
    (("io", "terra_invicta_json_v1", "known_game_version.json"), EXIT_SUCCESS),
    (("io", "terra_invicta_json_v1", "numeric_game_version.json"), EXIT_SUCCESS),
    (("io", "terra_invicta_json_v1", "absent_game_version.json"), EXIT_SUCCESS),
    (
        ("io", "terra_invicta_json_v1", "malformed_truncated.json"),
        EXIT_UNSUPPORTED_INPUT,
    ),
    (("io", "v0", "minimal_save.save"), EXIT_UNSUPPORTED_INPUT),
]


def expected_output_path(fixture_parts: tuple[str, ...]) -> Path:
    _area, fixture_set, name = fixture_parts
    return EXPECTED_ROOT / fixture_set / f"{name}.expected.txt"


@pytest.mark.fixture
@pytest.mark.parametrize(("fixture_parts", "exit_code"), GOLDEN_CASES)
def test_inspect_matches_the_golden_report_for_each_fixture(
    fixture_parts: tuple[str, ...],
    exit_code: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    save_path = fixture_path(*fixture_parts)
    expected = expected_output_path(fixture_parts).read_text(encoding="utf-8")

    assert main(["inspect", str(save_path)]) == exit_code
    first = capsys.readouterr()
    assert main(["inspect", str(save_path)]) == exit_code
    second = capsys.readouterr()

    assert first.out == expected
    assert second.out == first.out
    assert first.err == ""


@pytest.mark.fixture
def test_every_golden_report_belongs_to_an_existing_fixture() -> None:
    goldens = sorted(EXPECTED_ROOT.rglob("*.expected.txt"))
    assert len(goldens) == len(GOLDEN_CASES)

    for golden in goldens:
        fixture_set = golden.parent.name
        fixture_name = golden.name.removesuffix(".expected.txt")
        assert (FIXTURES_ROOT / "io" / fixture_set / fixture_name).is_file(), golden


@pytest.mark.fixture
def test_selected_path_is_rendered_with_bounded_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    pointer = "/gamestates/PavonisInteractive.TerraInvicta.TITimeState/0/Key"

    assert main(["inspect", str(fixture_path(*REPRESENTATIVE)), "-p", pointer]) == 0

    out = capsys.readouterr().out
    assert f"selected paths:\n  {pointer}: object (1 key)\n    {{\n" in out
    assert '      "value": 2\n    }\n' in out
    assert out.endswith("diagnostics: none\n")


@pytest.mark.fixture
def test_missing_paths_are_reported_and_change_the_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = [
        "inspect",
        str(fixture_path(*REPRESENTATIVE)),
        "--path",
        "/nope",
        "--path",
        "/currentID/value/x",
    ]

    assert main(argv) == EXIT_PATH_NOT_FOUND

    out = capsys.readouterr().out
    assert "root: object (2 keys)" in out
    assert "  /nope: not found (missing key 'nope' at root)" in out
    assert "  /currentID/value/x: not found (cannot descend into number at /currentID/value)" in out
    assert "pointer_not_found: /nope: missing key 'nope' at root" in out


@pytest.mark.fixture
def test_json_format_is_machine_readable(capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["inspect", str(fixture_path(*REPRESENTATIVE)), "--format", "json"]

    assert main(argv) == EXIT_SUCCESS

    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "ok"
    assert report["file_name"] == "representative_campaign.json"
    assert report["file"]["size_bytes"] == 2366
    assert [entry["key"] for entry in report["top_level"]] == [
        "currentID",
        "gamestates",
    ]
    assert len(report["second_level"]["gamestates"]) == 6
    assert report["diagnostics"] == []
    domains = {entry["domain"]["domain"] for entry in report["identity"]["domains"]}
    assert {"faction", "technology", "organization"} <= domains


@pytest.mark.fixture
def test_render_limits_are_applied_to_selected_paths(
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = [
        "inspect",
        str(fixture_path(*REPRESENTATIVE)),
        "-p",
        "/gamestates",
        "--max-items",
        "2",
        "--max-depth",
        "1",
        "--format",
        "json",
    ]

    assert main(argv) == EXIT_SUCCESS

    value = json.loads(capsys.readouterr().out)["paths"][0]["value"]
    assert value == {
        "PavonisInteractive.TerraInvicta.TIMetadataState": "[...]",
        "PavonisInteractive.TerraInvicta.TITimeState": "[...]",
        "...": "(+4 keys)",
    }


def test_inspect_without_a_save_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as result:
        main(["inspect"])

    assert result.value.code == EXIT_USAGE_ERROR
    assert capsys.readouterr().out == ""


def test_unreadable_save_is_an_input_error_without_a_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing.json"

    assert main(["inspect", str(missing)]) == EXIT_INPUT_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "cannot read" in captured.err

    assert main(["inspect", str(tmp_path)]) == EXIT_INPUT_ERROR
    assert capsys.readouterr().out == ""


def test_negative_limits_are_usage_errors(capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["inspect", str(fixture_path(*REPRESENTATIVE)), "--max-items", "-1"]

    with pytest.raises(SystemExit) as result:
        main(argv)

    assert result.value.code == 2
    assert "expected a value >= 0" in capsys.readouterr().err
