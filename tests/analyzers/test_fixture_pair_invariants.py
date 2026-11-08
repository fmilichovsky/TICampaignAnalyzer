"""Invariants every analyzer family keeps over each checked-in fixture pair: evidence, determinism, coverage."""

import json

import pytest

from tests.analyzers.support import fixture_pair
from tinarrative.analyzers import (
    ALIEN_ANALYZERS,
    ALL_ANALYZERS,
    CAMPAIGN_ANALYZERS,
    FACTION_ANALYZERS,
    MILITARY_ANALYZERS,
    POLITICS_ANALYZERS,
    SPACE_ANALYZERS,
    TECHNOLOGY_ANALYZERS,
    run_analyzers,
)
from tinarrative.analyzers.base import Analyzer
from tinarrative.analyzers.military.armies import HANDLED_LISTS as ARMY_LISTS
from tinarrative.analyzers.politics.control_points import HANDLED_LISTS as POINT_LISTS
from tinarrative.analyzers.politics.councilors import HANDLED_LISTS as COUNCILOR_LISTS
from tinarrative.analyzers.politics.federations import HANDLED_LISTS as FEDERATION_LISTS
from tinarrative.analyzers.politics.nations import HANDLED_LISTS as NATION_LISTS
from tinarrative.analyzers.politics.wars import HANDLED_LISTS as WAR_LISTS
from tinarrative.analyzers.space.fleets import HANDLED_LISTS as FLEET_LISTS
from tinarrative.analyzers.space.ships import HANDLED_LISTS as SHIP_LISTS
from tinarrative.model.changes import ChangeKind, MembershipDetail
from tinarrative.model.entities import EntityRef
from tinarrative.model.events import Confidence, DateBasis, EventStatus, SourceRole
from tinarrative.model.values import Unknown, UnknownReason

ASSET_ANALYZERS = MILITARY_ANALYZERS + SPACE_ANALYZERS + TECHNOLOGY_ANALYZERS
FAMILIES: dict[str, tuple[Analyzer, ...]] = {
    "politics": POLITICS_ANALYZERS,
    "assets": ASSET_ANALYZERS,
    "ledger": FACTION_ANALYZERS,
    "campaign": CAMPAIGN_ANALYZERS,
    "aliens": ALIEN_ANALYZERS,
}
FAMILY_PAIRS = [
    ("politics", "interval"),
    ("politics", "records"),
    ("politics", "politics"),
    ("politics", "wars"),
    ("assets", "interval"),
    ("assets", "assets"),
    ("ledger", "ledger"),
    ("campaign", "global_values"),
    ("campaign", "notifications"),
    ("assets", "combat"),
    ("aliens", "aliens"),
]
"""A new family gets the invariants by adding its rows here."""
HANDLED = {
    "politics": POINT_LISTS + NATION_LISTS + WAR_LISTS + FEDERATION_LISTS + COUNCILOR_LISTS,
    "assets": ARMY_LISTS + FLEET_LISTS + SHIP_LISTS,
}
ALL_PAIRS = sorted({name for _, name in FAMILY_PAIRS} | {"notifications", "combat"})


def files(name: str) -> tuple[str, str]:
    return f"{name}_before.json", f"{name}_after.json"


@pytest.mark.parametrize(("family", "name"), FAMILY_PAIRS)
def test_every_event_is_evidenced_objective_and_deterministic(family: str, name: str) -> None:
    analyzers = FAMILIES[family]
    before, after, diff = fixture_pair(*files(name))
    events = run_analyzers(analyzers, before, after, diff)
    ids = [event.id for event in events]
    assert events and len(ids) == len(set(ids))
    again = run_analyzers(analyzers, before, after, diff)
    assert events == again
    assert json.dumps([event.to_dict() for event in events]) == json.dumps([event.to_dict() for event in again])
    changes = set(diff.changes)
    for event in events:
        assert event.status is EventStatus.OBJECTIVE
        assert event.sources and any(source.role is SourceRole.PRIMARY for source in event.sources)
        assert all(source.change in changes for source in event.sources)
        assert event.entities
        assert event.not_before == before.date
        unresolved = [
            value
            for _, value in event.attributes
            if isinstance(value, Unknown) and value.reason is UnknownReason.UNRESOLVED_REFERENCE
        ]
        assert event.confidence is (Confidence.LOW if unresolved else Confidence.HIGH)
        if event.date_basis is DateBasis.INTERVAL:
            assert event.date == after.date


@pytest.mark.parametrize(("family", "name"), [(family, name) for family, name in FAMILY_PAIRS if family in HANDLED])
def test_every_member_of_a_handled_list_is_cited(family: str, name: str) -> None:
    handled = {(domain.value, field) for domain, field in HANDLED[family]}
    before, after, diff = fixture_pair(*files(name))
    cited = {
        (source.change, source.member.entity_id)
        for event in run_analyzers(FAMILIES[family], before, after, diff)
        for source in event.sources
        if isinstance(source.member, EntityRef)
    }
    for change in diff.changes:
        if (change.domain, change.field) not in handled or change.kind is not ChangeKind.MEMBERSHIP:
            continue
        assert isinstance(change.detail, MembershipDetail)
        for member in change.detail.added + change.detail.removed:
            assert isinstance(member, EntityRef) and (change, member.entity_id) in cited, (change.entity_id, member)


@pytest.mark.parametrize("name", ALL_PAIRS)
def test_all_families_together_never_collide(name: str) -> None:
    before, after, diff = fixture_pair(*files(name))
    events = run_analyzers(ALL_ANALYZERS, before, after, diff)
    ids = [event.id for event in events]
    assert len(ids) == len(set(ids))
    assert events == tuple(sorted(events, key=lambda event: event.sort_key))
