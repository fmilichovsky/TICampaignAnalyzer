"""Opt-in check that a real save normalizes with resolved political references (never committed)."""

import os
from pathlib import Path

import pytest

from tinarrative.io.save_loader import load_raw_save
from tinarrative.model.entities import EntityRef
from tinarrative.model.values import Unknown, UnknownReason
from tinarrative.parsing.normalization import normalize

pytestmark = pytest.mark.real_save


def real_save_path() -> Path:
    location = os.environ.get("TINARRATIVE_REAL_SAVE")
    if not location:
        pytest.skip("TINARRATIVE_REAL_SAVE is not set")
    return Path(location)


def test_real_save_normalizes_with_resolved_control_point_ownership() -> None:
    snapshot = normalize(load_raw_save(real_save_path()))
    assert snapshot.timestamp is not None
    assert isinstance(snapshot.date, str)
    assert isinstance(snapshot.campaign_day, int)
    assert snapshot.factions and snapshot.nations and snapshot.regions and snapshot.control_points
    unresolved = [
        state.ref
        for state in snapshot.control_points
        if isinstance(state.get("nation"), Unknown) or isinstance(state.get("faction"), Unknown)
    ]
    assert unresolved == []
    assert all(isinstance(state.get("faction"), EntityRef | None) for state in snapshot.control_points)
    for state in snapshot.nations + snapshot.regions:
        for name, value in state.fields:
            if isinstance(value, Unknown):
                assert value.reason is not UnknownReason.UNRESOLVED_REFERENCE, (state.ref, name)
