"""Territorial reconstruction: synthetic region transfers with tracker, executive, breakaway and war evidence."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    by_type,
    faction_ref,
    nation_ref,
    pair,
    point_ref,
    record_set,
    region_ref,
    snapshot,
    state,
)
from tests.reconstruction.support import Scenario, assert_traceable, lines_of, only, run
from tinarrative.analyzers.render import describe_event
from tinarrative.model.entities import EntityDomain, EntityRef
from tinarrative.model.events import Confidence, DateBasis, EventStatus, Significance, SourceRole
from tinarrative.model.records import KeyedEntry, RecordKind, RecordSet
from tinarrative.model.snapshot import EntityState
from tinarrative.model.values import Observed, Unknown, freeze
from tinarrative.reconstruction import (
    ANNEXATION,
    INDEPENDENCE,
    TERRITORY_GAINED,
    TERRITORY_LOST,
    UNIFICATION,
    infer_events,
)

NATION = EntityDomain.NATION
REGION = EntityDomain.REGION
GDP_TRACKER = "tracker_GDPChangeReason_AllTime"
INEQUALITY_TRACKER = "tracker_InequalityChangeReason_AllTime"
COHESION_TRACKER = "tracker_CohesionChangeReason_AllTime"
DEMOCRACY_TRACKER = "tracker_DemocracyChangeReason_AllTime"

Fields = Mapping[str, Mapping[str, Observed]]


def territory_pair(
    moves: Mapping[str, tuple[str, str]],
    *,
    kept: Mapping[str, tuple[str, ...]] | None = None,
    nation_before: Fields | None = None,
    nation_after: Fields | None = None,
    region_before: Fields | None = None,
    region_after: Fields | None = None,
    extra_before: tuple[EntityState, ...] = (),
    extra_after: tuple[EntityState, ...] = (),
    records_before: tuple[RecordSet, ...] = (),
    records_after: tuple[RecordSet, ...] = (),
) -> Scenario:
    """Regions ``moves`` from the first nation to the second; ``kept`` regions stay with their nation throughout."""
    kept = kept or {}
    nations = sorted({n for move in moves.values() for n in move} | set(kept))

    def nation_states(save: str, side: int, overrides: Fields | None) -> list[EntityState]:
        states = []
        for nation in nations:
            held = kept.get(nation, ()) + tuple(region for region, move in moves.items() if move[side] == nation)
            fields: dict[str, Observed] = {"regions": tuple(region_ref(region) for region in sorted(held))}
            fields.update((overrides or {}).get(nation, {}))
            states.append(state(NATION, nation, save, **fields))  # type: ignore[arg-type]
        return states

    def region_states(save: str, side: int, overrides: Fields | None) -> list[EntityState]:
        owners = {region: move[side] for region, move in moves.items()}
        owners.update({region: nation for nation, regions in kept.items() for region in regions})
        return [
            state(REGION, region, save, nation=nation_ref(owner), **(overrides or {}).get(region, {}))  # type: ignore[arg-type]
            for region, owner in sorted(owners.items())
        ]

    before = snapshot(
        BEFORE,
        *nation_states(BEFORE, 0, nation_before),
        *region_states(BEFORE, 0, region_before),
        *extra_before,
        records=records_before,
    )
    after = snapshot(
        AFTER,
        *nation_states(AFTER, 1, nation_after),
        *region_states(AFTER, 1, region_after),
        *extra_after,
        records=records_after,
    )
    return pair(before, after)


def ids(refs: Observed) -> list[str]:
    assert isinstance(refs, tuple)
    return [str(ref.entity_id) for ref in refs]  # type: ignore[union-attr]


def executive(save: str, nation: str, cause: str, date: str) -> RecordSet:
    entries = (
        KeyedEntry(0, "cause", cause),
        KeyedEntry(1, "date", date),
        KeyedEntry(2, "newExecutive", faction_ref("15")),
    )
    return record_set(save, nation_ref(nation), "lastExecutiveChange", RecordKind.EXECUTIVE_CHANGE, entries)


def war(save: str, attacking: tuple[str, ...], defending: tuple[str, ...]) -> EntityState:
    return state(
        EntityDomain.WAR,
        "60",
        save,
        attacker=nation_ref(attacking[0]),
        defender=nation_ref(defending[0]),
        _attackingAlliance=tuple(nation_ref(n) for n in attacking),
        _defendingAlliance=tuple(nation_ref(n) for n in defending),
    )


# --- Scenarios --------------------------------------------------------------------------------------------


def gdp_territory() -> Scenario:
    """Nation 20 takes regions 40 and 41 from nation 21; its GDP shift sits under ``GDPReason_TerritoryChange``."""
    return territory_pair(
        {"40": ("21", "20"), "41": ("21", "20")},
        kept={"20": ("30",), "21": ("31",)},
        nation_before={"20": {"GDP": 1.0e9, GDP_TRACKER: freeze({"GDPReason_EconomyPriority": 1.0e8})}},
        nation_after={
            "20": {
                "GDP": 3.0e9,
                GDP_TRACKER: freeze({"GDPReason_EconomyPriority": 1.0e8, "GDPReason_TerritoryChange": 2.0e9}),
            }
        },
    )


def plain_transfer() -> Scenario:
    return territory_pair({"40": ("21", "20")}, kept={"20": ("30",), "21": ("31",)})


def small_inequality_tracker() -> Scenario:
    """The inequality tracker moved under ``InqReason_Annexation`` but the statistic stayed below its threshold."""
    return territory_pair(
        {"40": ("21", "20")},
        kept={"20": ("30",), "21": ("31",)},
        nation_before={"20": {"inequality": 3.0, INEQUALITY_TRACKER: freeze({"InqReason_Annexation": 0.0})}},
        nation_after={"20": {"inequality": 3.01, INEQUALITY_TRACKER: freeze({"InqReason_Annexation": 0.01})}},
    )


def executive_independence() -> Scenario:
    """Region-less nation 25 takes region 40 from 21, records an ``Independence`` executive change and a cohesion
    delta under ``CohesionReason_Independence``."""
    return territory_pair(
        {"40": ("21", "25")},
        kept={"21": ("31",), "25": ()},
        nation_before={"25": {"cohesion": 5.0, COHESION_TRACKER: freeze({})}},
        nation_after={"25": {"cohesion": 1.0, COHESION_TRACKER: freeze({"CohesionReason_Independence": -4.0})}},
        records_before=(executive(BEFORE, "25", "Politics", "2030-01-10T00:00:00"),),
        records_after=(executive(AFTER, "25", "Independence", "2031-04-20T00:00:00"),),
    )


def breakaway_independence() -> Scenario:
    return territory_pair(
        {"40": ("21", "25")},
        kept={"21": ("31",), "25": ()},
        nation_before={"25": {"breakawayParent": nation_ref("21")}},
        nation_after={"25": {"breakawayParent": None}},
    )


def two_nation_unification() -> Scenario:
    """Nations 22 and 23 give their only regions to nation 20."""
    return territory_pair({"42": ("22", "20"), "43": ("23", "20")}, kept={"20": ("30",)})


AMICABLE = (
    {DEMOCRACY_TRACKER: freeze({"DemReason_AmicableRelease": 0.0})},
    {DEMOCRACY_TRACKER: freeze({"DemReason_AmicableRelease": 4.5})},
)
RELEASED = (
    {COHESION_TRACKER: freeze({"CohesionReason_NationReleased": 0.0})},
    {COHESION_TRACKER: freeze({"CohesionReason_NationReleased": 0.2})},
)


def executive_point(save: str) -> EntityState:
    return state(
        EntityDomain.CONTROL_POINT,
        "9",
        save,
        controlPointType="TheParty",
        positionInNation=0,
        faction=faction_ref("15"),
    )


def capital_release() -> Scenario:
    """New nation 25 takes region 40 (its capital) from 21 and region 41 from 22; it carries ``AmicableRelease``,
    nation 21 ``NationReleased``, and faction 15 holds nation 21's executive control point."""
    return territory_pair(
        {"40": ("21", "25"), "41": ("22", "25")},
        kept={"21": ("31",), "22": ("32",), "25": ()},
        nation_before={"25": AMICABLE[0], "21": {**RELEASED[0], "controlPoints": (point_ref("9"),)}},
        nation_after={
            "25": {**AMICABLE[1], "capital": region_ref("40")},
            "21": {**RELEASED[1], "controlPoints": (point_ref("9"),)},
        },
        extra_before=(executive_point(BEFORE),),
        extra_after=(executive_point(AFTER),),
    )


def single_parent_release() -> Scenario:
    """Nation 25 takes region 40 from 21 under ``AmicableRelease`` alone; no capital, no executive point."""
    return territory_pair(
        {"40": ("21", "25")},
        kept={"21": ("31",), "25": ()},
        nation_before={"25": AMICABLE[0]},
        nation_after={"25": AMICABLE[1]},
    )


def unattributed_release() -> Scenario:
    """Nation 25 takes regions from 21 and 22 under ``AmicableRelease``; its capital is a region it already held."""
    return territory_pair(
        {"40": ("21", "25"), "41": ("22", "25")},
        kept={"21": ("31",), "22": ("32",), "25": ("35",)},
        nation_before={"25": {**AMICABLE[0], "capital": region_ref("35")}},
        nation_after={"25": {**AMICABLE[1], "capital": region_ref("35")}},
    )


def last_region_release() -> Scenario:
    """Nation 22 releases its only region to nation 20: a release, not a unification."""
    return territory_pair(
        {"42": ("22", "20")},
        kept={"20": ("30",)},
        nation_before={"20": AMICABLE[0], "22": RELEASED[0]},
        nation_after={"20": AMICABLE[1], "22": RELEASED[1]},
    )


def single_whole_loser() -> Scenario:
    return territory_pair({"42": ("22", "20")}, kept={"20": ("30",)})


def flagged_annexation() -> Scenario:
    return territory_pair(
        {"40": ("21", "20")},
        kept={"20": ("30",), "21": ("31",)},
        region_before={"40": {"isBeingAnnexed": True}},
        region_after={"40": {"isBeingAnnexed": False}},
    )


def war_annexation() -> Scenario:
    return territory_pair(
        {"40": ("21", "20")},
        kept={"20": ("30",), "21": ("31",)},
        extra_after=(war(AFTER, ("20",), ("21",)),),
    )


def ambiguous() -> Scenario:
    """Nations 22 and 23 give their only regions to 20 while region 42's annexation flag clears."""
    return territory_pair(
        {"42": ("22", "20"), "43": ("23", "20")},
        kept={"20": ("30",)},
        region_before={"42": {"isBeingAnnexed": True}},
        region_after={"42": {"isBeingAnnexed": False}},
    )


SCENARIOS: dict[str, Callable[[], Scenario]] = {
    "gdp_territory": gdp_territory,
    "plain_transfer": plain_transfer,
    "small_inequality_tracker": small_inequality_tracker,
    "executive_independence": executive_independence,
    "breakaway_independence": breakaway_independence,
    "unification": two_nation_unification,
    "capital_release": capital_release,
    "single_parent_release": single_parent_release,
    "unattributed_release": unattributed_release,
    "last_region_release": last_region_release,
    "single_whole_loser": single_whole_loser,
    "flagged_annexation": flagged_annexation,
    "war_annexation": war_annexation,
    "ambiguous": ambiguous,
}


# --- Territory gained and lost ----------------------------------------------------------------------------


def test_a_transfer_with_a_territory_cause_is_gained_with_high_confidence_and_cites_the_shift() -> None:
    objective, inferred = run(gdp_territory())
    gained = only(inferred, TERRITORY_GAINED)
    assert gained.id == "nation.territory_gained/nation:20"
    assert (gained.status, gained.confidence) == (EventStatus.INFERRED, Confidence.HIGH)
    assert gained.date_basis is DateBasis.INTERVAL
    assert ids(gained.attribute("regions")) == ["region:40", "region:41"]
    assert ids(gained.attribute("counterparts")) == ["nation:21"]
    assert gained.attribute("region_count") == 2
    assert gained.attribute("territory_causes") == ("GDPReason_TerritoryChange",)
    assert set(gained.constituents) == {
        "region.nation_changed/region:40",
        "region.nation_changed/region:41",
        "nation.statistic_shifted/nation:20/GDP",
    }
    primary_fields = {(s.change.entity_id, s.change.field) for s in gained.sources if s.role is SourceRole.PRIMARY}
    assert {str(entity) for entity, field in primary_fields if field == "nation"} == {"region:40", "region:41"}
    lost = only(inferred, TERRITORY_LOST)
    assert lost.id == "nation.territory_lost/nation:21" and lost.confidence is Confidence.MEDIUM
    assert ids(lost.attribute("counterparts")) == ["nation:20"] and lost.attribute("territory_causes") == ()
    assert not [event for event in inferred if event.event_type not in (TERRITORY_GAINED, TERRITORY_LOST)]


def test_region_events_alone_give_medium_confidence() -> None:
    _, inferred = run(plain_transfer())
    assert only(inferred, TERRITORY_GAINED).confidence is Confidence.MEDIUM
    assert only(inferred, TERRITORY_LOST).confidence is Confidence.MEDIUM


def test_territory_events_carry_the_population_of_the_moved_regions_on_the_holding_side() -> None:
    scenario = territory_pair(
        {"40": ("21", "20"), "41": ("21", "20")},
        kept={"21": ("42",)},
        region_before={"40": {"populationInMillions": 3.0}, "41": {"populationInMillions": 4.5}},
        region_after={"40": {"populationInMillions": 3.5}, "41": {"populationInMillions": 4.5}},
    )
    _, inferred = run(scenario)
    assert only(inferred, TERRITORY_GAINED).attribute("population") == 8.0  # after the interval
    assert only(inferred, TERRITORY_LOST).attribute("population") == 7.5  # before it
    _, inferred = run(plain_transfer())
    assert isinstance(only(inferred, TERRITORY_GAINED).attribute("population"), Unknown)  # no population field


def test_a_tracker_change_below_the_statistic_threshold_is_cited_directly() -> None:
    objective, inferred = run(small_inequality_tracker())
    assert not by_type(list(objective), "nation.statistic_shifted")
    gained = only(inferred, TERRITORY_GAINED)
    assert gained.confidence is Confidence.HIGH
    assert gained.attribute("territory_causes") == ("InqReason_Annexation",)
    assert gained.constituents == ("region.nation_changed/region:40",)
    assert (INEQUALITY_TRACKER, SourceRole.CORROBORATING) in {(s.change.field, s.role) for s in gained.sources}


# --- Independence -----------------------------------------------------------------------------------------


def test_an_independence_executive_cause_with_a_tracker_cause_is_high() -> None:
    _, inferred = run(executive_independence())
    event = only(inferred, INDEPENDENCE)
    assert event.id == "nation.independence/nation:25" and event.confidence is Confidence.HIGH
    assert ids(event.attribute("parents")) == ["nation:21"]
    assert event.attribute("signals") == ("executive_cause", "tracker_cause")
    assert event.attribute("independence_causes") == ("CohesionReason_Independence",)
    assert set(event.constituents) == {
        "region.nation_changed/region:40",
        "nation.executive_change_recorded/nation:25",
        "nation.statistic_shifted/nation:25/cohesion",
    }
    assert [str(ref.entity_id) for ref in event.entities] == ["nation:25", "nation:21"]
    assert not by_type(inferred, UNIFICATION) and not by_type(inferred, ANNEXATION)


def test_a_breakaway_parent_change_alone_is_medium() -> None:
    _, inferred = run(breakaway_independence())
    event = only(inferred, INDEPENDENCE)
    assert event.confidence is Confidence.MEDIUM and event.attribute("signals") == ("breakaway_parent",)
    assert "nation.breakaway_parent_changed/nation:25" in event.constituents
    assert event.attribute("released") is False and isinstance(event.attribute("releasing_nation"), Unknown)


def test_a_release_names_the_earlier_holder_of_the_capital_and_its_executive_faction() -> None:
    _, inferred = run(capital_release())
    event = only(inferred, INDEPENDENCE)
    assert event.confidence is Confidence.HIGH
    assert event.attribute("signals") == ("amicable_release", "nation_released")
    assert event.attribute("released") is True
    assert event.attribute("release_causes") == ("CohesionReason_NationReleased", "DemReason_AmicableRelease")
    assert ids(event.attribute("parents")) == ["nation:21", "nation:22"]
    releaser = event.attribute("releasing_nation")
    assert isinstance(releaser, EntityRef) and str(releaser.entity_id) == "nation:21"
    assert event.attribute("releasing_basis") == "capital"
    faction = event.attribute("releasing_executive_faction")
    assert isinstance(faction, EntityRef) and str(faction.entity_id) == "faction:15"
    cited = {(str(s.change.entity_id), s.change.field) for s in event.sources}
    assert {("nation:25", DEMOCRACY_TRACKER), ("nation:21", COHESION_TRACKER)} <= cited
    assert describe_event(event) == "Fixture nation 25 (nation:25) was released by Fixture nation 21 (nation:21)"


def test_a_parents_release_reason_is_not_attributed_when_it_lost_regions_to_several_nations() -> None:
    scenario = territory_pair(
        {"40": ("21", "25"), "41": ("21", "26")},
        kept={"21": ("31",), "25": (), "26": ()},
        nation_before={"21": RELEASED[0]},
        nation_after={"21": RELEASED[1]},
    )
    _, inferred = run(scenario)
    assert not by_type(inferred, INDEPENDENCE)


def test_a_release_from_one_parent_without_a_moved_capital_names_that_parent() -> None:
    _, inferred = run(single_parent_release())
    event = only(inferred, INDEPENDENCE)
    assert event.confidence is Confidence.MEDIUM and event.attribute("signals") == ("amicable_release",)
    assert event.attribute("releasing_basis") == "only_parent"
    assert isinstance(event.attribute("releasing_executive_faction"), Unknown)  # the parent has no executive point


def test_a_release_from_several_parents_without_a_moved_capital_names_no_releaser() -> None:
    _, inferred = run(unattributed_release())
    event = only(inferred, INDEPENDENCE)
    assert event.attribute("released") is True
    assert event.attribute("releasing_nation") is None and event.attribute("releasing_basis") is None
    assert (
        describe_event(event) == "Fixture nation 25 (nation:25) became independent of Fixture nation 21 (nation:21), "
        "Fixture nation 22 (nation:22)"
    )


# --- Unification ------------------------------------------------------------------------------------------


def test_two_nations_giving_every_region_to_one_gainer_is_a_medium_unification() -> None:
    _, inferred = run(two_nation_unification())
    event = only(inferred, UNIFICATION)
    assert event.id == "nation.unification/nation:20" and event.confidence is Confidence.MEDIUM
    assert ids(event.attribute("unified")) == ["nation:22", "nation:23"]
    assert set(event.constituents) == {"region.nation_changed/region:42", "region.nation_changed/region:43"}


def test_one_nation_giving_every_region_is_no_unification() -> None:
    _, inferred = run(single_whole_loser())
    assert sorted(event.event_type for event in inferred) == [TERRITORY_GAINED, TERRITORY_LOST]


def test_a_release_of_a_parents_last_region_is_an_independence_not_a_unification() -> None:
    _, inferred = run(last_region_release())
    assert not by_type(inferred, UNIFICATION)
    event = only(inferred, INDEPENDENCE)
    assert event.attribute("released") is True and event.confidence is Confidence.HIGH


# --- Annexation -------------------------------------------------------------------------------------------


def test_an_annexation_flag_change_on_a_transferred_region_is_a_medium_annexation() -> None:
    _, inferred = run(flagged_annexation())
    event = only(inferred, ANNEXATION)
    assert event.id == "nation.annexation/nation:20/nation:21" and event.confidence is Confidence.MEDIUM
    assert event.attribute("signals") == ("annexation_flags",)
    assert ids(event.attribute("regions")) == ["region:40"]
    assert ("isBeingAnnexed", SourceRole.CORROBORATING) in {(s.change.field, s.role) for s in event.sources}
    assert event.constituents == ("region.nation_changed/region:40",)


def test_a_war_event_between_the_two_nations_is_a_medium_annexation() -> None:
    _, inferred = run(war_annexation())
    event = only(inferred, ANNEXATION)
    assert event.confidence is Confidence.MEDIUM and event.attribute("signals") == ("war",)
    assert "war.appeared/war:60" in event.constituents


def test_a_war_between_other_nations_is_no_evidence() -> None:
    scenario = territory_pair(
        {"40": ("21", "20")},
        kept={"20": ("30",), "21": ("31",)},
        extra_after=(war(AFTER, ("20",), ("22",)),),
    )
    _, inferred = run(scenario)
    assert not by_type(inferred, ANNEXATION)


# --- Ambiguity --------------------------------------------------------------------------------------------


def test_competing_readings_are_both_kept_one_level_lower_and_cross_referenced() -> None:
    _, inferred = run(ambiguous())
    unification = only(inferred, UNIFICATION)
    annexation = only(inferred, ANNEXATION)
    assert unification.confidence is Confidence.LOW and annexation.confidence is Confidence.LOW
    assert unification.attribute("ambiguous") is True and annexation.attribute("ambiguous") is True
    assert unification.attribute("alternatives") == (annexation.id,)
    assert annexation.attribute("alternatives") == (unification.id,)
    assert only(inferred, TERRITORY_GAINED).attribute("ambiguous") is not True


# --- No evidence ------------------------------------------------------------------------------------------


def test_no_region_transfer_infers_nothing() -> None:
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, regions=(region_ref("30"),)))
    after = snapshot(AFTER, state(NATION, "20", AFTER, regions=(region_ref("30"),), capital=region_ref("30")))
    assert run(pair(before, after))[1] == []


def test_a_region_whose_nation_was_null_is_not_a_transfer() -> None:
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, regions=()), state(REGION, "40", BEFORE, nation=None))
    after = snapshot(
        AFTER,
        state(NATION, "20", AFTER, regions=(region_ref("40"),)),
        state(REGION, "40", AFTER, nation=nation_ref("20")),
    )
    objective, inferred = run(pair(before, after))
    assert by_type(list(objective), "region.nation_changed") and inferred == []


# --- Invariants -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_inferred_events_cite_their_constituents_and_trace_to_the_diff(name: str) -> None:
    assert_traceable(SCENARIOS[name]())


def test_inferred_input_events_are_ignored() -> None:
    scenario = ambiguous()
    objective, inferred = run(scenario)
    assert infer_events((*objective, *inferred), *scenario) == inferred


def test_lines_name_the_reading_and_significance_ranks_it() -> None:
    territory = lines_of(gdp_territory())
    assert territory["nation.territory_gained/nation:20"] == (
        "Fixture nation 20 (nation:20) gained 2 regions from Fixture nation 21 (nation:21)",
        Significance.MINOR,
    )
    assert territory["nation.territory_lost/nation:21"] == (
        "Fixture nation 21 (nation:21) lost 2 regions to Fixture nation 20 (nation:20)",
        Significance.MINOR,
    )
    assert lines_of(executive_independence())["nation.independence/nation:25"] == (
        "Fixture nation 25 (nation:25) became independent of Fixture nation 21 (nation:21)",
        Significance.MAJOR,
    )
    assert lines_of(two_nation_unification())["nation.unification/nation:20"] == (
        "Fixture nation 20 (nation:20) unified with Fixture nation 22 (nation:22), Fixture nation 23 (nation:23)",
        Significance.MAJOR,
    )
    assert lines_of(flagged_annexation())["nation.annexation/nation:20/nation:21"] == (
        "Fixture nation 20 (nation:20) annexed 1 region of Fixture nation 21 (nation:21)",
        Significance.MAJOR,
    )
