"""Acceptance over the checked-in fixture pairs: expected events, evidence invariants, determinism, wording."""

import json
from collections import Counter

import pytest

from tests.analyzers.support import fixture_pair
from tinarrative.analyzers import POLITICS_ANALYZERS, run_analyzers
from tinarrative.analyzers.politics.control_points import HANDLED_LISTS as POINT_LISTS
from tinarrative.analyzers.politics.councilors import HANDLED_LISTS as COUNCILOR_LISTS
from tinarrative.analyzers.politics.federations import HANDLED_LISTS as FEDERATION_LISTS
from tinarrative.analyzers.politics.nations import HANDLED_LISTS as NATION_LISTS
from tinarrative.analyzers.politics.wars import HANDLED_LISTS as WAR_LISTS
from tinarrative.analyzers.render import describe_event
from tinarrative.model.changes import ChangeKind, MembershipDetail, StateDiff
from tinarrative.model.entities import EntityRef
from tinarrative.model.events import Confidence, DateBasis, Event, EventStatus, SourceRole
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.model.values import Unknown, UnknownReason

PAIRS = [
    ("interval_before.json", "interval_after.json"),
    ("records_before.json", "records_after.json"),
    ("politics_before.json", "politics_after.json"),
    ("wars_before.json", "wars_after.json"),
]
FORBIDDEN = (
    "purg", "coup", "annex", "defect", "destroy", "kill", "recruit", "join", "conquer", "captur", "seiz",
    "assassin", "died", "death", "creat",
)  # fmt: skip
WAR_FORBIDDEN = ("declar", "won", "lost", "peace", "victor", "defeat", "surrender")
"""Reconstruction vocabulary for wars; ``lost`` is fine elsewhere (``lostControlPoints`` is literal)."""
HANDLED = {
    (domain.value, field)
    for domain, field in POINT_LISTS + NATION_LISTS + WAR_LISTS + FEDERATION_LISTS + COUNCILOR_LISTS
}


def run(before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> tuple[Event, ...]:
    return run_analyzers(POLITICS_ANALYZERS, before, after, diff)


def ids(events: tuple[Event, ...]) -> list[str]:
    return [event.id for event in events]


@pytest.mark.fixture
def test_interval_pair_yields_the_expected_events() -> None:
    before, after, diff = fixture_pair(*PAIRS[0])
    events = run(before, after, diff)
    assert ids(events) == [
        "control_point.controller_changed/control point:9",
        "control_point.disappeared/control point:12",
        "councilor.appeared/councilor:102",
        "councilor.disappeared/councilor:101",
        "councilor.location_changed/councilor:100",
        "faction.councilors_changed/faction:15/councilor:101/removed",
        "federation.members_changed/federation:80/nation:20/added",
        "nation.relation_changed/allies/nation:20/nation:21/removed",
        "nation.relation_changed/allies/nation:20/nation:22/added",
        "nation.renamed/nation:20",
        "nation.statistic_shifted/nation:20/GDP",
        "organization.assigned_councilor_changed/organization:70",
    ]
    by_id = {event.id: event for event in events}
    renamed = by_id["nation.renamed/nation:20"]
    assert [(s.role, s.change.field) for s in renamed.sources] == [(SourceRole.PRIMARY, "displayName")]
    assert (renamed.attribute("before"), renamed.attribute("after")) == ("Fixture Northland", "Fixture Northland Union")
    gone = by_id["control_point.disappeared/control point:12"]
    assert [source.role for source in gone.sources] == [SourceRole.PRIMARY] + [SourceRole.CORROBORATING] * 2
    assert by_id["councilor.appeared/councilor:102"].sources[1].change.field == "councilors"
    unresolved = by_id["councilor.location_changed/councilor:100"]
    assert unresolved.confidence is Confidence.LOW and unresolved.attribute("transition") == "unresolved"
    joined = by_id["federation.members_changed/federation:80/nation:20/added"]
    assert [(s.role, s.change.domain, s.change.field) for s in joined.sources] == [
        (SourceRole.PRIMARY, "federation", "members"),
        (SourceRole.CORROBORATING, "nation", "federation"),
    ]
    assert by_id["nation.relation_changed/allies/nation:20/nation:22/added"].attribute("reciprocal") is True
    assert by_id["nation.relation_changed/allies/nation:20/nation:21/removed"].attribute("reciprocal") is False
    assert all(event.date_basis is DateBasis.INTERVAL for event in events)


@pytest.mark.fixture
def test_records_pair_yields_record_dated_events() -> None:
    before, after, diff = fixture_pair(*PAIRS[1])
    events = run(before, after, diff)
    assert ids(events) == [
        "control_point.loss_recorded/faction:15/control point:9",
        "nation.executive_change_recorded/nation:20",
        "nation.new_government_recorded/nation:20",
    ]
    loss, executive, new_government = events
    assert (loss.date, loss.date_basis) == ("2031-04-10T00:00:00", DateBasis.RECORD)
    assert loss.sources[0].entry is not None and loss.sources[0].entry.path.endswith("/lostControlPoints/0")  # type: ignore[union-attr]
    assert (executive.date, executive.date_basis) == ("2031-04-20T00:00:00", DateBasis.RECORD)
    assert executive.attribute("cause") == "Coup"
    assert {source.member for source in executive.sources} == {"cause", "date", "newExecutive"}
    assert (new_government.date, new_government.date_basis) == (executive.date, DateBasis.RECORD)
    assert [(s.role, s.change.field) for s in new_government.sources] == [(SourceRole.PRIMARY, "dateOfNewGovernment")]
    assert (new_government.attribute("transition"), new_government.attribute("before")) == ("set", None)


@pytest.mark.fixture
def test_politics_pair_covers_every_transition_once() -> None:
    before, after, diff = fixture_pair(*PAIRS[2])
    events = run(before, after, diff)
    assert Counter(event.event_type for event in events) == {
        "control_point.controller_changed": 2,
        "control_point.nation_changed": 1,
        "control_point.loss_recorded": 1,
        "region.nation_changed": 1,
        "nation.capital_changed": 1,
        "nation.breakaway_parent_changed": 1,
        "nation.relation_changed": 2,
        "nation.control_points_changed": 1,
        "nation.executive_change_recorded": 1,
        "councilor.faction_changed": 2,
        "councilor.status_changed": 1,
        "councilor.detaining_faction_changed": 1,
        "councilor.location_changed": 1,
        "faction.councilors_changed": 1,
        "nation.claims_changed": 1,
        "nation.hostile_claims_changed": 1,
        "nation.unrest_attempts_changed": 2,
        "nation.rank_changed": 1,
    }
    by_id = {event.id: event for event in events}
    claims = by_id["nation.claims_changed/nation:21"]
    assert [str(value.entity_id) for value in claims.attribute("added")] == ["region:40"]  # type: ignore[union-attr]
    assert claims.attribute("removed") == ()
    assert [(s.role, s.change.field, str(s.member.entity_id)) for s in claims.sources] == [  # type: ignore[union-attr]
        (SourceRole.PRIMARY, "claims", "region:40")
    ]
    assert [str(ref.entity_id) for ref in claims.entities] == ["nation:21", "region:40", "nation:20"]
    hostile = by_id["nation.hostile_claims_changed/nation:22"]
    assert [str(ref.entity_id) for ref in hostile.entities] == ["nation:22", "region:42", "nation:20"]
    attempts = {
        event_id: (event.attribute("before"), event.attribute("after"))
        for event_id, event in by_id.items()
        if event.event_type == "nation.unrest_attempts_changed"
    }
    assert attempts == {
        "nation.unrest_attempts_changed/nation:20/faction:15": (None, 1),
        "nation.unrest_attempts_changed/nation:20/faction:16": (1, 2),
    }
    transfer = by_id["control_point.controller_changed/control point:9"]
    assert transfer.attribute("loss_recorded_on") == "2032-02-15T00:00:00"
    assert [(s.role, s.change.field) for s in transfer.sources] == [
        (SourceRole.PRIMARY, "faction"),
        (SourceRole.CORROBORATING, "controlPoints"),
        (SourceRole.CORROBORATING, "controlPoints"),
        (SourceRole.CORROBORATING, "lostControlPoints"),
    ]
    loss = by_id["control_point.loss_recorded/faction:16/control point:9"]  # the record is evidence of its own
    assert loss.sources[0].entry == transfer.sources[3].entry and loss.date_basis is DateBasis.RECORD
    stale = by_id["faction.councilors_changed/faction:15/unresolved"]
    assert stale.confidence is Confidence.LOW
    assert all(event.date_basis is DateBasis.INTERVAL for event in events if "recorded" not in event.event_type)
    # priorLocation changed in the fixture and must not have produced an event
    assert not any("priorLocation" in (source.change.field or "") for event in events for source in event.sources)


@pytest.mark.fixture
def test_wars_pair_yields_war_and_federation_events_corroborated_by_the_nations() -> None:
    before, after, diff = fixture_pair(*PAIRS[3])
    events = run(before, after, diff)
    assert sorted(ids(events)) == [
        "federation.members_changed/federation:80/nation:20/added",
        "federation.members_changed/federation:80/nation:25/removed",
        "federation.renamed/federation:80",
        "nation.relation_changed/wars/nation:21/nation:24/added",
        "war.alliance_changed/war:90/attacking/nation:22/added",
        "war.appeared/war:92",
        "war.disappeared/war:91",
        "war.last_fighting_changed/war:90",
    ]
    by_id = {event.id: event for event in events}

    def cited(event_id: str) -> list[tuple[SourceRole, str, str | None]]:
        return [(s.role, str(s.change.entity_id), s.change.field) for s in by_id[event_id].sources]

    appeared = by_id["war.appeared/war:92"]
    assert (appeared.date, appeared.date_basis) == ("2032-02-20T00:00:00", DateBasis.RECORD)
    assert appeared.attribute("started_on") == "2032-02-20T00:00:00"
    assert [str(ref.entity_id) for ref in appeared.entities] == ["war:92", "nation:23", "nation:25"]
    assert cited("war.appeared/war:92")[-2:] == [
        (SourceRole.CORROBORATING, "nation:23", "wars"),
        (SourceRole.CORROBORATING, "nation:25", "wars"),
    ]
    start = next(s for s in appeared.sources if s.member == "startDate")
    assert start.entry is not None and start.entry.path.endswith("/startDate")  # type: ignore[union-attr]
    renamed = by_id["federation.renamed/federation:80"]
    assert cited("federation.renamed/federation:80") == [
        (SourceRole.PRIMARY, "federation:80", "displayName"),
        (SourceRole.PRIMARY, "federation:80", "federationName"),
    ]
    assert (renamed.attribute("before"), renamed.attribute("after")) == (
        "Fixture Federation",
        "Fixture Grand Federation",
    )
    assert isinstance(renamed.attribute("federation_name_before"), Unknown)  # same values as the display names
    gone = by_id["war.disappeared/war:91"]
    assert gone.date_basis is DateBasis.INTERVAL
    assert cited("war.disappeared/war:91") == [
        (SourceRole.PRIMARY, "war:91", None),
        (SourceRole.CORROBORATING, "nation:22", "wars"),
        (SourceRole.CORROBORATING, "nation:23", "wars"),
    ]
    assert cited("war.alliance_changed/war:90/attacking/nation:22/added") == [
        (SourceRole.PRIMARY, "war:90", "_attackingAlliance"),
        (SourceRole.CORROBORATING, "nation:21", "wars"),
        (SourceRole.CORROBORATING, "nation:22", "wars"),
    ]
    fighting = by_id["war.last_fighting_changed/war:90"]
    assert (fighting.date, fighting.date_basis) == ("2032-03-15T00:00:00", DateBasis.RECORD)
    for member, transition in (("20", "added"), ("25", "removed")):
        assert cited(f"federation.members_changed/federation:80/nation:{member}/{transition}") == [
            (SourceRole.PRIMARY, "federation:80", "members"),
            (SourceRole.CORROBORATING, f"nation:{member}", "federation"),
        ]
    assert by_id["nation.relation_changed/wars/nation:21/nation:24/added"].attribute("reciprocal") is False


@pytest.mark.fixture
@pytest.mark.parametrize(("before_name", "after_name"), PAIRS)
def test_every_event_is_evidenced_objective_and_deterministic(before_name: str, after_name: str) -> None:
    before, after, diff = fixture_pair(before_name, after_name)
    events = run(before, after, diff)
    assert events and len(ids(events)) == len(set(ids(events)))
    assert events == run(before, after, diff)
    assert json.dumps([e.to_dict() for e in events]) == json.dumps([e.to_dict() for e in run(before, after, diff)])
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
        json.loads(json.dumps(event.to_dict()))


@pytest.mark.fixture
@pytest.mark.parametrize(("before_name", "after_name"), PAIRS)
def test_every_member_of_a_handled_list_is_cited(before_name: str, after_name: str) -> None:
    before, after, diff = fixture_pair(before_name, after_name)
    cited = {
        (source.change, source.member.entity_id)
        for event in run(before, after, diff)
        for source in event.sources
        if isinstance(source.member, EntityRef)
    }
    for change in diff.changes:
        if (change.domain, change.field) not in HANDLED or change.kind is not ChangeKind.MEMBERSHIP:
            continue
        assert isinstance(change.detail, MembershipDetail)
        for member in change.detail.added + change.detail.removed:
            assert isinstance(member, EntityRef) and (change, member.entity_id) in cited, (change.entity_id, member)


@pytest.mark.fixture
@pytest.mark.parametrize(("before_name", "after_name"), PAIRS)
def test_types_and_messages_never_name_a_cause(before_name: str, after_name: str) -> None:
    before, after, diff = fixture_pair(before_name, after_name)
    for event in run(before, after, diff):
        text = f"{event.event_type} {describe_event(event)}".lower()
        war_words = WAR_FORBIDDEN if event.event_type.startswith(("war.", "federation.")) else ()
        for word in FORBIDDEN + war_words:
            assert word not in text, (event.id, word)
