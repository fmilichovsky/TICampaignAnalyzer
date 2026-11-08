"""Significance rules on synthetic events: one test per rule and branch, plus coverage of every event type."""

from __future__ import annotations

from dataclasses import replace

import pytest

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
from tests.narrative.support import ref
from tinarrative.analyzers import POLITICS_ANALYZERS, run_analyzers
from tinarrative.analyzers.base import Analyzer
from tinarrative.analyzers.common import Lookup
from tinarrative.analyzers.military import ArmyAnalyzer
from tinarrative.analyzers.politics import CouncilorAnalyzer, NationMetricAnalyzer, OrganizationAnalyzer
from tinarrative.analyzers.render import _TEMPLATES
from tinarrative.diff.state_diff import diff_states
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef
from tinarrative.model.events import SIGNIFICANCE_ORDER, Confidence, DateBasis, Event, EventStatus, Significance
from tinarrative.model.snapshot import EntityState, SaveSnapshot
from tinarrative.model.values import Observed, Unknown, UnknownReason
from tinarrative.narrative import assign_significance, significance, significance_of
from tinarrative.narrative.significance import BASE, DEFAULT, RULES, SCALED

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


def test_an_organization_changing_hands_is_scaled_by_its_tier_share() -> None:
    def assigned(tier: int) -> Event:
        orgs = {"70": tier, "71": 3, "72": 3, "73": 3, "74": 3, "75": 3, "76": 3, "77": 3, "78": 3, "79": 3}
        before = snapshot(
            BEFORE,
            *(
                state(ORG, key, BEFORE, assignedCouncilor=None, homeRegion=region_ref("40"), tier=t)
                for key, t in orgs.items()
            ),
        )
        after = snapshot(
            AFTER,
            *(
                state(
                    ORG,
                    key,
                    AFTER,
                    assignedCouncilor=councilor_ref("100") if key == "70" else None,
                    homeRegion=region_ref("40"),
                    tier=t,
                )
                for key, t in orgs.items()
            ),
        )
        return only(classified(OrganizationAnalyzer(), before, after), "organization.assigned_councilor_changed")

    top, low = assigned(3), assigned(1)
    assert top.score > low.score
    assert top.significance_basis is not None
    assert top.significance_basis.measure == "organization"
    assert top.significance_basis.share == 0.1
    assert top.significance_basis.scale == 10
    assert low.significance_basis is not None and low.significance_basis.scale < top.significance_basis.scale


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


def test_a_nuclear_arsenal_shift_is_major_and_any_other_statistic_shift_is_trivial() -> None:
    regions = (region_ref("40"),)
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, regions=regions, numNuclearWeapons=0, GDP=1.0e9))
    after = snapshot(AFTER, state(NATION, "20", AFTER, regions=regions, numNuclearWeapons=1, GDP=2.0e9))
    events = classified(NationMetricAnalyzer(), before, after)
    levels = {event.attribute("statistic"): event.significance for event in events}
    assert levels == {"numNuclearWeapons": Significance.MAJOR, "GDP": Significance.TRIVIAL}
    lookup = empty_lookup()
    assert significance_of(bare_event("nation.statistic_shifted", statistic="numControlPoints"), lookup) is (
        Significance.TRIVIAL
    )
    assert significance_of(bare_event("nation.statistic_shifted"), lookup) is Significance.TRIVIAL


def test_a_population_drop_is_major_growth_minor_and_a_gdp_trend_trivial() -> None:
    lookup = empty_lookup()
    assert significance_of(bare_event("nation.population_changed", direction="drop"), lookup) is Significance.MAJOR
    assert significance_of(bare_event("nation.population_changed", direction="growth"), lookup) is Significance.MINOR
    assert significance_of(bare_event("nation.pcgdp_trend"), lookup) is Significance.TRIVIAL


def test_first_space_defences_are_major_other_space_assets_minor_and_a_rank_change_trivial() -> None:
    lookup = empty_lookup()
    first = bare_event("nation.space_assets_changed", statistic="spaceDefences", before=0)
    more = bare_event("nation.space_assets_changed", statistic="spaceDefences", before=2)
    boost = bare_event("nation.space_assets_changed", statistic="boost", before=0)
    assert significance_of(first, lookup) is Significance.MAJOR
    assert significance_of(more, lookup) is Significance.MINOR
    assert significance_of(boost, lookup) is Significance.MINOR
    assert significance_of(bare_event("nation.rank_changed"), lookup) is Significance.TRIVIAL


# --- Table, defaults and the pass itself -------------------------------------------------------------------


def test_unlisted_and_notification_types_take_the_default() -> None:
    lookup = empty_lookup()
    assert significance_of(bare_event("fleet.fixture_unknown"), lookup) is DEFAULT
    assert significance_of(bare_event("notification.FixtureTemplate"), lookup) is DEFAULT
    assert significance_of(bare_event("notification.unknown_template"), lookup) is DEFAULT


def test_table_entries_resolve_without_context() -> None:
    lookup = empty_lookup()
    expected = {
        "councilor.location_changed": Significance.TRIVIAL,
        "ship.fleet_changed": Significance.TRIVIAL,
        "fleet.orbit_changed": Significance.MINOR,
        "nation.regions_changed": Significance.MINOR,
        "nation.hostile_claims_changed": Significance.MINOR,
        "faction.finished_project_names_changed": Significance.MINOR,
        "nation.unrest_attempts_changed": Significance.MINOR,
        "nation.new_government_recorded": Significance.MINOR,
        "nation.nuclear_program_changed": Significance.MINOR,
        "nation.policy_changed": Significance.MINOR,
        "control_point.controller_changed": Significance.MAJOR,
        "nation.renamed": Significance.MAJOR,
        "federation.renamed": Significance.MAJOR,
        "campaign.global_milestone_recorded": Significance.CAMPAIGN_DEFINING,
        "nation.disappeared": Significance.CAMPAIGN_DEFINING,
    }
    assert {event_type: significance_of(bare_event(event_type), lookup) for event_type in expected} == expected


def test_a_completion_takes_its_curated_tier_and_an_unlisted_one_is_minor() -> None:
    lookup = empty_lookup()

    def technology(name: str) -> Event:
        return replace(bare_event("technology.completed"), entities=(ref(EntityDomain.TECHNOLOGY, name),))

    def project(name: str) -> Event:
        return bare_event("faction.project_completed", project=name)

    assert significance_of(technology("DeuteriumTritiumFusion"), lookup) is Significance.CAMPAIGN_DEFINING
    assert significance_of(technology("SpaceNavies"), lookup) is Significance.MAJOR
    assert significance_of(technology("PrinciplesofSpaceWarfare"), lookup) is Significance.MINOR
    assert significance_of(technology("KineticsWarfareDoctrine"), lookup) is Significance.MINOR
    assert significance_of(project("Project_KilltheHive"), lookup) is Significance.CAMPAIGN_DEFINING
    assert significance_of(project("Project_Warships"), lookup) is Significance.MAJOR
    assert significance_of(project("Project_SpaceTugs"), lookup) is Significance.MINOR
    assert significance_of(bare_event("technology.completed"), lookup) is Significance.MINOR
    assert significance_of(bare_event("faction.project_completed"), lookup) is Significance.MINOR


def test_the_pass_gives_every_event_the_base_score_of_its_level() -> None:
    def technology(name: str) -> Event:
        return replace(bare_event("technology.completed"), entities=(ref(EntityDomain.TECHNOLOGY, name),))

    snap = snapshot(BEFORE)
    events = [
        technology("DeuteriumTritiumFusion"),  # campaign_defining milestone
        technology("SpaceNavies"),  # major milestone
        bare_event("fleet.orbit_changed"),  # minor in the table
        bare_event("nation.rank_changed"),  # trivial in the table
        bare_event("nation.relation_changed", relation="wars"),  # major by its context rule
    ]
    assigned = assign_significance(events, snap, snap)
    assert [event.score for event in assigned] == [
        Significance.CAMPAIGN_DEFINING.base,
        Significance.MAJOR.base,
        Significance.MINOR.base,
        Significance.TRIVIAL.base,
        Significance.MAJOR.base,
    ]
    assert all(event.score == event.significance.base for event in assigned)


def test_a_ledger_charge_is_minor_and_named_in_the_table() -> None:
    assert "faction.transaction_recorded" in BASE  # corroboration only (architecture 11.3)
    assert significance_of(bare_event("faction.transaction_recorded"), empty_lookup()) is Significance.MINOR


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
    assert {event.score for event in assigned} == {Significance.TRIVIAL.base}
    assert len(assigned) == 3  # two recruit-pool presences and one location move


def test_serialization_carries_the_level_and_score() -> None:
    event = bare_event("fleet.orbit_changed")
    assert event.to_dict()["significance"] == "minor"
    assert event.to_dict()["score"] == Significance.MINOR.base


def test_the_alien_administrations_claims_are_minor_and_a_human_nations_are_major() -> None:
    claims = replace(bare_event("nation.claims_changed"), entities=(nation_ref("21"),))
    for alien, expected in ((True, Significance.MINOR), (False, Significance.MAJOR)):
        lookup = Lookup(
            snapshot(BEFORE, state(NATION, "21", BEFORE, alienNation=alien)),
            snapshot(AFTER, state(NATION, "21", AFTER, alienNation=alien)),
        )
        assert significance_of(claims, lookup) is expected, alien
    assert significance_of(claims, empty_lookup()) is Significance.MAJOR
    assert significance_of(bare_event("nation.claims_changed"), empty_lookup()) is Significance.MAJOR


# --- Entity-scaled score ----------------------------------------------------------------------------------

BIG, MICRO, OTHER = "20", "21", "22"


def scaled_event(
    event_type: str, *entities: EntityRef, constituents: tuple[str, ...] = (), **attributes: Observed
) -> Event:
    return replace(bare_event(event_type, **attributes), entities=entities, constituents=constituents)


def scored(
    monkeypatch: pytest.MonkeyPatch,
    event: Event,
    *,
    power: dict[str, float] | None = None,
    regions: dict[str, float] | None = None,
    evidence: tuple[Event, ...] = (),
    states: tuple[EntityState, ...] = (),
) -> Event:
    def keyed(shares: dict[str, float] | None, domain: EntityDomain) -> dict[EntityId, float]:
        return {EntityId(domain, key): share for key, share in (shares or {}).items()}

    monkeypatch.setattr(significance, "nation_power", lambda *_: keyed(power, NATION))
    monkeypatch.setattr(significance, "region_shares", lambda *_: keyed(regions, EntityDomain.REGION))
    before, after = snapshot(BEFORE, *states), snapshot(AFTER, *states)
    return assign_significance([event], before, after, evidence=evidence)[0]


POWER = {BIG: 0.3, MICRO: 0.001, OTHER: 0.1}
NATION_TYPES = (
    "nation.executive_change_recorded",
    "nation.appeared",
    "nation.disappeared",
    "nation.statistic_shifted",
    "nation.federation_changed",
    "nation.claims_changed",
    "faction.nation_control_changed",
)


@pytest.mark.parametrize("event_type", NATION_TYPES)
def test_a_nation_event_scores_higher_for_a_large_nation_than_a_micro_state(
    monkeypatch: pytest.MonkeyPatch, event_type: str
) -> None:
    big = scored(monkeypatch, scaled_event(event_type, nation_ref(BIG)), power=POWER)
    micro = scored(monkeypatch, scaled_event(event_type, nation_ref(MICRO)), power=POWER)
    assert big.score > micro.score
    assert big.significance_basis is not None and micro.significance_basis is not None
    assert (big.significance_basis.measure, big.significance_basis.share) == ("power", 0.3)
    assert micro.significance_basis.scale == -10
    assert big.significance_basis.entities == (nation_ref(BIG),)


def test_a_micro_states_disappearance_is_major_and_a_large_states_campaign_defining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    power = {BIG: 0.3, MICRO: 0.0005}
    micro = scored(monkeypatch, scaled_event("nation.disappeared", nation_ref(MICRO)), power=power)
    big = scored(monkeypatch, scaled_event("nation.disappeared", nation_ref(BIG)), power=power)
    assert micro.significance is Significance.MAJOR
    assert big.significance is Significance.CAMPAIGN_DEFINING


def test_a_stake_at_the_reference_share_keeps_the_level_and_the_clamp_bounds_the_scale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    at_reference = scored(
        monkeypatch, scaled_event("nation.disappeared", nation_ref(BIG)), power={BIG: 0.01, OTHER: 0.99}
    )
    assert at_reference.score == Significance.CAMPAIGN_DEFINING.base
    assert at_reference.significance_basis is not None and at_reference.significance_basis.scale == 0
    tiny = scored(monkeypatch, scaled_event("nation.disappeared", nation_ref(BIG)), power={BIG: 1e-12, OTHER: 1.0})
    assert tiny.significance_basis is not None and tiny.significance_basis.scale == -20
    empty = scored(monkeypatch, scaled_event("nation.disappeared", nation_ref(BIG)), power={BIG: 0.0})
    assert empty.significance_basis is not None and empty.significance_basis.scale == -20


def test_the_stake_is_read_on_the_later_side_for_an_entity_that_exists_only_there(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def power(snapshot: SaveSnapshot, *_: object) -> dict[EntityId, float]:
        calls.append(1)
        return {EntityId(NATION, BIG): 0.2} if snapshot.source == AFTER else {}

    monkeypatch.setattr(significance, "nation_power", power)
    monkeypatch.setattr(significance, "region_shares", lambda *_: {})
    event = scaled_event("nation.appeared", nation_ref(BIG))
    result = assign_significance([event], snapshot(BEFORE), snapshot(AFTER))[0]
    assert result.significance_basis is not None and result.significance_basis.share == 0.2


def test_a_war_sums_both_nations_and_nuclear_arms_on_both_sides_add_the_bonus(monkeypatch: pytest.MonkeyPatch) -> None:
    pair = (nation_ref(BIG), nation_ref(OTHER))
    war = scaled_event("nation.relation_changed", *pair, relation="wars")
    unarmed = scored(monkeypatch, war, power=POWER)
    assert unarmed.significance_basis is not None
    assert unarmed.significance_basis.share == 0.4 and unarmed.significance_basis.bonus == 0
    armed_states = tuple(state(NATION, key, BEFORE, numNuclearWeapons=3) for key in (BIG, OTHER))
    armed = scored(monkeypatch, war, power=POWER, states=armed_states)
    assert armed.significance_basis is not None and armed.significance_basis.bonus == 5
    assert armed.score == unarmed.score + 5
    one_sided = scored(monkeypatch, war, power=POWER, states=armed_states[:1])
    assert one_sided.significance_basis is not None and one_sided.significance_basis.bonus == 0


def test_only_wars_are_scaled_among_relations(monkeypatch: pytest.MonkeyPatch) -> None:
    pair = (nation_ref(BIG), nation_ref(OTHER))
    allies = scored(monkeypatch, scaled_event("nation.relation_changed", *pair, relation="allies"), power=POWER)
    assert allies.significance_basis is None and allies.score == Significance.MINOR.base


REGIONS = {"40": 0.2, "41": 0.0005}


def test_a_transfer_is_scaled_by_the_population_share_of_the_territory(monkeypatch: pytest.MonkeyPatch) -> None:
    large = scored(monkeypatch, scaled_event("region.nation_changed", region_ref("40")), regions=REGIONS)
    small = scored(monkeypatch, scaled_event("region.nation_changed", region_ref("41")), regions=REGIONS)
    assert large.score > small.score
    assert large.significance_basis is not None and large.significance_basis.measure == "population"
    both = scored(
        monkeypatch,
        scaled_event(
            "nation.territory_gained",
            nation_ref(BIG),
            region_ref("40"),
            region_ref("41"),
            regions=(region_ref("40"), region_ref("41")),
        ),
        regions=REGIONS,
    )
    assert both.significance_basis is not None and both.significance_basis.share == 0.2005


def test_an_independence_takes_its_territory_from_the_region_events_it_cites(monkeypatch: pytest.MonkeyPatch) -> None:
    transfer = replace(scaled_event("region.nation_changed", region_ref("40")), id="region.nation_changed/region:40")
    independence = scaled_event("nation.independence", nation_ref(BIG), constituents=(transfer.id,))
    result = scored(monkeypatch, independence, regions=REGIONS, evidence=(transfer,))
    assert result.significance_basis is not None and result.significance_basis.share == 0.2
    assert scored(monkeypatch, independence, regions=REGIONS).significance_basis is None


def test_a_single_control_point_is_scaled_by_its_share_of_the_nations_power(monkeypatch: pytest.MonkeyPatch) -> None:
    nation_state = state(
        NATION, BIG, BEFORE, controlPoints=(ref(EntityDomain.CONTROL_POINT, "1"), ref(EntityDomain.CONTROL_POINT, "2"))
    )
    event = scaled_event("control_point.controller_changed", ref(EntityDomain.CONTROL_POINT, "1"), nation_ref(BIG))
    result = scored(monkeypatch, event, power=POWER, states=(nation_state,))
    assert result.significance_basis is not None and result.significance_basis.share == 0.15


def test_churn_and_movement_are_never_scaled(monkeypatch: pytest.MonkeyPatch) -> None:
    for event_type in (
        "fleet.orbit_changed",
        "councilor.location_changed",
        "nation.rank_changed",
        "nation.band_crossed",
    ):
        result = scored(monkeypatch, scaled_event(event_type, nation_ref(BIG)), power=POWER)
        assert result.significance_basis is None
        assert result.score == BASE.get(event_type, DEFAULT).base


def test_every_scaled_type_names_a_known_measure() -> None:
    assert {stake.measure for stake in SCALED.values()} <= {"power", "population", "organization"}
    assert not {"fleet.orbit_changed", "nation.rank_changed", "nation.population_changed"} & set(SCALED)


def test_the_basis_is_in_the_event_json(monkeypatch: pytest.MonkeyPatch) -> None:
    result = scored(monkeypatch, scaled_event("nation.appeared", nation_ref(MICRO)), power=POWER)
    basis = result.to_dict()["significance_basis"]
    assert {key: basis[key] for key in ("base", "measure", "share", "scale")} == {
        "base": Significance.CAMPAIGN_DEFINING.base,
        "measure": "power",
        "share": 0.001,
        "scale": -10,
    }
    assert "significance_basis" not in bare_event("nation.rank_changed").to_dict()
