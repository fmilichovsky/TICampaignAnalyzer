"""Opt-in invariants of a real save sequence (never committed): unique IDs, constituents and record dates in their
interval."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tinarrative.model.events import DateBasis
from tinarrative.sequence import event_stream, plan_sequence, run_sequence, survey

pytestmark = pytest.mark.real_save

ENV_VAR = "TINARRATIVE_REAL_SAVE_SEQUENCE"


def real_save_sequence() -> list[Path]:
    value = os.environ.get(ENV_VAR, "")
    paths = [Path(part) for part in value.split(os.pathsep) if part]
    if len(paths) < 2:
        pytest.skip(f"{ENV_VAR} does not list at least two saves (separated by {os.pathsep!r})")
    return paths


def test_real_save_sequence_has_unique_ids_and_events_inside_their_interval() -> None:
    plan = plan_sequence(survey(path) for path in real_save_sequence())
    intervals = list(run_sequence(plan, inferred=True))

    stream = event_stream(intervals)  # raises on a duplicate ID

    assert len(intervals) == len(plan.saves) - 1
    assert stream
    for interval in intervals:
        own = {event.id for event in interval.objective}
        for event in interval.events():
            assert event.id.endswith("@" + interval.key)
            assert set(event.constituents) <= own
            if event.date_basis is DateBasis.RECORD:
                assert interval.before.date[:10] <= str(event.date)[:10] <= interval.after.date[:10]
