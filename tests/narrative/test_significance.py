"""Significance rules on synthetic events: one test per rule and branch, plus coverage of every event type."""

from __future__ import annotations

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    MEGAFAUNA_STATE_TYPE,
    analyze,
    councilor_ref,
    faction_ref,
    fixture_pair,
    nation_ref,
    only,
    region_ref,
    snapshot,
    state,
)
from tinarrative.analyzers import POLITICS_ANALYZERS, run_analyzers
from tinarrative.analyzers.base import Analyzer
from tinarrative.analyzers.common import Lookup
from tinarrative.analyzers.military import ArmyAnalyzer
from tinarrative.analyzers.politics import CouncilorAnalyzer, NationMetricAnalyzer, OrganizationAnalyzer
from tinarrative.analyzers.render import _TEMPLATES
from tinarrative.diff.state_diff import diff_states
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import SIGNIFICANCE_ORDER, Confidence, DateBasis, Event, EventStatus, Significance
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.model.values import Observed, Unknown, UnknownReason
from tinarrative.narrative import assign_significance, significance_of
from tinarrative.narrative.significance import BASE, DEFAULT, RULES

COUNCILOR = EntityDomain.COUNCILOR
FACTION = EntityDomain.FACTION
NATION = EntityDomain.NATION
ORG = EntityDomain.ORGANIZATION
ARMY = EntityDomain.ARMY


def bare_event(event_type: str, **attributes: Observed) -> Event:
    """An event of ``event_type`` with no sources and no entities; the rules must cope with it."""
    return Event(
        id=f"{event_type}/x",
        event_type=event_type,
        status=EventStatus.OBJECTIVE,
        confidence=Confidence.HIGH,
        date=Unknown(),
        date_basis=DateBasis.INTERVAL,
        not_before=Unknown(),
        sources=(),
        entities=(),
        attributes=tuple(attributes.items()),
    )


def empty_lookup() -> Lookup:
    return Lookup(snapshot(BEFORE), snapshot(AFTER))


def classified(analyzer: Analyzer, before: SaveSnapshot, after: SaveSnapshot) -> tuple[Event, ...]:
    return assign_significance(analyze(analyzer, before, after), before, after)


# --- Recruit-pool councilors ------------------------------------------------------------------------------


def test_councilor_presence_with_a_null_faction_is_trivial_on_both_sides() -> None:
    before = snapshot(BEFORE, state(COUNCILOR, "100", BEFORE, faction=None))
    after = snapshot(AFTER, state(COUNCILOR, "101", AFTER, faction=None))
    events = classified(CouncilorAnalyzer(), before, after)
    assert only(events, "councilor.disappeared").significance is Significance.TRIVIAL
    assert only(events, "councilor.appeared").significance is Significance.TRIVIAL


def test_a_councilor_with_a_faction_is_major_when_gone_and_minor_when_new() -> None:
    before = snapshot(
        BEFORE,
        state(COUNCILOR, "100", BEFORE, faction=faction_ref("15")),
        state(FACTION, "15", BEFORE, councilors=(councilor_ref("100"),)),
    )
    after = snapshot(
        AFTER,
        state(COUNCILOR, "101", AFTER, faction=faction_ref("15")),
        state(FACTION, "15", AFTER, councilors=(councilor_ref("101"),)),
    )
    events = classified(CouncilorAnalyzer(), before, after)
    assert only(events, "councilor.disappeared").significance is Significance.MAJOR
    assert only(events, "councilor.appeared").significance is Significance.MINOR


def test_a_councilor_whose_faction_is_unknown_defers_to_the_default() -> None:
    unknown = Unknown(UnknownReason.UNRESOLVED_REFERENCE, raw=999)
    before = snapshot(BEFORE, state(COUNCILOR, "100", BEFORE, faction=unknown))
    after = snapshot(AFTER)
    (event,) = classified(CouncilorAnalyzer(), before, after)
    assert event.event_type == "councilor.disappeared" and event.significance is DEFAULT


def test_a_presence_event_without_a_subject_or_side_falls_back_to_the_table() -> None:
    lookup = empty_lookup()
    assert significance_of(bare_event("councilor.disappeared"), lookup) is DEFAULT
    assert significance_of(bare_event("councilor.disappeared", side="before"), lookup) is DEFAULT


# --- Relations, executives, organizations, megafauna -------------------------------------------------------


def test_a_war_relation_is_major_and_an_alliance_is_minor() -> None:
    before = snapshot(
        BEFORE,
        state(NATION, "20", BEFORE, allies=(), wars=()),
        state(NATION, "21", BEFORE, allies=(), wars=()),
        state(NATION, "22", BEFORE, allies=(), wars=()),
    )
    after = snapshot(
        AFTER,
        state(NATION, "20", AFTER, allies=(nation_ref("21"),), wars=(nation_ref("22"),)),
        state(NATION, "21", AFTER, allies=(nation_ref("20"),), wars=()),
        state(NATION, "22", AFTER, allies=(), wars=(nation_ref("20"),)),
    )
    events = assign_significance(
        run_analyzers(POLITICS_ANALYZERS, before, after, diff_states(before, after)), before, after
    )
    by_relation = {event.attribute("relation"): event.significance for event in events}
    assert by_relation == {"allies": Significance.MINOR, "wars": Significance.MAJOR}


def test_an_executive_change_is_major_only_for_an_upheaval_cause() -> None:
    before, after, diff = fixture_pair("records_before.json", "records_after.json")
    events = assign_significance(run_analyzers(POLITICS_ANALYZERS, before, after, diff), before, after)
    (recorded,) = [event for event in events if event.event_type == "nation.executive_change_recorded"]
    assert recorded.attribute("cause") == "Coup" and recorded.significance is Significance.MAJOR
    lookup = empty_lookup()
    assert (
        significance_of(bare_event("nation.executive_change_recorded", cause="Politics"), lookup) is Significance.MINOR
    )
    assert significance_of(bare_event("nation.executive_change_recorded"), lookup) is Significance.MINOR


def test_a_top_tier_organization_changing_hands_is_major_and_a_lower_tier_is_minor() -> None:
    for tier, expected in ((3, Significance.MAJOR), (1, Significance.MINOR), (Unknown(), Significance.MINOR)):
        before = snapshot(
            BEFORE, state(ORG, "70", BEFORE, assignedCouncilor=None, homeRegion=region_ref("40"), tier=tier)
        )
        after = snapshot(
            AFTER,
            state(ORG, "70", AFTER, assignedCouncilor=councilor_ref("100"), homeRegion=region_ref("40"), tier=tier),
        )
        events = classified(OrganizationAnalyzer(), before, after)
        assert only(events, "organization.assigned_councilor_changed").significance is expected, tier


def test_megafauna_presence_is_major_and_regular_army_presence_is_minor() -> None:
    before = snapshot(BEFORE, state(ARMY, "110", BEFORE, faction=faction_ref("15"), currentRegion=region_ref("40")))
    after = snapshot(
        AFTER,
        state(
            ARMY,
            "112",
            AFTER,
            state_type=MEGAFAUNA_STATE_TYPE,
            faction=faction_ref("16"),
            currentRegion=region_ref("41"),
        ),
    )
    events = classified(ArmyAnalyzer(), before, after)
    assert only(events, "army.disappeared").significance is Significance.MINOR
    assert only(events, "army.appeared").significance is Significance.MAJOR


def test_a_discrete_statistic_shift_is_major_and_a_continuous_one_is_minor() -> None:
    regions = (region_ref("40"),)
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, regions=regions, numNuclearWeapons=0, GDP=1.0e9))
    after = snapshot(AFTER, state(NATION, "20", AFTER, regions=regions, numNuclearWeapons=1, GDP=2.0e9))
    events = classified(NationMetricAnalyzer(), before, after)
    levels = {event.attribute("statistic"): event.significance for event in events}
    assert levels == {"numNuclearWeapons": Significance.MAJOR, "GDP": Significance.MINOR}
    lookup = empty_lookup()
    assert significance_of(bare_event("nation.statistic_shifted", statistic="numControlPoints"), lookup) is (
        Significance.MAJOR
    )
    assert significance_of(bare_event("nation.statistic_shifted"), lookup) is Significance.MINOR


# --- Table, defaults and the pass itself -------------------------------------------------------------------


def test_unlisted_and_notification_types_take_the_default() -> None:
    lookup = empty_lookup()
    assert significance_of(bare_event("fleet.fixture_unknown"), lookup) is DEFAULT
    assert significance_of(bare_event("notification.FixtureTemplate"), lookup) is DEFAULT
    assert significance_of(bare_event("notification.unknown_template"), lookup) is DEFAULT


def test_table_entries_resolve_without_context() -> None:
    lookup = empty_lookup()
    assert significance_of(bare_event("councilor.location_changed"), lookup) is Significance.TRIVIAL
    assert significance_of(bare_event("ship.fleet_changed"), lookup) is Significance.TRIVIAL
    assert significance_of(bare_event("fleet.orbit_changed"), lookup) is Significance.MINOR
    assert significance_of(bare_event("nation.regions_changed"), lookup) is Significance.MINOR
    assert significance_of(bare_event("control_point.controller_changed"), lookup) is Significance.MAJOR
    assert significance_of(bare_event("technology.completed"), lookup) is Significance.MAJOR
    assert significance_of(bare_event("campaign.global_milestone_recorded"), lookup) is Significance.CAMPAIGN_DEFINING
    assert significance_of(bare_event("nation.disappeared"), lookup) is Significance.CAMPAIGN_DEFINING


def test_every_known_event_type_resolves_and_every_rule_names_a_known_type() -> None:
    lookup = empty_lookup()
    for event_type in _TEMPLATES:
        assert significance_of(bare_event(event_type), lookup) in SIGNIFICANCE_ORDER, event_type
    assert set(BASE) <= set(_TEMPLATES), sorted(set(BASE) - set(_TEMPLATES))
    assert set(RULES) <= set(_TEMPLATES), sorted(set(RULES) - set(_TEMPLATES))
    assert not set(BASE) & set(RULES)  # a type is decided by its rule or by the table, never both


def test_the_pass_keeps_order_and_ids_and_is_idempotent() -> None:
    before = snapshot(
        BEFORE,
        state(COUNCILOR, "100", BEFORE, faction=None),
        state(COUNCILOR, "102", BEFORE, faction=faction_ref("15"), location=region_ref("40")),
        state(FACTION, "15", BEFORE, councilors=(councilor_ref("102"),)),
    )
    after = snapshot(
        AFTER,
        state(COUNCILOR, "101", AFTER, faction=None),
        state(COUNCILOR, "102", AFTER, faction=faction_ref("15"), location=region_ref("41")),
        state(FACTION, "15", AFTER, councilors=(councilor_ref("102"),)),
    )
    raw = run_analyzers(POLITICS_ANALYZERS, before, after, diff_states(before, after))
    assert all(event.significance is DEFAULT for event in raw)
    assigned = assign_significance(raw, before, after)
    assert [event.id for event in assigned] == [event.id for event in raw]
    assert assign_significance(assigned, before, after) == assigned
    assert {event.significance for event in assigned} == {Significance.TRIVIAL}
    assert len(assigned) == 3  # two recruit-pool presences and one location move


def test_serialization_carries_the_level() -> None:
    event = bare_event("fleet.orbit_changed")
    assert event.to_dict()["significance"] == "minor"
    assert (
        Significance.CAMPAIGN_DEFINING.rank
        > Significance.MAJOR.rank
        > Significance.MINOR.rank
        > Significance.TRIVIAL.rank
    )
