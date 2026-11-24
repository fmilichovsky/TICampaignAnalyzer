"""The calibration timing: which requests it replays through the server's handler, and the report's shape."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.benchmarking.calibration_golden import GOLDEN
from tinarrative.benchmarking.calibration import replay, server, timing
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
        assert set(figures) == {"count", "median_seconds", "p95_seconds", "answer_bytes"}
        assert figures["median_seconds"] <= figures["p95_seconds"]
        assert figures["answer_bytes"] > 0
    assert report["requests"][timing.SWEEP]["count"] == 2 * len(timing.requests(INDEX, TABLES)[timing.SWEEP])
    assert report["requests"][timing.FULL]["count"] == 2


def test_a_server_that_cannot_answer_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(timing.TimingError):
        timing.measure(server.Calibration(tmp_path), repeats=1)


def _fake_revision(tmp_path: Path, document: dict[str, object]) -> str:
    """An interpreter that ignores its arguments and prints ``document``, as the other revision's script would."""
    output = tmp_path / "measured.json"
    output.write_text(json.dumps(document), encoding="utf-8")
    script = tmp_path / "fake-python"
    script.write_text(f"#!/bin/sh\ncat '{output}'\n", encoding="utf-8")
    script.chmod(0o755)
    return str(script)


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
        "median_seconds": 0.75,
        "p95_seconds": 1.0,
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
    assert "| Request | Median s (base) | Median s (head)" in text
    assert "| full answer | 0.750 | " in text
    assert "| base switch | n/a | " in text
    assert "`main def`: 7 table rows." in text
    assert f"Head `head abc`: {sum(report['campaigns'].values()):,} table rows." in text


def test_the_other_revision_extracts_from_the_samples_it_is_given(
    calibration: server.Calibration, tmp_path: Path
) -> None:
    seen = tmp_path / "seen"
    output = tmp_path / "measured.json"
    output.write_text(json.dumps(_measured()), encoding="utf-8")
    script = tmp_path / "recording-python"
    script.write_text(f"#!/bin/sh\necho \"$3\" > '{seen}'\ncat '{output}'\n", encoding="utf-8")
    script.chmod(0o755)
    base_samples = tmp_path / "base-samples"
    base_samples.mkdir()

    timing.measure(calibration, repeats=1, base_python=str(script), base_samples=base_samples)

    assert Path(seen.read_text(encoding="utf-8").strip()) == base_samples.resolve()


def test_progress_is_told_in_order_with_each_group_and_round_summed_from_the_timed_requests(
    calibration: server.Calibration,
) -> None:
    steps: list[timing.Progress] = []

    report = timing.measure(calibration, repeats=2, on_progress=steps.append)

    sizes = {kind: len(bodies) for kind, bodies in timing.requests(INDEX, TABLES).items()}
    per_round = sum(sizes.values())
    assert [step.event for step in steps[:3]] == ["start", "warm_up", "round"]
    assert steps[0] == timing.Progress("start", rounds=2, total=per_round)
    assert steps[-1].event == "head_done"
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
