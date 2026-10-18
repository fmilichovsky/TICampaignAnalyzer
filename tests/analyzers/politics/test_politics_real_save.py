"""Opt-in check that every analyzer family is deterministic, evidenced and cause-free on a real interval."""

import json
import os
from pathlib import Path

import pytest

from tinarrative.analyzers import ALL_ANALYZERS, run_analyzers
from tinarrative.analyzers.common import Lookup, Side
from tinarrative.analyzers.render import describe_event
from tinarrative.diff.state_diff import diff_states
from tinarrative.io.save_loader import load_raw_save
from tinarrative.model.events import SIGNIFICANCE_ORDER, EventStatus, Significance, SourceRole
from tinarrative.narrative import assign_significance
from tinarrative.parsing.normalization import normalize

pytestmark = pytest.mark.real_save

FORBIDDEN = (
    "purg",
    "coup",
    "annex",
    "defect",
    "kill",
    "recruit",
    "join",
    "conquer",
    "captur",
    "seiz",
    "battle",
    "merge",
)
FIELD_BACKED = {"destroy": ("destroyed", "HabDestructionLog", "publicOpinion"), "refit": ("lastRefitDate",)}
"""Words allowed only when the event's primary source is the save field that literally carries them (the
``Destroy`` ideology is a ``publicOpinion`` key)."""
NOTIFICATION_LOG = "notificationSummaryQueue"
COUNCILOR_PRESENCE = {"councilor.appeared": Side.AFTER, "councilor.disappeared": Side.BEFORE}


def real_save_pair() -> tuple[Path, Path]:
    before = os.environ.get("TINARRATIVE_REAL_SAVE")
    after = os.environ.get("TINARRATIVE_REAL_SAVE_AFTER")
    if not before or not after:
        pytest.skip("TINARRATIVE_REAL_SAVE and TINARRATIVE_REAL_SAVE_AFTER are not both set")
    return Path(before), Path(after)


def test_real_save_pair_analyzes_deterministically_with_evidence_on_every_event() -> None:
    before_path, after_path = real_save_pair()
    before = normalize(load_raw_save(before_path))
    after = normalize(load_raw_save(after_path))
    diff = diff_states(before, after)
    first = run_analyzers(ALL_ANALYZERS, before, after, diff)
    second = run_analyzers(ALL_ANALYZERS, before, after, diff)
    assert first == second
    assert json.dumps([e.to_dict() for e in first]) == json.dumps([e.to_dict() for e in second])
    changes = set(diff.changes)
    for event in first:
        assert event.status is EventStatus.OBJECTIVE
        assert event.sources and any(source.role is SourceRole.PRIMARY for source in event.sources)
        assert all(source.change in changes for source in event.sources)
        assert event.entities and event.not_before == before.date
        if event.sources[0].change.field == NOTIFICATION_LOG:
            continue  # the game's own event log says what happened: its wording is evidence, not inference
        text = f"{event.event_type} {describe_event(event)}".lower()
        assert not any(word in text for word in FORBIDDEN), event.id
        for word, fields in FIELD_BACKED.items():
            if word in text:
                assert event.sources[0].change.field in fields, (event.id, word)


def test_real_save_pair_ranks_recruit_pool_councilors_as_trivial() -> None:
    before_path, after_path = real_save_pair()
    before = normalize(load_raw_save(before_path))
    after = normalize(load_raw_save(after_path))
    diff = diff_states(before, after)
    raw = run_analyzers(ALL_ANALYZERS, before, after, diff)
    assigned = assign_significance(raw, before, after)
    assert assigned == assign_significance(raw, before, after)
    assert [event.id for event in assigned] == [event.id for event in raw]
    assert all(event.significance in SIGNIFICANCE_ORDER for event in assigned)
    lookup = Lookup(before, after)
    presence = [event for event in assigned if event.event_type in COUNCILOR_PRESENCE]
    for event in presence:
        state = lookup.state(event.entities[0].entity_id, COUNCILOR_PRESENCE[event.event_type])
        assert state is not None, event.id
        recruit_pool = state.get("faction") is None
        assert (event.significance is Significance.TRIVIAL) == recruit_pool, event.id
