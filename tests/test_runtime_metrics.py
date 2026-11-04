"""Coverage for the runtime benchmark: timing lines, measurement order, the report and the CLI."""

from __future__ import annotations

import json
import lzma
import os
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures import fixture_path
from tinarrative import cli
from tinarrative.benchmarking import runtime as benchmark_runtime
from tinarrative.benchmarking.manifest import MANIFEST, update_samples
from tinarrative.benchmarking.runtime import MARKER, Side, measure, parse_timings, report

SAVES = ["politics_reverted.json", "politics_before.json", "politics_after.json"]
TIMING_LINES = """\
INFO tinarrative.timing: survey seconds=0.25
INFO tinarrative.timing: survey seconds=0.25
INFO tinarrative.timing: normalize seconds=0.5
INFO tinarrative.timing: save index=0 load=0.75 situation=0.25
INFO tinarrative.timing: normalize seconds=0.5
INFO tinarrative.timing: save index=1 load=0.75 situation=0.25
INFO tinarrative.timing: interval index=0 diff=1.0 analyzers=0.5 reconstruction=0.25 significance=0.25
INFO tinarrative.timing: rule name=faction.takeover seconds=0.5
INFO tinarrative.timing: rule name=war.arc seconds=0.25
INFO tinarrative.timing: aggregate seconds=0.75
tinarrative events: parsing and processing took 4.0s
"""


def _samples(root: Path) -> Path:
    samples = root / "samples"
    campaign = samples / "politics"
    campaign.mkdir(parents=True)
    for name in SAVES:
        (campaign / f"{name}.xz").write_bytes(
            lzma.compress(fixture_path("io", "terra_invicta_json_v1", name).read_bytes())
        )
    manifest = update_samples(samples)
    manifest["campaigns"]["politics"]["description"] = "Synthetic politics sequence."
    (samples / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return samples


def _matrix(root: Path) -> Path:
    matrix = root / "matrix.toml"
    matrix.write_text('[[events]]\nid = "major"\nargs = ["--narrative", "--format", "json"]\n', encoding="utf-8")
    return matrix


def _config(root: Path) -> Path:
    config = root / "config.toml"
    config.write_text("", encoding="utf-8")
    return config


def _fake_python(root: Path, name: str, calls: Path, stderr: str, exit_code: int = 0) -> str:
    """An interpreter stand-in that records its name, argv and timing variable, then prints ``stderr``."""
    script = root / name
    (root / f"{name}.stderr").write_text(stderr, encoding="utf-8")
    script.write_text(
        f"#!/bin/sh\n"
        f'echo "{name} $TINARRATIVE_TIMING ${{TINARRATIVE_LOG_LEVEL:-unset}} $*" >> "{calls}"\n'
        f'cat "{root / f"{name}.stderr"}" >&2\n'
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def _run(seconds: float, stages: dict[str, float] | None, **extra: Any) -> dict[str, Any]:
    timings = None
    if stages is not None:
        timings = {"saves": 4, "stages": stages, "intervals": [1.0, 1.0, 1.0], "rules": {"faction.takeover": 0.5}}
    return {"exit": 0, "seconds": seconds, "max_rss": 500_000_000, "timings": timings, "runs": [seconds], **extra}


def _runtime(base: dict[str, Any] | None, head: dict[str, Any]) -> dict[str, Any]:
    sides = {"head": {"label": "#1 abc", "campaigns": {"camp": head}}}
    if base is not None:
        sides = {"base": {"label": "main def", "campaigns": {"camp": base}}, **sides}
    return {"tool_version": 1, "run": "major", "args": [], "repeats": 2, "samples_sha256": None, "sides": sides}


def test_timing_lines_give_stage_totals_the_interval_series_and_rules() -> None:
    timings = parse_timings(TIMING_LINES)

    assert timings is not None
    assert timings["saves"] == 2
    assert timings["stages"] == {
        "survey": 0.5,
        "decode": 0.5,
        "normalize": 1.0,
        "situation": 0.5,
        "diff": 1.0,
        "analyzers": 0.5,
        "reconstruction": 0.25,
        "significance": 0.25,
        "aggregation": 0.75,
    }
    assert timings["intervals"] == [3.0]
    assert timings["rules"] == {"faction.takeover": 0.5, "war.arc": 0.25}


def test_a_revision_without_timing_lines_has_no_timings() -> None:
    assert parse_timings("tinarrative events: parsing and processing took 4.0s\n") is None


@pytest.mark.skipif(not hasattr(os, "wait4"), reason="the fake interpreter is a POSIX shell script")
def test_sides_alternate_and_each_keeps_its_fastest_run(tmp_path: Path) -> None:
    calls = tmp_path / "calls.log"
    sides = [
        Side("base", _fake_python(tmp_path, "base", calls, "no timing lines\n"), "main"),
        Side("head", _fake_python(tmp_path, "head", calls, TIMING_LINES), "branch"),
    ]

    runtime = measure(
        sides=sides,
        samples=_samples(tmp_path),
        matrix_path=_matrix(tmp_path),
        run_id="major",
        config=_config(tmp_path),
        repeats=3,
        campaign="latest",
        log=None,
    )

    order = [line.split()[0] for line in calls.read_text(encoding="utf-8").splitlines()]
    assert order == ["base", "head", "head", "base", "base", "head"]
    first = calls.read_text(encoding="utf-8").splitlines()[0].split()
    assert first[1:3] == ["1", "unset"]
    assert first[3:6] == ["-m", "tinarrative.cli", "events"]
    assert first[-4:] == ["--campaign", "latest", "--config", str(tmp_path / "config.toml")]
    head = runtime["sides"]["head"]["campaigns"]["politics"]
    assert head["exit"] == 0 and len(head["runs"]) == 3 and head["seconds"] == min(head["runs"])
    assert head["timings"]["stages"]["diff"] == 1.0
    assert runtime["sides"]["base"]["campaigns"]["politics"]["timings"] is None
    assert runtime["sides"]["base"]["label"] == "main"
    assert runtime["args"] == ["--narrative", "--format", "json", "--campaign", "latest"]


@pytest.mark.skipif(not hasattr(os, "wait4"), reason="the fake interpreter is a POSIX shell script")
def test_a_failing_run_records_its_exit_and_error(tmp_path: Path) -> None:
    calls = tmp_path / "calls.log"
    side = Side("head", _fake_python(tmp_path, "head", calls, "tinarrative events: broken\n", exit_code=5), "x")

    runtime = measure(
        sides=[side],
        samples=_samples(tmp_path),
        matrix_path=_matrix(tmp_path),
        run_id="major",
        config=_config(tmp_path),
        repeats=1,
        log=None,
    )

    run = runtime["sides"]["head"]["campaigns"]["politics"]
    assert run["exit"] == 5 and run["error"] == "tinarrative events: broken"
    assert "failed with exit 5" in report(runtime)


@pytest.mark.fixture
def test_a_measurement_of_this_tree_reads_its_own_timing_lines(tmp_path: Path) -> None:
    runtime = measure(
        sides=[Side("head", sys.executable, "test")],
        samples=_samples(tmp_path),
        matrix_path=_matrix(tmp_path),
        run_id="major",
        config=_config(tmp_path),
        repeats=1,
        log=None,
    )

    run = runtime["sides"]["head"]["campaigns"]["politics"]
    assert run["exit"] == 0
    assert run["timings"]["saves"] == len(SAVES)
    assert len(run["timings"]["intervals"]) == len(SAVES) - 1
    assert set(run["timings"]["rules"]) and run["timings"]["stages"]["normalize"] > 0
    assert sum(run["timings"]["stages"].values()) <= run["seconds"]


def test_an_unknown_run_is_a_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no events run 'missing'"):
        measure(
            sides=[Side("head", sys.executable, "x")],
            samples=tmp_path,
            matrix_path=_matrix(tmp_path),
            run_id="missing",
            config=_config(tmp_path),
            repeats=1,
            log=None,
        )


def test_the_report_flags_only_changes_both_relative_and_absolute() -> None:
    stages = {"survey": 1.0, "diff": 4.0, "aggregation": 0.2}
    base = _run(10.0, stages)
    head = _run(8.0, {"survey": 1.05, "diff": 2.0, "aggregation": 0.4})

    text = report(_runtime(base, head), run_url="https://example.invalid/run")

    assert text.startswith(MARKER + "\n## Processing runtime")
    assert "- camp · diff: 4.00s → 2.00s (-50.0%)" in text
    assert "- camp · total: 10.00s → 8.00s (-20.0%)" in text
    assert "aggregation: " not in text  # +100%, but only 0.2s
    assert "survey: " not in text
    assert "| other | 4.80s | 4.55s |" in text
    assert "| peak memory | 500 MB | 500 MB | |" in text
    assert "last third over first third: base ×1.00, head ×1.00" in text
    assert "`faction.takeover` 0.50s (base 0.50s)" in text
    assert text.rstrip().endswith("(https://example.invalid/run).")


def test_a_change_within_the_noise_between_runs_is_not_flagged() -> None:
    base = _run(10.0, {"diff": 4.0}, runs=[10.0, 10.6])
    head = _run(9.0, {"diff": 3.0}, runs=[9.0, 9.5])

    text = report(_runtime(base, head))

    assert "No stage changed by more than the thresholds and the noise between runs." in text
    assert "| total | 10.00s | 9.00s | -10.0% |" in text


def test_a_base_without_timing_lines_is_compared_by_wall_time_only() -> None:
    text = report(_runtime(_run(10.0, None), _run(10.0, {"diff": 4.0})))

    assert "No stage changed by more than the thresholds and the noise between runs." in text
    assert "| diff | – | 4.00s |  |" in text
    assert "camp · base writes no timing lines" in text


def test_a_single_side_is_reported_without_deltas() -> None:
    text = report(_runtime(None, _run(10.0, {"diff": 4.0})))

    assert "`#1 abc` · `events` run `major`" in text
    assert "### Highlights" not in text
    assert "| diff | 4.00s |" in text


def test_runtime_cli_measure_and_report_write_their_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: dict[str, Any] = {}

    def fake_measure(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return _runtime(_run(10.0, {"diff": 4.0}), _run(9.0, {"diff": 3.0}))

    monkeypatch.setattr(benchmark_runtime, "measure", fake_measure)
    out = tmp_path / "out" / "runtime.json"
    samples = _samples(tmp_path)
    argv = ["benchmark", "runtime", "measure", "--samples", str(samples), "--out", str(out), "--repeats", "2"]
    code = cli.main([*argv, "--base-python", "/base/python", "--base-label", "main", "--label", "head"])

    assert code == cli.EXIT_SUCCESS
    assert [side.name for side in captured["sides"]] == ["base", "head"]
    assert captured["sides"][0] == Side("base", "/base/python", "main")
    assert captured["repeats"] == 2 and captured["run_id"] == "major"
    assert json.loads(out.read_text(encoding="utf-8"))["repeats"] == 2

    assert cli.main(["benchmark", "runtime", "report", str(out)]) == cli.EXIT_SUCCESS
    assert "## Processing runtime" in capsys.readouterr().out


def test_runtime_cli_rejects_a_missing_samples_directory(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["benchmark", "runtime", "measure", "--samples", str(tmp_path / "none"), "--out", "x.json"])

    assert code == cli.EXIT_INPUT_ERROR
    assert "not a directory" in capsys.readouterr().err


@pytest.mark.fixture
def test_timing_lines_change_neither_the_output_nor_the_default_log(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    saves = [str(fixture_path("io", "terra_invicta_json_v1", name)) for name in SAVES]
    monkeypatch.delenv("TINARRATIVE_TIMING", raising=False)
    assert cli.main(["events", *saves, "--narrative", "--format", "json"]) == cli.EXIT_SUCCESS
    quiet = capsys.readouterr()
    monkeypatch.setenv("TINARRATIVE_TIMING", "1")
    assert cli.main(["events", *saves, "--narrative", "--format", "json"]) == cli.EXIT_SUCCESS
    timed = capsys.readouterr()

    assert timed.out == quiet.out
    assert "tinarrative.timing" not in quiet.err
    assert "INFO tinarrative.timing: interval index=1 diff=" in timed.err
