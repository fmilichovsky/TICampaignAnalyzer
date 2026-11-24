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
