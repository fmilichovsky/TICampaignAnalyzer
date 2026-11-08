"""Significance on two saves of each committed benchmark campaign: the councilor presence rule.

Calls the stages directly: no command reports whether a councilor sat in the recruit pool.
"""

from pathlib import Path

import pytest

from tests.samples import save_paths
from tinarrative.analyzers import ALL_ANALYZERS, run_analyzers
from tinarrative.analyzers.common import Lookup, Side
from tinarrative.diff.state_diff import diff_states
from tinarrative.io.save_loader import load_raw_save
from tinarrative.model.events import Significance
from tinarrative.narrative import assign_significance
from tinarrative.parsing.normalization import normalize

pytestmark = pytest.mark.samples

COUNCILOR_PRESENCE = {"councilor.appeared": Side.AFTER, "councilor.disappeared": Side.BEFORE}


def test_recruit_pool_councilors_and_only_they_rank_as_trivial(sample_campaign: Path) -> None:
    snapshots = [normalize(load_raw_save(path)) for path in save_paths(sample_campaign)[:2]]
    before, after = sorted(snapshots, key=lambda snapshot: snapshot.timestamp)
    raw = run_analyzers(ALL_ANALYZERS, before, after, diff_states(before, after))
    assigned = assign_significance(raw, before, after)
    lookup = Lookup(before, after)
    presence = [event for event in assigned if event.event_type in COUNCILOR_PRESENCE]
    assert presence
    for event in presence:
        state = lookup.state(event.entities[0].entity_id, COUNCILOR_PRESENCE[event.event_type])
        assert state is not None, event.id
        recruit_pool = state.get("faction") is None
        assert (event.significance is Significance.TRIVIAL) == recruit_pool, event.id
