"""Transition classification, change lookup, the membership ledger and the analyzer runner."""

import json
import logging

import pytest

from tests.analyzers.support import (
    AFTER,
    AFTER_DATE,
    BEFORE,
    BEFORE_DATE,
    councilor_ref,
    faction_ref,
    fixture_kind,
    nation_ref,
    pair,
    point_ref,
    snapshot,
    state,
)
from tinarrative.analyzers import POLITICS_ANALYZERS, run_analyzers
from tinarrative.analyzers.common import (
    FACTION_KINDS,
    ChangeIndex,
    EventBuilder,
    Lookup,
    MembershipLedger,
    Side,
    Transition,
    classify,
    confidence_for,
    event_id,
    primary,
)
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, DateBasis, EventStatus, SourceRole
from tinarrative.model.values import Observed, Unknown, UnknownReason, freeze

XY = fixture_kind("x.y")
TEST_EVENT = fixture_kind("test.event")

UNRESOLVED = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 999}))


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (None, faction_ref("15"), Transition.SET),
        (faction_ref("15"), None, Transition.CLEARED),
        (faction_ref("15"), faction_ref("16"), Transition.CHANGED),
        ("Available", "Detained", Transition.CHANGED),
        (None, freeze({"value": 80}), Transition.SET),
        (faction_ref("15"), UNRESOLVED, Transition.UNRESOLVED),
        (UNRESOLVED, None, Transition.UNRESOLVED),
        (Unknown(), faction_ref("15"), None),
        (faction_ref("15"), Unknown(UnknownReason.UNPARSEABLE, ()), None),
    ],
)
def test_classify_names_the_literal_transition_or_skips_schema_gaps(
    before: Observed, after: Observed, expected: Transition | None
) -> None:
    assert classify(before, after) is expected


def test_confidence_is_low_only_for_unresolved_sides() -> None:
    assert confidence_for(Transition.CHANGED) is Confidence.HIGH
    assert confidence_for(Transition.CLEARED, None) is Confidence.HIGH
    assert confidence_for(Transition.UNRESOLVED) is Confidence.LOW
    assert confidence_for(Transition.CHANGED, UNRESOLVED) is Confidence.LOW


def test_event_id_is_the_type_and_its_parts() -> None:
    assert event_id("nation.relation_changed", nation_ref("20").entity_id, "allies", "added") == (
        "nation.relation_changed/nation:20/allies/added"
    )


def test_change_index_finds_changes_by_entity_field_domain_and_presence() -> None:
    before, after, diff = pair(
        snapshot(
            BEFORE,
            state(EntityDomain.CONTROL_POINT, "9", BEFORE, faction=None),
            state(EntityDomain.CONTROL_POINT, "12", BEFORE, faction=faction_ref("16")),
        ),
        snapshot(AFTER, state(EntityDomain.CONTROL_POINT, "9", AFTER, faction=faction_ref("15"))),
    )
    index = ChangeIndex(diff)
    change = index.field(point_ref("9").entity_id, "faction")
    assert change is not None and change.after == faction_ref("15")
    assert index.field(point_ref("9").entity_id, "nation") is None
    assert index.fields(EntityDomain.CONTROL_POINT, "faction") == (change,)
    assert index.fields(EntityDomain.NATION, "faction") == ()
    (gone,) = index.presence(EntityDomain.CONTROL_POINT)
    assert gone.entity_id == point_ref("12").entity_id and gone.field is None


def test_lookup_reads_context_from_the_after_snapshot_first() -> None:
    before = snapshot(
        BEFORE,
        state(EntityDomain.CONTROL_POINT, "9", BEFORE, nation=nation_ref("20")),
        state(EntityDomain.NATION, "20", BEFORE),
        state(EntityDomain.NATION, "21", BEFORE),
    )
    after = snapshot(AFTER, state(EntityDomain.CONTROL_POINT, "9", AFTER, nation=nation_ref("21")))
    lookup = Lookup(before, after)
    point = point_ref("9").entity_id
    assert lookup.ref(point) is not None and lookup.ref(point).name == "Fixture control point 9"  # type: ignore[union-attr]
    assert lookup.ref(nation_ref("22").entity_id) is None
    context = lookup.context_ref(point, "nation")
    assert context is not None and context.entity_id == nation_ref("21").entity_id
    assert context.name == "Fixture nation 21"  # the entity's own reference, not the bare field value
    assert lookup.ref_field(point, "nation", Side.BEFORE) == lookup.ref(nation_ref("20").entity_id)
    assert lookup.resolve(None) is None and lookup.resolve(UNRESOLVED) is None
    assert lookup.resolve(nation_ref("22")) == nation_ref("22")  # not normalized: the field value itself


def test_membership_ledger_claims_members_once_and_reports_the_rest() -> None:
    _, _, diff = pair(
        snapshot(BEFORE, state(EntityDomain.FACTION, "15", BEFORE, councilors=(councilor_ref("100"),))),
        snapshot(
            AFTER, state(EntityDomain.FACTION, "15", AFTER, councilors=(councilor_ref("101"), councilor_ref("102")))
        ),
    )
    ledger = MembershipLedger(ChangeIndex(diff), ((EntityDomain.FACTION, "councilors"),))
    faction = faction_ref("15").entity_id
    assert ledger.pending("councilors") == [
        (faction, councilor_ref("101"), Transition.ADDED),
        (faction, councilor_ref("102"), Transition.ADDED),
        (faction, councilor_ref("100"), Transition.REMOVED),
    ]
    cited = ledger.claim(
        faction, "councilors", councilor_ref("101").entity_id, Transition.ADDED, SourceRole.CORROBORATING
    )
    assert cited is not None and cited.member == councilor_ref("101") and cited.role is SourceRole.CORROBORATING
    assert (
        ledger.claim(faction, "councilors", councilor_ref("101").entity_id, Transition.ADDED, SourceRole.PRIMARY)
        is None
    )
    assert (
        ledger.claim(faction, "councilors", councilor_ref("100").entity_id, Transition.ADDED, SourceRole.PRIMARY)
        is None
    )
    assert (
        ledger.claim(faction, "controlPoints", councilor_ref("100").entity_id, Transition.REMOVED, SourceRole.PRIMARY)
        is None
    )
    leftovers = [(member, transition) for _, member, transition in ledger.leftovers()]
    assert leftovers == [(councilor_ref("102"), Transition.ADDED), (councilor_ref("100"), Transition.REMOVED)]


def test_membership_ledger_reports_a_list_unresolved_on_one_side_as_one_leftover() -> None:
    _, _, diff = pair(
        snapshot(
            BEFORE, state(EntityDomain.FACTION, "15", BEFORE, councilors=(councilor_ref("100"),), fleets=Unknown())
        ),
        snapshot(AFTER, state(EntityDomain.FACTION, "15", AFTER, councilors=UNRESOLVED, fleets=())),
    )
    ledger = MembershipLedger(
        ChangeIndex(diff), ((EntityDomain.FACTION, "councilors"), (EntityDomain.FACTION, "fleets"))
    )
    assert ledger.pending("councilors") == []
    ((change, member, transition),) = list(ledger.leftovers())
    assert (change.field, member, transition) == ("councilors", None, Transition.UNRESOLVED)  # fleets: missing side


def test_event_builder_dates_by_the_interval_unless_a_record_date_is_given() -> None:
    before, after, diff = pair(snapshot(BEFORE), snapshot(AFTER))
    build = EventBuilder(before, after)
    _, _, change_diff = pair(
        snapshot(BEFORE, state(EntityDomain.NATION, "20", BEFORE, GDP=1.0)),
        snapshot(AFTER, state(EntityDomain.NATION, "20", AFTER, GDP=2.0)),
    )
    (change,) = [c for c in change_diff.changes if c.field == "GDP"]
    event = build.event(XY, id_parts=("a", 1), sources=(primary(change),), entities=(nation_ref("20"), None))
    assert (event.id, event.status, event.confidence) == ("x.y/a/1", EventStatus.OBJECTIVE, Confidence.HIGH)
    assert (event.date, event.date_basis, event.not_before) == (AFTER_DATE, DateBasis.INTERVAL, BEFORE_DATE)
    assert event.entities == (nation_ref("20"),)
    dated = build.event(XY, id_parts=(), sources=(), entities=(), recorded_on="2031-04-10T00:00:00")
    assert (dated.date, dated.date_basis, dated.not_before) == ("2031-04-10T00:00:00", DateBasis.RECORD, BEFORE_DATE)
    undated = build.event(XY, id_parts=(), sources=(), entities=(), recorded_on=Unknown())
    assert undated.date_basis is DateBasis.INTERVAL
    no_dates = EventBuilder(snapshot(BEFORE, date=Unknown()), snapshot(AFTER, date=Unknown()))
    assert no_dates.event(XY, id_parts=(), sources=(), entities=()).date == Unknown()


def test_run_analyzers_sorts_events_logs_aggregates_only_and_rejects_duplicate_ids(
    caplog: pytest.LogCaptureFixture,
) -> None:
    before, after, diff = pair(
        snapshot(
            BEFORE,
            state(EntityDomain.CONTROL_POINT, "9", BEFORE, faction=None, nation=nation_ref("20")),
            state(EntityDomain.COUNCILOR, "100", BEFORE, status="Available"),
        ),
        snapshot(
            AFTER,
            state(EntityDomain.CONTROL_POINT, "9", AFTER, faction=faction_ref("15"), nation=nation_ref("20")),
            state(EntityDomain.COUNCILOR, "100", AFTER, status="Fixture Status"),
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="tinarrative.analyzers.common"):
        events = run_analyzers(POLITICS_ANALYZERS, before, after, diff)
    assert [event.event_type for event in events] == ["control_point.controller_changed", "councilor.status_changed"]
    assert events == run_analyzers(POLITICS_ANALYZERS, before, after, diff)
    assert json.dumps([event.to_dict() for event in events]) == json.dumps(
        [event.to_dict() for event in run_analyzers(POLITICS_ANALYZERS, before, after, diff)]
    )
    lines = [record.getMessage() for record in caplog.records]
    assert "analyzer done analyzer=ControlPointAnalyzer events=1 high=1 medium=0 low=0" in lines
    assert "analyzer done analyzer=NationAnalyzer events=0 high=0 medium=0 low=0" in lines
    assert all("Fixture" not in line and "Available" not in line for line in lines)

    class Twice:
        def analyze(self, b: object, a: object, d: object) -> list[object]:
            return list(events) + list(events)

    with pytest.raises(ValueError, match="duplicate event IDs"):
        run_analyzers([Twice()], before, after, diff)  # type: ignore[list-item]


def test_every_event_naming_a_faction_carries_its_kind_by_template() -> None:
    faction = EntityDomain.FACTION
    before = snapshot(BEFORE, state(faction, "16", BEFORE, templateName="AlienCouncil"))
    after = snapshot(
        AFTER,
        state(faction, "15", AFTER, templateName="ResistCouncil"),
        state(faction, "17", AFTER),
        state(EntityDomain.NATION, "20", AFTER),
    )
    build = EventBuilder(before, after)
    refs = (nation_ref("20"), faction_ref("15"), faction_ref("16"), faction_ref("17"))
    event = build.event(TEST_EVENT, id_parts=("x",), sources=(), entities=refs)
    assert dict(event.attribute(FACTION_KINDS).items) == {"faction:15": "human", "faction:16": "alien"}  # type: ignore[union-attr]
    plain = build.event(TEST_EVENT, id_parts=("y",), sources=(), entities=(nation_ref("20"), faction_ref("17")))
    assert plain.attributes == ()  # no faction of known template: no attribute
