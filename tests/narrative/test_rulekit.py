"""Rule helpers: the date index equals the ``overlaps`` filter."""

from __future__ import annotations

import pytest

from tests.narrative.support import atomic
from tinarrative.model.events import DateBasis
from tinarrative.model.values import Unknown
from tinarrative.narrative.rulekit import DatedEvents, overlaps

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
