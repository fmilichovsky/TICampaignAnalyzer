"""Organization events: presence, assignment and faction orbit, corroborated by councilor and faction org lists."""

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    analyze,
    councilor_ref,
    faction_ref,
    named,
    org_ref,
    region_ref,
    snapshot,
    state,
)
from tinarrative.analyzers.politics import OrganizationAnalyzer
from tinarrative.analyzers.politics.organizations import (
    ASSIGNED_COUNCILOR_CHANGED,
    COUNCILOR_ORGS_CHANGED,
    FACTION_ORBIT_CHANGED,
    UNASSIGNED_ORGS_CHANGED,
)
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, SourceRole
from tinarrative.model.values import Unknown, UnknownReason, freeze

ANALYZER = OrganizationAnalyzer()
ORG = EntityDomain.ORGANIZATION
COUNCILOR = EntityDomain.COUNCILOR
FACTION = EntityDomain.FACTION


def org(save: str, key: str = "70", councilor: str | None = None, orbit: str | None = None) -> object:
    return state(
        ORG,
        key,
        save,
        assignedCouncilor=councilor_ref(councilor) if councilor else None,
        factionOrbit=faction_ref(orbit) if orbit else None,
        homeRegion=region_ref("40"),
        tier=1,
    )


def councilor(save: str, key: str, *orgs: str, faction: str = "15") -> object:
    return state(COUNCILOR, key, save, faction=faction_ref(faction), orgs=tuple(org_ref(o) for o in orgs))


def faction(save: str, *unassigned: str, key: str = "15") -> object:
    return state(FACTION, key, save, unassignedOrgs=tuple(org_ref(o) for o in unassigned))


def sources(event: object) -> list[tuple[SourceRole, str, str | None]]:
    return [(s.role, str(s.change.entity_id), s.change.field) for s in event.sources]  # type: ignore[attr-defined]


def test_an_assignment_cites_the_councilor_list_and_the_faction_pool() -> None:
    before = snapshot(BEFORE, org(BEFORE), councilor(BEFORE, "100"), faction(BEFORE, "70"))
    after = snapshot(AFTER, org(AFTER, councilor="100"), councilor(AFTER, "100", "70"), faction(AFTER))
    (event,) = analyze(ANALYZER, before, after)
    assert event.id == "organization.assigned_councilor_changed/organization:70"
    assert event.event_type == ASSIGNED_COUNCILOR_CHANGED and event.confidence is Confidence.HIGH
    assert dict(event.attributes) == {"transition": "set", "before": None, "after": named(councilor_ref("100"))}
    assert sources(event) == [
        (SourceRole.PRIMARY, "organization:70", "assignedCouncilor"),
        (SourceRole.CORROBORATING, "councilor:100", "orgs"),
        (SourceRole.CORROBORATING, "faction:15", "unassignedOrgs"),
    ]
    assert [str(ref.entity_id) for ref in event.entities] == ["organization:70", "region:40", "councilor:100"]


def test_a_release_cites_the_councilor_list_and_the_faction_pool() -> None:
    before = snapshot(BEFORE, org(BEFORE, councilor="100"), councilor(BEFORE, "100", "70"), faction(BEFORE))
    after = snapshot(AFTER, org(AFTER), councilor(AFTER, "100"), faction(AFTER, "70"))
    (event,) = analyze(ANALYZER, before, after)
    assert dict(event.attributes) == {"transition": "cleared", "before": named(councilor_ref("100")), "after": None}
    assert sources(event) == [
        (SourceRole.PRIMARY, "organization:70", "assignedCouncilor"),
        (SourceRole.CORROBORATING, "councilor:100", "orgs"),
        (SourceRole.CORROBORATING, "faction:15", "unassignedOrgs"),
    ]


def test_a_transfer_cites_both_councilors() -> None:
    before = snapshot(BEFORE, org(BEFORE, councilor="100"), councilor(BEFORE, "100", "70"), councilor(BEFORE, "101"))
    after = snapshot(AFTER, org(AFTER, councilor="101"), councilor(AFTER, "100"), councilor(AFTER, "101", "70"))
    (event,) = analyze(ANALYZER, before, after)
    assert sources(event) == [
        (SourceRole.PRIMARY, "organization:70", "assignedCouncilor"),
        (SourceRole.CORROBORATING, "councilor:100", "orgs"),
        (SourceRole.CORROBORATING, "councilor:101", "orgs"),
    ]


def test_faction_orbit_changes_are_their_own_event() -> None:
    before = snapshot(BEFORE, org(BEFORE, orbit="15"))
    after = snapshot(AFTER, org(AFTER, orbit="16"))
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == FACTION_ORBIT_CHANGED
    assert [str(ref.entity_id) for ref in event.entities] == [
        "organization:70",
        "region:40",
        "faction:15",
        "faction:16",
    ]


def test_presence_cites_the_holders_list_entry() -> None:
    before = snapshot(BEFORE, org(BEFORE, "71", councilor="100"), councilor(BEFORE, "100", "71"))
    after = snapshot(AFTER, org(AFTER, councilor="100"), councilor(AFTER, "100", "70"))
    events = analyze(ANALYZER, before, after)
    assert sorted(event.id for event in events) == [
        "organization.appeared/organization:70",
        "organization.disappeared/organization:71",
    ]
    appeared = next(event for event in events if event.id.startswith("organization.appeared"))
    assert dict(appeared.attributes) == {"side": "after"}
    assert sources(appeared) == [
        (SourceRole.PRIMARY, "organization:70", None),
        (SourceRole.CORROBORATING, "councilor:100", "orgs"),
    ]
    gone = next(event for event in events if event.id.startswith("organization.disappeared"))
    assert sources(gone)[1] == (SourceRole.CORROBORATING, "councilor:100", "orgs")


def test_unexplained_list_changes_are_reported_on_their_own() -> None:
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze([{"value": 999}]))
    before = snapshot(BEFORE, org(BEFORE), councilor(BEFORE, "100"), faction(BEFORE))
    after = snapshot(
        AFTER, org(AFTER), councilor(AFTER, "100", "70"), state(FACTION, "15", AFTER, unassignedOrgs=unresolved)
    )
    events = analyze(ANALYZER, before, after)
    assert sorted(event.id for event in events) == [
        "councilor.orgs_changed/councilor:100/organization:70/added",
        "faction.unassigned_orgs_changed/faction:15/unresolved",
    ]
    assert {event.event_type for event in events} == {COUNCILOR_ORGS_CHANGED, UNASSIGNED_ORGS_CHANGED}
    assert next(e for e in events if e.event_type == UNASSIGNED_ORGS_CHANGED).confidence is Confidence.LOW
