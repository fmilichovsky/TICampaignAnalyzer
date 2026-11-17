"""Rule helpers: the date index equals the ``overlaps`` filter; runs starting in one interval are numbered."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest

from tests.narrative.support import atomic
from tinarrative.model.events import DateBasis, Event
from tinarrative.model.values import Unknown
from tinarrative.narrative.rulekit import DatedEvents, Run, anchored, chained, overlaps

K1 = "2032-04-01T00:00:00"
K2 = "2032-07-01T00:00:00"
EVENTS = (
    atomic("ledger.charge/3", K2, date="2032-05-20T00:00:00", date_basis=DateBasis.RECORD),
    atomic("ledger.charge/1", K1, date="2032-03-10T00:00:00", date_basis=DateBasis.RECORD),
    atomic("ledger.charge/2", K1, not_before="2032-01-01T00:00:00"),
    atomic("ledger.charge/4", K2, date="2032-05-20T00:00:00", date_basis=DateBasis.RECORD),
    atomic("ledger.charge/5", K2, date=Unknown(), date_basis=DateBasis.RECORD),
    atomic("ledger.charge/6", K2, date="garbled", date_basis=DateBasis.RECORD),
)


@pytest.mark.parametrize(
    ("low", "high"),
    [
        ("2032-03-10T00:00:00", "2032-05-20T00:00:00"),
        ("2032-03-11T00:00:00", "2032-05-19T00:00:00"),
        ("2031-01-01T00:00:00", "2033-01-01T00:00:00"),
        ("2032-06-01T00:00:00", "2032-06-02T00:00:00"),
        (None, "2033-01-01T00:00:00"),
        ("2031-01-01T00:00:00", "garbled"),
    ],
)
def test_overlapping_equals_the_overlaps_filter_in_input_order(low: str | None, high: str | None) -> None:
    expected = [event.id for event in EVENTS if overlaps(event, low, high)]
    assert [event.id for event in DatedEvents(EVENTS).overlapping(low, high)] == expected


def _on(raw_id: str, key: str, date: str | Unknown) -> Event:
    return atomic(raw_id, key, date=date, date_basis=DateBasis.RECORD)


LONG = "2033-01-01T00:00:00"
LONG_RUNS = (
    _on("habs/1", LONG, "2032-01-10T00:00:00"),
    _on("habs/2", LONG, "2032-01-20T00:00:00"),
    _on("habs/3", LONG, "2032-11-10T00:00:00"),
    _on("habs/4", LONG, "2032-11-20T00:00:00"),
    _on("habs/5", K2, "2032-06-20T00:00:00"),
)


@pytest.mark.parametrize("runs_of", [anchored, chained])
def test_a_later_run_starting_in_the_same_interval_is_numbered_and_the_first_is_not(
    runs_of: Callable[[Sequence[Event], int], Sequence[Run]],
) -> None:
    runs = runs_of(LONG_RUNS, 30)

    assert [[event.id.split("@")[0] for event in run] for run in runs] == [
        ["habs/1", "habs/2"],
        ["habs/5"],
        ["habs/3", "habs/4"],
    ]
    assert [run.discriminator for run in runs] == [(), (), ("run2",)]


@pytest.mark.parametrize("runs_of", [anchored, chained])
def test_undated_members_each_start_a_run_and_are_numbered_apart(
    runs_of: Callable[[Sequence[Event], int], Sequence[Run]],
) -> None:
    runs = runs_of([_on("habs/1", K1, Unknown()), _on("habs/2", K1, Unknown())], 30)

    assert [run.discriminator for run in runs] == [(), ("run2",)]


def test_a_run_reads_as_the_sequence_of_its_members() -> None:
    [run] = anchored(LONG_RUNS[:2], 30)

    assert (len(run), run[0], run[-1], [*run]) == (2, LONG_RUNS[0], LONG_RUNS[1], list(LONG_RUNS[:2]))
