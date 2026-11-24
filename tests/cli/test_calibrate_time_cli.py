"""`benchmark calibrate time`: argument wiring, the cache it refreshes, its exit codes and the shape of its JSON."""

from __future__ import annotations

import json
import shutil
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from tests.benchmark_support import synthetic_samples
from tests.benchmarking.calibration_golden import GOLDEN
from tinarrative import cli
from tinarrative.benchmarking.calibration import cache, progress, timing

COMMAND = ["benchmark", "calibrate", "time"]


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Synthetic samples, and a refresh that leaves the golden table in the cache directory."""
    samples = synthetic_samples(tmp_path)

    def refresh(samples: Path, out: Path, **_: Any) -> cache.CacheCheck:
        shutil.copytree(GOLDEN, out, dirs_exist_ok=True)
        return cache.check(samples, out)

    monkeypatch.setattr(cache, "refresh", refresh)
    return samples, tmp_path / "out"


def timed(paths: tuple[Path, Path], *flags: str) -> tuple[int, str, str]:
    samples, out = paths
    return run_cli([*COMMAND, "--samples", str(samples), "--out", str(out), *flags])


def test_the_report_is_printed_as_json_with_a_figure_set_per_request_type(paths: tuple[Path, Path]) -> None:
    code, stdout, stderr = timed(paths, "--repeats", "1")

    assert code == cli.EXIT_SUCCESS, stderr
    report = json.loads(stdout)
    assert set(report["requests"]) == {timing.FULL, timing.SWEEP, timing.TYPE_FILTER, timing.BASE_SWITCH}
    for figures in report["requests"].values():
        assert set(figures) == {"count", "median_seconds", "p95_seconds", "answer_bytes"}
    assert report["campaigns"]


def test_the_report_can_be_written_to_a_file(paths: tuple[Path, Path], tmp_path: Path) -> None:
    target = tmp_path / "timing.json"

    code, stdout, stderr = timed(paths, "--repeats", "1", "--output", str(target))

    assert code == cli.EXIT_SUCCESS, stderr
    assert stdout == ""
    assert set(json.loads(target.read_text(encoding="utf-8"))) >= {"requests", "campaigns", "key"}


def test_a_report_that_cannot_be_written_is_an_output_error(paths: tuple[Path, Path], tmp_path: Path) -> None:
    code, _, stderr = timed(paths, "--repeats", "1", "--output", str(tmp_path / "missing" / "timing.json"))

    assert code == cli.EXIT_OUTPUT_ERROR
    assert "tinarrative benchmark calibrate time" in stderr


def test_samples_that_are_not_a_directory_are_an_input_error(tmp_path: Path) -> None:
    code, _, stderr = run_cli([*COMMAND, "--samples", str(tmp_path / "none"), "--out", str(tmp_path / "out")])

    assert code == cli.EXIT_INPUT_ERROR
    assert "not a directory" in stderr


def test_repeats_must_be_positive(paths: tuple[Path, Path]) -> None:
    with pytest.raises(SystemExit):
        timed(paths, "--repeats", "0")


def _fake_python(tmp_path: Path) -> str:
    """An interpreter standing in for another revision: it answers every request type but the base switch."""
    kinds = [timing.FULL, timing.SWEEP, timing.TYPE_FILTER, timing.BASE_SWITCH]
    document = {
        "key": "base-key",
        "campaigns": {"alpha": 3},
        "seconds": {kind: None if kind == timing.BASE_SWITCH else [0.2, 0.4] for kind in kinds},
        "sizes": {kind: None if kind == timing.BASE_SWITCH else [10, 30] for kind in kinds},
    }
    data = tmp_path / "base.json"
    data.write_text(json.dumps(document), encoding="utf-8")
    script = tmp_path / "fake-python"
    script.write_text(f"#!/bin/sh\ncat '{data}'\n", encoding="utf-8")
    script.chmod(0o755)
    return str(script)


def test_another_revision_adds_a_base_report_with_n_a_and_a_markdown_table(
    paths: tuple[Path, Path], tmp_path: Path
) -> None:
    table = tmp_path / "calibration.md"

    code, stdout, stderr = timed(
        paths,
        "--repeats",
        "1",
        "--base-python",
        _fake_python(tmp_path),
        "--base-label",
        "main abc1234",
        "--label",
        "pr def5678",
        "--report",
        str(table),
    )

    assert code == cli.EXIT_SUCCESS, stderr
    report = json.loads(stdout)
    assert report["base"]["requests"][timing.BASE_SWITCH] is None
    assert report["base"]["requests"][timing.FULL]["answer_bytes"] == 20
    text = table.read_text(encoding="utf-8")
    assert "| base switch | n/a | " in text
    assert "`main abc1234`: 3 table rows."
    assert "Head `pr def5678`:" in text


def test_a_report_needs_another_revision_to_compare(paths: tuple[Path, Path], tmp_path: Path) -> None:
    code, _, stderr = timed(paths, "--report", str(tmp_path / "calibration.md"))

    assert code == cli.EXIT_USAGE_ERROR
    assert "--base-python" in stderr


def test_an_interpreter_that_cannot_be_run_is_a_usage_error(paths: tuple[Path, Path], tmp_path: Path) -> None:
    code, _, stderr = timed(paths, "--repeats", "1", "--base-python", str(tmp_path / "no-python"))

    assert code == cli.EXIT_USAGE_ERROR
    assert "no-python" in stderr


def test_base_samples_that_are_not_a_directory_are_an_input_error(paths: tuple[Path, Path], tmp_path: Path) -> None:
    code, _, stderr = timed(
        paths, "--base-python", _fake_python(tmp_path), "--base-samples", str(tmp_path / "none"), "--repeats", "1"
    )

    assert code == cli.EXIT_INPUT_ERROR
    assert "not a directory" in stderr


def test_progress_goes_to_stderr_by_round_and_group_and_leaves_stdout_as_the_json(paths: tuple[Path, Path]) -> None:
    code, stdout, stderr = timed(paths, "--repeats", "2")

    assert code == cli.EXIT_SUCCESS, stderr
    json.loads(stdout)
    lines = stderr.splitlines()
    prefix = "tinarrative benchmark calibrate time: "
    assert all(line.startswith(prefix) for line in lines)
    body = [line.removeprefix(prefix) for line in lines]
    assert "The calibration table in" in body[0] and body[0].endswith("is fresh.")
    assert body[1].startswith("head: 2 rounds of ")
    assert body[2] == "head: starting round 1/2"
    assert body[3].startswith("  full: 1 request in ")
    assert body[4].startswith("  sweep: ") and " requests in " in body[4]
    assert body[5].startswith("  type filter: 1 request in ")
    assert body[6].startswith("  base switch: 1 request in ")
    assert body[7].startswith("head: round 1/2 done in ")
    assert [line for line in body if line.startswith("head: starting round")] == [
        "head: starting round 1/2",
        "head: starting round 2/2",
    ]
    assert body[-1].startswith("head: measured in ")


def test_the_base_side_is_announced_and_its_time_reported_after_the_head(
    paths: tuple[Path, Path], tmp_path: Path
) -> None:
    code, _, stderr = timed(paths, "--repeats", "1", "--base-python", _fake_python(tmp_path))

    assert code == cli.EXIT_SUCCESS, stderr
    lines = stderr.splitlines()
    announced = next(i for i, line in enumerate(lines) if ": base: extracting its table from " in line)
    assert "head: measured in " in lines[announced - 1]
    assert ": base: done in " in lines[-1]


def test_each_campaign_extraction_is_timed_from_the_one_before_it_finished(capsys: pytest.CaptureFixture[str]) -> None:
    reporter = cli._ExtractionReporter("tinarrative benchmark calibrate time: base")
    reporter.stale(cache.CacheCheck(Path("out"), "key", None))

    def snapshot(elapsed: float, alpha: progress.Phase, beta: progress.Phase) -> progress.ProgressSnapshot:
        steps = (progress.CampaignStep("alpha", alpha, 34, 34), progress.CampaignStep("beta", beta, 1, 34))
        return progress.ProgressSnapshot(steps, 0.0, 1.0, elapsed)

    reporter.progress(snapshot(34.1, "done", "survey"))
    reporter.progress(snapshot(95.9, "done", "done"))

    err = capsys.readouterr().err
    assert "Extracted alpha (34 saves) in 34.1s" in err
    assert "Extracted beta (34 saves) in 61.8s" in err
