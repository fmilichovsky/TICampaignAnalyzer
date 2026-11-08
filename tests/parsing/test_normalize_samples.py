"""Normalization of the committed benchmark campaigns resolves the references a save makes to itself.

Calls ``normalize`` directly: no command reports whether a reference resolved.
"""

from pathlib import Path

import pytest

from tests.samples import save_paths
from tinarrative.io.save_loader import load_raw_save
from tinarrative.model.entities import EntityRef, IdentityConfidence
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.model.values import FrozenMap, Unknown, UnknownReason
from tinarrative.parsing.normalization import normalize

pytestmark = pytest.mark.samples

ALWAYS_RESOLVED = {
    "councilors": ("faction", "orgs", "location", "homeRegion"),
    "armies": ("currentRegion", "homeRegion", "priorRegion", "faction"),
    "fleets": ("ships", "faction", "orbitState", "barycenter"),
    "ships": ("fleet",),
    "habs": ("faction", "dockedFleets", "sectors", "councilorsOnBoard", "orbitState", "habSite"),
}
"""Reference fields that always name an entity of the same save."""


@pytest.fixture(scope="session")
def snapshots(sample_campaign: Path) -> list[SaveSnapshot]:
    """The first and the last save of the campaign by name, normalized."""
    paths = save_paths(sample_campaign)
    return [normalize(load_raw_save(path)) for path in (paths[0], paths[-1])]


def unresolved(value: object) -> bool:
    return isinstance(value, Unknown) and value.reason is UnknownReason.UNRESOLVED_REFERENCE


def test_samples_normalize_with_resolved_control_point_ownership(snapshots: list[SaveSnapshot]) -> None:
    for snapshot in snapshots:
        assert snapshot.timestamp is not None
        assert isinstance(snapshot.date, str)
        assert isinstance(snapshot.campaign_day, int)
        assert snapshot.factions and snapshot.nations and snapshot.regions and snapshot.control_points
        for state in snapshot.control_points:
            assert not isinstance(state.get("nation"), Unknown), state.ref
            assert isinstance(state.get("faction"), EntityRef | None), state.ref
        for state in snapshot.nations + snapshot.regions:
            for name, value in state.fields:
                assert not unresolved(value), (state.ref, name)


def test_samples_normalize_personnel_military_space_and_research(snapshots: list[SaveSnapshot]) -> None:
    for snapshot in snapshots:
        assert snapshot.councilors and snapshot.armies and snapshot.fleets and snapshot.ships and snapshot.habs
        for attribute, names in ALWAYS_RESOLVED.items():
            for state in getattr(snapshot, attribute):
                for name in names:
                    assert not unresolved(state.get(name)), (state.ref, name)
        # A fleet whose parent was merged away keeps the stale ID visible rather than dropping it.
        for state in snapshot.fleets:
            assert isinstance(state.get("parentFleet"), EntityRef | Unknown | None), state.ref
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
