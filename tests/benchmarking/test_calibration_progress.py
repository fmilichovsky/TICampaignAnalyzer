"""The progress of an extraction of the calibration table: the work credited, the time left and its reading."""

from __future__ import annotations

import threading

import pytest

from tinarrative.benchmarking.calibration.progress import (
    ESTIMATE_FROM,
    ExtractionProgress,
    ProgressSnapshot,
    phase_weights,
)

SIZES = {"first": {"a.json": 100, "b.json": 300}, "second": {"c.json": 600}}
TOTAL = sum(sum(saves.values()) for saves in SIZES.values())
SURVEY, SEQUENCE = phase_weights(1)["survey"], phase_weights(1)["sequence"]


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_the_weights_of_one_process_cover_the_whole_work_and_those_of_more_workers_less() -> None:
    assert sum(phase_weights(1).values()) == pytest.approx(1.0)
    assert sum(phase_weights(14).values()) < sum(phase_weights(4).values()) < 1.0
    assert phase_weights(14)["narrative"] == phase_weights(1)["narrative"]
    assert ExtractionProgress(SIZES).snapshot().total_work == pytest.approx(TOTAL)


def test_a_campaign_with_more_workers_has_less_work_in_the_total() -> None:
    jobs = {"first": 1, "second": 14}
    expected = 400 * sum(phase_weights(1).values()) + 600 * sum(phase_weights(14).values())

    assert ExtractionProgress(SIZES, jobs).snapshot().total_work == pytest.approx(expected)


def test_each_save_is_credited_by_its_size_and_phase_weight_once_whatever_order_it_finishes_in() -> None:
    progress = ExtractionProgress(SIZES)
    first = progress.campaign("first")

    first.phase("survey")
    first.saves_done(["b.json"])
    first.saves_done(["b.json", "unknown.json"])
    assert progress.snapshot().done_work == pytest.approx(300 * SURVEY)

    first.saves_done(["a.json"])
    first.phase("sequence")
    first.saves_done(["b.json", "a.json"])

    assert progress.snapshot().done_work == pytest.approx(400 * (SURVEY + SEQUENCE))


def test_a_phase_that_reports_no_saves_is_credited_whole_when_it_ends() -> None:
    progress = ExtractionProgress(SIZES)
    first = progress.campaign("first")

    first.phase("decompress")
    first.saves_done(["a.json", "b.json"])
    assert progress.snapshot().done_work == 0

    first.phase("survey")
    assert progress.snapshot().done_work == pytest.approx(400 * phase_weights(1)["decompress"])


def test_leaving_a_save_phase_credits_the_saves_it_did_not_report() -> None:
    """A merged duplicate is never reported by the sequence phase, yet a finished campaign is fully credited."""
    progress = ExtractionProgress(SIZES)
    first = progress.campaign("first")

    first.phase("survey")
    first.saves_done(["a.json"])
    first.phase("sequence")
    first.phase("narrative")
    first.phase("done")

    snapshot = progress.snapshot()
    assert snapshot.done_work == pytest.approx(400 - 400 * phase_weights(1)["decompress"])
    assert [(step.name, step.phase, step.done, step.total) for step in snapshot.campaigns] == [
        ("first", "done", 2, 2),
        ("second", "waiting", 0, 1),
    ]


def test_the_time_left_follows_the_throughput_once_enough_work_is_done() -> None:
    clock = Clock()
    progress = ExtractionProgress(SIZES, clock=clock)
    second = progress.campaign("second")
    second.phase("survey")

    clock.now = 10.0
    assert progress.snapshot().fraction < ESTIMATE_FROM
    assert progress.snapshot().remaining is None

    second.saves_done(["c.json"])
    done = 600 * SURVEY
    assert progress.snapshot().remaining == pytest.approx(10.0 * (TOTAL - done) / done)


def test_no_time_left_is_estimated_once_all_is_done() -> None:
    clock = Clock()
    progress = ExtractionProgress(SIZES, clock=clock)
    clock.now = 5.0
    for name in SIZES:
        for phase in ("decompress", "survey", "sequence", "narrative", "done"):
            progress.campaign(name).phase(phase)

    assert progress.snapshot().fraction == 1.0
    assert progress.snapshot().remaining is None


def test_every_change_is_told_with_a_snapshot() -> None:
    seen: list[ProgressSnapshot] = []
    progress = ExtractionProgress(SIZES, on_change=seen.append)
    first = progress.campaign("first")

    first.phase("survey")
    first.saves_done(["a.json"])
    first.saves_done(["a.json"])

    assert [snapshot.done_work for snapshot in seen] == [0, pytest.approx(100 * SURVEY)]


def test_changes_from_several_threads_are_told_one_at_a_time_and_in_order() -> None:
    sizes = {"many": {f"{index}.json": 1 for index in range(400)}}
    seen: list[float] = []
    inside = threading.Lock()

    def observed(snapshot: ProgressSnapshot) -> None:
        assert inside.acquire(blocking=False), "two snapshots were told at once"
        seen.append(snapshot.done_work)
        inside.release()

    progress = ExtractionProgress(sizes, on_change=observed)
    many = progress.campaign("many")
    many.phase("survey")
    names = list(sizes["many"])
    threads = [
        threading.Thread(target=lambda part=names[start::4]: [many.saves_done([name]) for name in part])
        for start in range(4)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert seen == sorted(seen)
    assert seen[-1] == pytest.approx(400 * SURVEY)


def test_the_status_carries_what_a_reader_shows() -> None:
    clock = Clock()
    progress = ExtractionProgress(SIZES, clock=clock)
    progress.campaign("first").phase("survey")
    progress.campaign("first").saves_done(["a.json", "b.json"])
    progress.campaign("second").phase("sequence")
    progress.campaign("second").saves_done(["c.json"])
    clock.now = 4.0

    status = progress.snapshot().to_status()

    assert set(status) == {"percent", "elapsed_seconds", "remaining_seconds", "text", "summary", "campaigns"}
    assert 0 < status["percent"] < 100
    assert status["elapsed_seconds"] == 4
    assert isinstance(status["remaining_seconds"], int)
    assert status["campaigns"] == [
        {"name": "first", "phase": "survey", "done": 2, "total": 2, "step": "survey 2/2"},
        {"name": "second", "phase": "sequence", "done": 1, "total": 1, "step": "sequence 1/1"},
    ]
    assert status["text"] == f"first: survey 2/2, second: sequence 1/1 · {status['summary']}"
    assert status["summary"].endswith(" left") and "first" not in status["summary"]


def test_the_summary_and_the_percent_agree_where_floating_point_falls_short() -> None:
    snapshot = ProgressSnapshot((), done_work=58, total_work=100, elapsed=42)

    assert snapshot.to_status()["percent"] == 58.0
    assert snapshot.summary() == "58% · about 30 s left"


def test_no_work_counts_as_done() -> None:
    assert ExtractionProgress({}).snapshot().fraction == 1.0
