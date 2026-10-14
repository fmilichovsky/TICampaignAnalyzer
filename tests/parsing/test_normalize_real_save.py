"""Opt-in check that a real save normalizes with resolved in-save references (never committed)."""

import os
from pathlib import Path

import pytest

from tinarrative.io.save_loader import load_raw_save
from tinarrative.model.entities import EntityRef, IdentityConfidence
from tinarrative.model.values import FrozenMap, Unknown, UnknownReason
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


def test_real_save_normalizes_personnel_military_space_and_research() -> None:
    snapshot = normalize(load_raw_save(real_save_path()))
    assert snapshot.councilors and snapshot.armies and snapshot.fleets and snapshot.ships and snapshot.habs
    always_resolved = {
        "councilors": ("faction", "orgs", "location", "homeRegion"),
        "armies": ("currentRegion", "homeRegion", "priorRegion", "faction"),
        "fleets": ("ships", "faction", "orbitState", "barycenter"),
        "ships": ("fleet",),
        "habs": ("faction", "dockedFleets", "sectors", "councilorsOnBoard", "orbitState", "habSite"),
    }
    for attribute, names in always_resolved.items():
        for state in getattr(snapshot, attribute):
            for name in names:
                value = state.get(name)
                if isinstance(value, Unknown):
                    assert value.reason is not UnknownReason.UNRESOLVED_REFERENCE, (state.ref, name)
    # A fleet whose parent was merged away keeps the stale ID visible rather than dropping it.
    for state in snapshot.fleets:
        parent = state.get("parentFleet")
        assert parent is None or isinstance(parent, EntityRef | Unknown)
    finished = snapshot.research.finished_techs_names
    progress = snapshot.research.tech_progress
    assert isinstance(finished, tuple) and isinstance(progress, tuple)
    names = {item for item in finished if isinstance(item, str)}
    for item in progress:
        if isinstance(item, FrozenMap):
            name = dict(item.items).get("techTemplateName")
            if isinstance(name, str):
                names.add(name)
    assert len(snapshot.technologies) == len(names)
    assert all(state.ref.confidence is IdentityConfidence.NAME_KEY for state in snapshot.technologies)
