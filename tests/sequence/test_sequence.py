"""Ordering, merging and per-interval processing of a save sequence over synthetic fixtures."""

from __future__ import annotations

import gc
import shutil
import weakref
from datetime import datetime
from pathlib import Path

import pytest

from tests.fixtures import fixture_path
from tinarrative.io.save_loader import load_raw_save
from tinarrative.model.changes import StateDiff
from tinarrative.model.events import Event, EventStatus
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.narrative.situation import build_situation
from tinarrative.parsing.normalization import normalize
from tinarrative.sequence import (
    SaveRef,
    UnknownChronologyError,
    analyze_interval,
    event_stream,
    load_snapshot,
    plan_sequence,
    run_sequence,
    situations,
    survey,
)

FIXTURE_SET = "terra_invicta_json_v1"
SEQUENCE = ("politics_before.json", "politics_after.json", "politics_reverted.json")
DATES = ("2032-01-01T00:00:00", "2032-04-01T00:00:00", "2032-07-01T00:00:00")


def fixture(name: str) -> Path:
    return fixture_path("io", FIXTURE_SET, name)


def surveyed(*paths: Path) -> list[SaveRef]:
    return [survey(path) for path in paths]


@pytest.mark.fixture
def test_saves_are_ordered_by_game_time_whatever_the_argument_order() -> None:
    plan = plan_sequence(surveyed(*(fixture(name) for name in reversed(SEQUENCE))))

    assert [Path(save.source).name for save in plan.saves] == list(SEQUENCE)
    assert plan.keys == DATES
    assert (plan.inputs, plan.duplicates) == (3, 0)


@pytest.mark.fixture
def test_byte_identical_saves_are_one_snapshot_with_every_path_kept(tmp_path: Path) -> None:
    copy = tmp_path / "Exitsave.json"
    shutil.copyfile(fixture(SEQUENCE[1]), copy)

    plan = plan_sequence(surveyed(fixture(SEQUENCE[1]), fixture(SEQUENCE[0]), copy))

    assert (plan.inputs, plan.duplicates, len(plan.saves)) == (3, 1, 2)
    merged = plan.saves[1]
    assert sorted((merged.source, *merged.aliases)) == sorted((str(copy), str(fixture(SEQUENCE[1]))))
    assert merged.source == min(str(copy), str(fixture(SEQUENCE[1])))


@pytest.mark.fixture
def test_equal_game_times_with_different_bytes_are_both_kept_in_path_order(tmp_path: Path) -> None:
    variant = tmp_path / "a_autosave.json"
    variant.write_bytes(fixture(SEQUENCE[1]).read_bytes() + b"\n")

    plan = plan_sequence(surveyed(fixture(SEQUENCE[1]), variant, fixture(SEQUENCE[0])))

    assert [save.timestamp for save in plan.saves] == [
        datetime(2032, 1, 1),
        datetime(2032, 4, 1),
        datetime(2032, 4, 1),
    ]
    assert plan.saves[1].source < plan.saves[2].source
    assert plan.keys == (DATES[0], DATES[1], f"{DATES[1]}#2")


@pytest.mark.fixture
def test_a_save_without_game_time_has_unknown_chronology() -> None:
    with pytest.raises(UnknownChronologyError):
        survey(fixture("representative_campaign.json"))


@pytest.mark.fixture
def test_every_interval_runs_the_diff_pipeline_and_qualifies_its_ids() -> None:
    plan = plan_sequence(surveyed(*(fixture(name) for name in SEQUENCE)))

    intervals = list(run_sequence(plan, inferred=True))

    assert [(interval.before.date, interval.after.date, interval.key) for interval in intervals] == [
        (DATES[0], DATES[1], DATES[1]),
        (DATES[1], DATES[2], DATES[2]),
    ]
    first_pair = [normalize(load_raw_save(fixture(name))) for name in SEQUENCE[:2]]
    direct = analyze_interval(*first_pair, inferred=True)
    assert intervals[0].changes == len(direct.diff.changes)
    assert [event.id for event in intervals[0].objective] == [f"{event.id}@{DATES[1]}" for event in direct.objective]
    assert direct.inferred is not None and intervals[0].inferred is not None
    assert len(intervals[0].inferred) == len(direct.inferred)
    assert all(interval.state_changes is None for interval in intervals)
    reports = situations(intervals)
    assert reports == tuple(build_situation(normalize(load_raw_save(fixture(name)))) for name in SEQUENCE)
    assert intervals[0].after_situation is intervals[1].before_situation
    assert "situation" not in intervals[0].to_dict()


@pytest.mark.fixture
def test_at_most_two_snapshots_are_held_while_reports_are_kept() -> None:
    plan = plan_sequence(surveyed(*(fixture(name) for name in SEQUENCE)))
    loaded: list[weakref.ref[SaveSnapshot]] = []
    held: list[int] = []

    def load(source: str) -> SaveSnapshot:
        gc.collect()
        held.append(sum(snapshot() is not None for snapshot in loaded))
        result = load_snapshot(source)
        loaded.append(weakref.ref(result))
        return result

    intervals = list(run_sequence(plan, inferred=True, load=load))

    assert held == [0, 1, 1]  # with the one being loaded, never more than two
    gc.collect()
    assert all(snapshot() is None for snapshot in loaded)
    assert len(situations(intervals)) == len(SEQUENCE)


@pytest.mark.fixture
def test_only_the_first_interval_runs_the_first_interval_analyzers(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []

    class Recording:
        def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
            seen.append(before.date)
            return []

    monkeypatch.setattr("tinarrative.sequence.FIRST_INTERVAL_ANALYZERS", (Recording(),))
    plan = plan_sequence(surveyed(*(fixture(name) for name in SEQUENCE)))

    list(run_sequence(plan, inferred=False))

    assert seen == [DATES[0]]


@pytest.mark.fixture
def test_literal_changes_are_kept_only_when_asked() -> None:
    plan = plan_sequence(surveyed(*(fixture(name) for name in SEQUENCE)))

    intervals = list(run_sequence(plan, inferred=False, changes=True))

    first_pair = [normalize(load_raw_save(fixture(name))) for name in SEQUENCE[:2]]
    direct = analyze_interval(*first_pair, inferred=False)
    assert intervals[0].state_changes == direct.diff.changes
    assert [len(interval.state_changes or ()) for interval in intervals] == [interval.changes for interval in intervals]


@pytest.mark.fixture
def test_a_subject_that_changes_in_two_intervals_is_two_events_in_the_stream() -> None:
    plan = plan_sequence(surveyed(*(fixture(name) for name in SEQUENCE)))
    intervals = list(run_sequence(plan, inferred=True))

    stream = event_stream(intervals)

    region = [event for event in stream if event.id.startswith("region.nation_changed/region:42@")]
    assert [event.date for event in region] == [DATES[1], DATES[2]]
    forth, back = region
    assert (back.attribute("before"), back.attribute("after")) == (forth.attribute("after"), forth.attribute("before"))
    assert len({event.id for event in stream}) == len(stream)
    for interval in intervals:
        own = {event.id for event in interval.objective}
        for inferred in interval.inferred or ():
            assert inferred.status is EventStatus.INFERRED
            assert inferred.constituents and set(inferred.constituents) <= own


def test_fewer_than_two_distinct_saves_produce_no_interval() -> None:
    save = SaveRef("only.json", "0" * 64, datetime(2032, 1, 1))

    plan = plan_sequence([save, SaveRef("copy.json", "0" * 64, datetime(2032, 1, 1))])

    assert (len(plan.saves), plan.duplicates) == (1, 1)
    assert list(run_sequence(plan, inferred=False)) == []
    assert situations([]) == ()
