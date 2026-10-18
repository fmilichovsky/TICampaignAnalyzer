"""Opt-in invariants of a real save sequence (never committed): unique IDs, constituents and record dates in their
interval."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tinarrative.grouping import group_saves
from tinarrative.model.events import DateBasis
from tinarrative.parsing.errors import SaveLoadError
from tinarrative.sequence import event_stream, plan_sequence, run_sequence, survey

pytestmark = pytest.mark.real_save

ENV_VAR = "TINARRATIVE_REAL_SAVE_SEQUENCE"
CAMPAIGNS_ENV_VAR = "TINARRATIVE_REAL_SAVE_DIRECTORY"
"""A directory of real saves, possibly of several campaigns."""


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


def test_real_save_directory_splits_into_campaigns_with_distinct_keys() -> None:
    value = os.environ.get(CAMPAIGNS_ENV_VAR, "")
    if not value:
        pytest.skip(f"{CAMPAIGNS_ENV_VAR} does not name a directory of saves")
    saves = []
    for path in sorted(Path(value).iterdir()):
        try:
            saves.append(survey(path))
        except (OSError, SaveLoadError):
            continue
    groups = group_saves(saves)

    assert groups
    assert len({group.key for group in groups}) == len(groups)
    assert sum(len(group.members) for group in groups) == len(saves)
    for group in groups:
        assert not group.unclassified
        assert group.started is not None
