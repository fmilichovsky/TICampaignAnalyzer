"""The calibration timing: which requests it replays through the server's handler, and the report's shape."""

from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from tests.benchmark_support import synthetic_samples
from tests.benchmarking.calibration_golden import GOLDEN
from tinarrative.benchmarking.calibration import replay, server, timing
from tinarrative.benchmarking.calibration.progress import CampaignStep, ProgressSnapshot
from tinarrative.benchmarking.calibration.table import write_status

INDEX, TABLES, DRAFTS = replay.load(GOLDEN)


@pytest.fixture
def calibration(tmp_path: Path) -> server.Calibration:
    out = tmp_path / "out"
    shutil.copytree(GOLDEN, out)
    write_status(out, {"key": "golden", "state": "fresh", "message": "", "written_at": "2026-01-01T00:00:00+00:00"})
    return server.Calibration(out)


def test_every_request_the_timing_sends_is_a_state_the_server_reads() -> None:
    for kind, bodies in timing.requests(INDEX, TABLES).items():
        assert bodies, kind
        for body in bodies:
            answered = server.answer(INDEX, TABLES, DRAFTS, body)
            assert "error" not in answered, (kind, body)


def test_the_sweep_spans_the_focus_measures_slider_domain_with_distinct_rise_shares() -> None:
    bodies = timing.requests(INDEX, TABLES)[timing.SWEEP]
    measure = next(iter(INDEX["measures"]))
    rises = [body["state"]["rises"][measure] for body in bodies]

    assert len(set(rises)) == len(rises) > 1
    assert rises == sorted(rises)


def test_the_filter_and_the_base_switch_change_what_they_name() -> None:
    requests = timing.requests(INDEX, TABLES)
    code = replay.default_state(INDEX)

    filtered = server.state_from_values(requests[timing.TYPE_FILTER][0]["state"], INDEX)
    switched = server.state_from_values(requests[timing.BASE_SWITCH][0]["state"], INDEX)

    assert filtered.types
    assert replay.switched_types(code, INDEX) == {}
    assert replay.switched_types(switched, INDEX)


def test_the_report_names_each_request_type_with_its_figures_and_the_tables_row_counts(
    calibration: server.Calibration,
) -> None:
    report = timing.measure(calibration, repeats=2)

    assert json.loads(json.dumps(report)) == report
    assert report["key"] == INDEX["key"]
    assert report["campaigns"] == {name: len(rows) for name, rows in TABLES.items()}
    assert report["sweep_answers"] == timing.SWEEP_ANSWERS
    assert set(report["requests"]) == {timing.FULL, timing.SWEEP, timing.TYPE_FILTER, timing.BASE_SWITCH}
    for figures in report["requests"].values():
        assert set(figures) == {"count", "median_ms", "p95_ms", "answer_bytes"}
        assert figures["median_ms"] <= figures["p95_ms"]
        assert figures["answer_bytes"] > 0
    assert report["requests"][timing.SWEEP]["count"] == 2 * len(timing.requests(INDEX, TABLES)[timing.SWEEP])
    assert report["requests"][timing.FULL]["count"] == 2


def test_a_server_that_cannot_answer_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(timing.TimingError):
        timing.measure(server.Calibration(tmp_path), repeats=1)


def _fake_revision(
    tmp_path: Path, document: dict[str, object], *, stderr: Sequence[str] = (), before: str = "", status: int = 0
) -> str:
    """An interpreter that writes ``stderr`` lines, then ``document`` as its result (the script's third argument), as
    the other revision's script would; ``before`` runs first and ``status`` is its exit code."""
    output = tmp_path / "measured.json"
    output.write_text(json.dumps(document), encoding="utf-8")
    lines = tmp_path / "stderr.txt"
    lines.write_text("".join(f"{line}\n" for line in stderr), encoding="utf-8")
    script = tmp_path / "fake-python"
    script.write_text(
        f"#!/bin/sh\n{before}\ncat '{lines}' >&2\ncp '{output}' \"$5\"\nexit {status}\n", encoding="utf-8"
    )
    script.chmod(0o755)
    return str(script)


def _line(event: str, **fields: object) -> str:
    return timing.PROGRESS_PREFIX + json.dumps({"event": event, **fields})


def _measured(*, without: str | None = None) -> dict[str, object]:
    asked = timing.requests(INDEX, TABLES)
    return {
        "key": "base-key",
        "campaigns": {"alpha": 7},
        "seconds": {kind: None if kind == without else [0.5, 1.0] for kind in asked},
        "sizes": {kind: None if kind == without else [100, 300] for kind in asked},
    }


def test_another_revision_is_measured_through_its_own_interpreter_and_lacks_n_a_answer_types(
    calibration: server.Calibration, tmp_path: Path
) -> None:
    python = _fake_revision(tmp_path, _measured(without=timing.BASE_SWITCH))

    report = timing.measure(calibration, repeats=2, base_python=python, base_samples=tmp_path)

    base = report["base"]
    assert json.loads(json.dumps(report)) == report
    assert base["key"] == "base-key"
    assert base["campaigns"] == {"alpha": 7}
    assert base["requests"][timing.BASE_SWITCH] is None
    assert base["requests"][timing.FULL] == {
        "count": 2,
        "median_ms": 750.0,
        "p95_ms": 1000.0,
        "answer_bytes": 200,
    }
    assert set(base["requests"]) == set(report["requests"])


def test_an_interpreter_that_fails_is_a_timing_error(calibration: server.Calibration, tmp_path: Path) -> None:
    script = tmp_path / "broken-python"
    script.write_text("#!/bin/sh\necho 'ImportError: no cache' >&2\nexit 1\n", encoding="utf-8")
    script.chmod(0o755)

    with pytest.raises(timing.TimingError, match="ImportError"):
        timing.measure(calibration, repeats=1, base_python=str(script), base_samples=tmp_path)


def test_the_markdown_lists_base_and_head_figures_per_request_type_with_n_a_and_row_counts(
    calibration: server.Calibration, tmp_path: Path
) -> None:
    python = _fake_revision(tmp_path, _measured(without=timing.BASE_SWITCH))
    report = timing.measure(calibration, repeats=2, base_python=python, base_samples=tmp_path)

    text = timing.markdown(report, report["base"], head_label="head abc", base_label="main def")

    assert text.startswith(timing.MARKER + "\n")
    assert "| Request | Median ms (base) | Median ms (head)" in text
    assert "| full answer | 750.0 | " in text
    assert "| base switch | n/a | " in text
    assert "`main def`: 7 table rows." in text
    assert f"Head `head abc`: {sum(report['campaigns'].values()):,} table rows." in text


def _report(median: float, size: int, *, kinds: tuple[str, ...] = (timing.FULL, timing.SWEEP)) -> dict[str, object]:
    figures = {"count": 5, "median_ms": median, "p95_ms": median, "answer_bytes": size}
    return {"key": "k", "campaigns": {"alpha": 7}, "repeats": 5, "requests": {kind: figures for kind in kinds}}


def test_the_markdown_leads_with_the_changes_of_each_request_and_keeps_the_raw_figures_below() -> None:
    base, head = _report(2000.0, 1000), _report(2500.0, 1000)

    text = timing.markdown(head, base, head_label="h", base_label="b")

    assert "Changed: full answer median ▲ +500.0 ms (+25.0%); sweep request median ▲ +500.0 ms (+25.0%)." in text
    assert "| full answer | ▲ +500.0 ms (+25.0%) | ▲ +500.0 ms (+25.0%) | 0 |" in text
    assert "| type filter | – | – | – |" in text
    assert text.index("| Request | Δ median ms") < text.index("<details>") < text.index("| Median ms (base)")
    assert "| full answer | 2,000.0 | 2,500.0 |" in text


def test_the_markdown_flags_neither_a_median_change_under_the_threshold_nor_a_one_byte_change() -> None:
    base, head = _report(2000.0, 1_000_000), _report(2200.0, 1_000_001)

    text = timing.markdown(head, base, head_label="h", base_label="b")

    assert "Changed:" not in text
    assert "No median change of 15%+ nor answer size change of 1%+." in text
    assert "▲ +200.0 ms (+10.0%)" in text


def test_the_markdown_flags_a_size_change_of_one_per_cent() -> None:
    base, head = _report(2000.0, 1000), _report(2000.0, 900)

    text = timing.markdown(head, base, head_label="h", base_label="b")

    assert "full answer bytes ▼ -100 (-10.0%)" in text


def test_the_other_revision_extracts_from_the_samples_it_is_given(
    calibration: server.Calibration, tmp_path: Path
) -> None:
    seen = tmp_path / "seen"
    script = _fake_revision(tmp_path, _measured(), before=f"echo \"$3\" > '{seen}'\necho \"$8\" >> '{seen}'")
    base_samples = tmp_path / "base-samples"
    base_samples.mkdir()

    timing.measure(calibration, repeats=1, base_python=script, base_samples=base_samples, base_jobs=3)

    samples, jobs = seen.read_text(encoding="utf-8").splitlines()
    assert Path(samples) == base_samples.resolve()
    assert jobs == "3"


def test_progress_is_told_in_order_with_each_group_and_round_summed_from_the_timed_requests(
    calibration: server.Calibration,
) -> None:
    steps: list[timing.Progress] = []

    report = timing.measure(calibration, repeats=2, on_progress=steps.append)

    sizes = {kind: len(bodies) for kind, bodies in timing.requests(INDEX, TABLES).items()}
    per_round = sum(sizes.values())
    assert [step.event for step in steps[:3]] == ["start", "warm_up", "round"]
    assert steps[0] == timing.Progress("start", rounds=2, total=per_round)
    assert steps[-1] == timing.Progress("measured", seconds=steps[-1].seconds)
    assert [step.event for step in steps].count("request") == 2 * per_round
    groups = [step for step in steps if step.event == "group" and step.round == 1]
    assert {step.kind: step.total for step in groups} == sizes
    done = [step for step in steps if step.event == "round_done"]
    assert [(step.round, step.rounds) for step in done] == [(1, 2), (2, 2)]
    assert sum(step.seconds for step in done) == pytest.approx(steps[-1].seconds)
    figures = report["requests"][timing.SWEEP]
    assert figures["count"] == 2 * sizes[timing.SWEEP]
    sweep_requests = [
        step for step in steps if step.event == "request" and step.kind == timing.SWEEP and step.round == 1
    ]
    assert [step.done for step in sweep_requests] == list(range(1, sizes[timing.SWEEP] + 1))


def test_a_report_without_a_listener_is_the_same_shape(calibration: server.Calibration) -> None:
    quiet = timing.measure(calibration, repeats=1)
    heard = timing.measure(calibration, repeats=1, on_progress=lambda _: None)

    assert quiet.keys() == heard.keys()
    assert quiet["requests"].keys() == heard["requests"].keys()


def test_the_other_revision_streams_its_extraction_and_its_timing_as_it_goes(
    calibration: server.Calibration, tmp_path: Path
) -> None:
    python = _fake_revision(
        tmp_path,
        _measured(without=timing.BASE_SWITCH),
        stderr=[
            _line("extraction", campaigns=[["alpha", "sequence", 2, 3]], done_work=1.0, total_work=4.0, elapsed=2.0),
            "a warning the revision printed",
            _line("warm_up"),
            _line("skipped", kind=timing.BASE_SWITCH),
            _line("start", rounds=1, total=2),
            _line("round", round=1, rounds=1),
            _line("request", round=1, rounds=1, kind=timing.FULL, done=1, total=1),
            _line("group", round=1, rounds=1, kind=timing.FULL, total=1, seconds=0.5),
            _line("round_done", round=1, rounds=1, seconds=0.5),
            _line("measured", seconds=0.5),
        ],
    )
    steps: list[timing.Progress] = []
    snapshots: list[ProgressSnapshot] = []

    timing.measure(
        calibration,
        repeats=1,
        base_python=python,
        base_samples=tmp_path,
        on_progress=steps.append,
        on_extraction=snapshots.append,
    )

    assert snapshots == [
        ProgressSnapshot((CampaignStep("alpha", "sequence", 2, 3),), done_work=1.0, total_work=4.0, elapsed=2.0)
    ]
    head = [step.event for step in steps if step.side == "head"]
    base = [step for step in steps if step.side == "base"]
    assert head[-2:] == ["measured", "base"]
    assert [step.event for step in base] == [
        "warm_up",
        "skipped",
        "start",
        "round",
        "request",
        "group",
        "round_done",
        "measured",
    ]
    assert base[1].kind == timing.BASE_SWITCH
    assert base[-1].seconds == 0.5


def test_a_revision_that_dies_mid_stream_names_its_last_line_that_is_not_progress(
    calibration: server.Calibration, tmp_path: Path
) -> None:
    python = _fake_revision(
        tmp_path,
        _measured(),
        stderr=[_line("warm_up"), "RuntimeError: the table broke", _line("start", rounds=1, total=2)],
        status=1,
    )
    steps: list[timing.Progress] = []

    with pytest.raises(timing.TimingError, match="the table broke"):
        timing.measure(calibration, repeats=1, base_python=python, base_samples=tmp_path, on_progress=steps.append)

    assert [step.event for step in steps if step.side == "base"] == ["warm_up", "start"]


def test_a_progress_line_that_cannot_be_read_is_a_timing_error(calibration: server.Calibration, tmp_path: Path) -> None:
    python = _fake_revision(tmp_path, _measured(), stderr=[timing.PROGRESS_PREFIX + "{not json"])

    with pytest.raises(timing.TimingError, match="progress"):
        timing.measure(calibration, repeats=1, base_python=python, base_samples=tmp_path)


def test_the_revision_script_run_by_this_interpreter_reports_like_the_head(
    calibration: server.Calibration, tmp_path: Path
) -> None:
    samples = synthetic_samples(tmp_path)
    steps: list[timing.Progress] = []
    snapshots: list[ProgressSnapshot] = []

    report = timing.measure(
        calibration,
        repeats=2,
        base_python=sys.executable,
        base_samples=samples,
        base_jobs=1,
        on_progress=steps.append,
        on_extraction=snapshots.append,
    )

    assert snapshots and snapshots[-1].fraction == 1.0
    assert {step.name for step in snapshots[-1].campaigns} == {"politics"}
    base = [step for step in steps if step.side == "base"]
    head = [step for step in steps if step.side == "head" and step.event != "base"]
    skipped = {step.kind for step in base if step.event == "skipped"}
    assert base[0].event == "warm_up"  # the check of which types it answers, before it knows its total
    assert [(step.event, step.kind) for step in base if step.event not in {"warm_up", "skipped"}] == [
        (step.event, step.kind) for step in head if step.event != "warm_up" and step.kind not in skipped
    ]
    timed = [step for step in base if step.event == "request"]
    assert len(timed) == base[[step.event for step in base].index("start")].total * 2
    assert {step.kind for step in timed} == set(report["base"]["requests"]) - skipped
    assert base[-1].event == "measured"
    for kind in skipped:
        assert report["base"]["requests"][kind] is None
