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
from tinarrative.benchmarking.calibration import cache, timing

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
