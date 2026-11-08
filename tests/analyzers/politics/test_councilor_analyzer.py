"""Councilor events: faction membership, status, location, detention, presence and roster leftovers."""

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    analyze,
    by_type,
    councilor_ref,
    faction_ref,
    named,
    only,
    ref,
    region_ref,
    snapshot,
    state,
)
from tinarrative.analyzers.politics import CouncilorAnalyzer
from tinarrative.analyzers.politics.councilors import (
    APPEARED,
    DETAINING_FACTION_CHANGED,
    DISAPPEARED,
    FACTION_CHANGED,
    LOCATION_CHANGED,
    ROSTER_CHANGED,
    STATUS_CHANGED,
)
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, SourceRole
from tinarrative.model.values import Unknown, UnknownReason, freeze

ANALYZER = CouncilorAnalyzer()
COUNCILOR = EntityDomain.COUNCILOR
FACTION = EntityDomain.FACTION


def test_faction_change_cites_both_rosters() -> None:
    before = snapshot(
        BEFORE,
        state(COUNCILOR, "100", BEFORE, faction=faction_ref("15")),
        state(FACTION, "15", BEFORE, councilors=(councilor_ref("100"),)),
        state(FACTION, "16", BEFORE, councilors=()),
    )
    after = snapshot(
        AFTER,
        state(COUNCILOR, "100", AFTER, faction=faction_ref("16")),
        state(FACTION, "15", AFTER, councilors=()),
        state(FACTION, "16", AFTER, councilors=(councilor_ref("100"),)),
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == FACTION_CHANGED and event.confidence is Confidence.HIGH
    assert [str(r.entity_id) for r in event.entities] == ["councilor:100", "faction:15", "faction:16"]
    assert dict(event.attributes) == {
        "transition": "changed",
        "before": named(faction_ref("15")),
        "after": named(faction_ref("16")),
    }
    assert [(s.role, str(s.change.entity_id), s.member) for s in event.sources] == [
        (SourceRole.PRIMARY, "councilor:100", None),
        (SourceRole.CORROBORATING, "faction:15", councilor_ref("100")),
        (SourceRole.CORROBORATING, "faction:16", councilor_ref("100")),
    ]


def test_status_location_and_detention_are_separate_events_with_the_faction_as_context() -> None:
    hab = ref(EntityDomain.SPACE_OBJECT, "140")
    before = snapshot(
        BEFORE,
        state(
            COUNCILOR,
            "100",
            BEFORE,
            faction=faction_ref("15"),
            status="Available",
            location=region_ref("40"),
            detainingFaction=None,
        ),
        state(FACTION, "15", BEFORE),
    )
    after = snapshot(
        AFTER,
        state(
            COUNCILOR,
            "100",
            AFTER,
            faction=faction_ref("15"),
            status="Fixture Status",
            location=hab,
            detainingFaction=faction_ref("16"),
        ),
        state(FACTION, "15", AFTER),
    )
    events = analyze(ANALYZER, before, after)
    assert [event.event_type for event in events] == [STATUS_CHANGED, LOCATION_CHANGED, DETAINING_FACTION_CHANGED]
    status, location, detention = events
    assert dict(status.attributes) == {"transition": "changed", "before": "Available", "after": "Fixture Status"}
    assert [str(r.entity_id) for r in status.entities] == ["councilor:100", "faction:15"]
    assert [str(r.entity_id) for r in location.entities] == [
        "councilor:100",
        "faction:15",
        "region:40",
        "space object:140",
    ]
    assert dict(detention.attributes) == {"transition": "set", "before": None, "after": faction_ref("16")}
    assert [str(r.entity_id) for r in detention.entities] == ["councilor:100", "faction:15", "faction:16"]
    assert all(len(event.sources) == 1 and event.sources[0].role is SourceRole.PRIMARY for event in events)


def test_unresolved_location_is_low_confidence_and_churn_fields_are_ignored() -> None:
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 999}))
    before = snapshot(
        BEFORE,
        state(
            COUNCILOR,
            "100",
            BEFORE,
            location=region_ref("40"),
            priorLocation=None,
            XP=12,
            orgs=(ref(EntityDomain.ORGANIZATION, "70"),),
        ),
    )
    after = snapshot(
        AFTER,
        state(COUNCILOR, "100", AFTER, location=unresolved, priorLocation=region_ref("40"), XP=20, orgs=()),
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == LOCATION_CHANGED and event.confidence is Confidence.LOW
    assert dict(event.attributes) == {"transition": "unresolved", "before": region_ref("40"), "after": unresolved}
    assert [str(r.entity_id) for r in event.entities] == ["councilor:100", "region:40"]


def test_presence_cites_the_roster_of_the_faction_on_the_existing_side() -> None:
    before = snapshot(
        BEFORE,
        state(COUNCILOR, "101", BEFORE, faction=faction_ref("15")),
        state(FACTION, "15", BEFORE, councilors=(councilor_ref("101"),)),
    )
    after = snapshot(
        AFTER,
        state(COUNCILOR, "102", AFTER, faction=None),
        state(FACTION, "15", AFTER, councilors=(councilor_ref("102"),)),
    )
    events = analyze(ANALYZER, before, after)
    gone = only(events, DISAPPEARED)
    assert gone.attribute("side") == "before" and gone.confidence is Confidence.HIGH
    assert [str(r.entity_id) for r in gone.entities] == ["councilor:101", "faction:15"]
    assert [(s.role, str(s.change.entity_id)) for s in gone.sources] == [
        (SourceRole.PRIMARY, "councilor:101"),
        (SourceRole.CORROBORATING, "faction:15"),
    ]
    new = only(events, APPEARED)
    assert [str(r.entity_id) for r in new.entities] == ["councilor:102"] and len(new.sources) == 1
    # the councilor's own faction field was null, so the roster entry is unexplained and reported on its own
    roster = only(events, ROSTER_CHANGED)
    assert roster.id == "faction.councilors_changed/faction:15/councilor:102/added"
    assert len(events) == 3


def test_identical_snapshots_and_missing_fields_produce_nothing() -> None:
    before = snapshot(BEFORE, state(COUNCILOR, "100", BEFORE, faction=faction_ref("15"), status="Available"))
    after = snapshot(AFTER, state(COUNCILOR, "100", AFTER, faction=faction_ref("15")))
    assert analyze(ANALYZER, before, after) == []
    assert analyze(ANALYZER, before, before) == []
    assert not by_type(analyze(ANALYZER, after, before), STATUS_CHANGED)
