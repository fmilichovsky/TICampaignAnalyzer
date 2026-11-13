"""Situation reports built from synthetic snapshots: every section, the ``Unknown`` paths and determinism; and the
questions a report answers."""

from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest

from tests.analyzers.support import (
    AFTER,
    AFTER_DATE,
    army_ref,
    faction_ref,
    federation_ref,
    fleet_ref,
    named,
    nation_ref,
    point_ref,
    record_set,
    ref,
    region_ref,
    snapshot,
    state,
    war_ref,
)
from tests.narrative import support
from tests.narrative.support import nation_row, situation, war_row
from tinarrative.analyzers.politics.nation_assets import GDP, STRENGTH
from tinarrative.config import PowerSettings
from tinarrative.model.entities import EntityDomain, EntityRef
from tinarrative.model.records import ItemEntry, KeyedEntry, RecordKind
from tinarrative.model.snapshot import CampaignMetadata, EntityState, ResearchState, SaveSnapshot
from tinarrative.model.values import FrozenMap, Observed, Unknown, UnknownReason
from tinarrative.narrative.situation import (
    BodyHabs,
    Milestone,
    NationSituation,
    SituationReport,
    Unattributed,
    WarParty,
    build_situation,
)

NATION = EntityDomain.NATION
POINT = EntityDomain.CONTROL_POINT
UNRESOLVED = Unknown(UnknownReason.UNRESOLVED_REFERENCE)
GLOBAL = ref(EntityDomain.GLOBAL_VALUES, "9")


def body_ref(key: str) -> EntityRef:
    return ref(EntityDomain.SPACE_BODY, key)


def point(key: str, nation: str, position: int, faction: Observed, kind: str | None = None) -> EntityState:
    fields = {} if kind is None else {"controlPointType": kind}
    return state(POINT, key, AFTER, nation=nation_ref(nation), positionInNation=position, faction=faction, **fields)


def campaign() -> SaveSnapshot:
    states = [
        state(EntityDomain.FACTION, "1", AFTER, templateName="ResistCouncil", finishedProjectNames=("P1", "P1", "P2")),
        state(EntityDomain.FACTION, "2", AFTER, templateName="AlienCouncil"),
        state(EntityDomain.FACTION, "3", AFTER),
        # nation 20: the Executive point (position 2) held by faction 2, position 0 by faction 1, one point uncontrolled
        state(
            NATION,
            "20",
            AFTER,
            controlPoints=tuple(point_ref(key) for key in ("100", "101", "102", "103")),
            federation=federation_ref("60"),
            allies=(nation_ref("21"),),
            regions=(region_ref("40"), region_ref("41")),
            democracy=6.5,
            cohesion=5.0,
            unrest=1.5,
            inequality=0.3,
            GDP=900.0,
        ),
        point("100", "20", 0, faction_ref("1")),
        point("101", "20", 1, faction_ref("1")),
        point("102", "20", 2, faction_ref("2"), "Executive"),
        point("103", "20", 3, None),
        # nation 21: no Executive point, so position 0 stands in and its controller is unresolved; no regions field
        state(NATION, "21", AFTER, controlPoints=(point_ref("104"),), federation=None),
        point("104", "21", 0, UNRESOLVED),
        # nation 22: a known empty point list
        state(NATION, "22", AFTER, controlPoints=(), regions=()),
        # nation 23: no point list; nation 24: no point at position 0
        state(NATION, "23", AFTER),
        state(NATION, "24", AFTER, controlPoints=(point_ref("105"),)),
        point("105", "24", 1, faction_ref("2")),
        state(EntityDomain.REGION, "40", AFTER, populationInMillions=10.5),
        state(EntityDomain.REGION, "41", AFTER, populationInMillions=4.5),
        state(EntityDomain.REGION, "42", AFTER, populationInMillions=1.0),
        state(
            EntityDomain.WAR,
            "50",
            AFTER,
            attacker=nation_ref("20"),
            defender=nation_ref("21"),
            _attackingAlliance=(nation_ref("20"),),
            _defendingAlliance=(nation_ref("21"), nation_ref("22")),
        ),
        state(EntityDomain.FEDERATION, "60", AFTER, federationName="Fixture Union", members=(nation_ref("20"),)),
        state(EntityDomain.SPACE_BODY, "70", AFTER),
        state(EntityDomain.SPACE_BODY, "71", AFTER),
        state(EntityDomain.SPACE_OBJECT, "80", AFTER, faction=faction_ref("1"), barycenter=body_ref("70")),
        state(EntityDomain.SPACE_OBJECT, "81", AFTER, faction=faction_ref("1"), barycenter=body_ref("70")),
        state(EntityDomain.SPACE_OBJECT, "82", AFTER, faction=faction_ref("1"), barycenter=None),
        state(EntityDomain.SPACE_OBJECT, "83", AFTER, faction=None, barycenter=body_ref("70")),
        state(EntityDomain.SPACE_OBJECT, "84", AFTER, faction=faction_ref("2"), barycenter=body_ref("71")),
        state(EntityDomain.FLEET, "90", AFTER, faction=faction_ref("1")),
        state(EntityDomain.FLEET, "91", AFTER, faction=UNRESOLVED),
        state(EntityDomain.SHIP, "95", AFTER, fleet=fleet_ref("90")),
        state(EntityDomain.SHIP, "96", AFTER, fleet=fleet_ref("90")),
        state(EntityDomain.SHIP, "97", AFTER, fleet=fleet_ref("91")),
        state(EntityDomain.SHIP, "98", AFTER, fleet=UNRESOLVED),
        state(EntityDomain.GLOBAL_VALUES, "9", AFTER, nuclearStrikes=2, looseNukes=0, earthAtmosphericCO2_ppm=420.5),
    ]
    records = (
        record_set(AFTER, war_ref("50"), "startDate", RecordKind.DATE, (ItemEntry(0, "2031-01-15T00:00:00"),)),
        record_set(
            AFTER,
            GLOBAL,
            "globalMilestones",
            RecordKind.LABELLED_REFERENCES,
            (KeyedEntry(1, "SecondMilestone", faction_ref("2")), KeyedEntry(0, "FirstMilestone", faction_ref("1"))),
        ),
    )
    built = snapshot(AFTER, *states, records=records)
    return replace(
        built,
        campaign=CampaignMetadata(player_faction_name="Fixture Resistance"),
        research=ResearchState(finished_techs_names=("TechA", "TechB", "TechC")),
    )


def nation(report: SituationReport, key: str) -> NationSituation:
    return next(item for item in report.nations if item.nation.entity_id.key == key)


def test_a_nation_reports_its_executive_holder_and_point_shares() -> None:
    report = build_situation(campaign())

    northland = nation(report, "20")
    assert northland.executive == named(faction_ref("2"))  # the Executive point, not the position-0 one
    assert northland.seat_basis == "executive_point"
    assert northland.control_points == 4
    assert northland.shares == FrozenMap((("faction:1", 2), ("faction:2", 1)))
    assert northland.unresolved_points == 0
    assert northland.federation == named(federation_ref("60"))
    assert northland.allies == (named(nation_ref("21")),)
    assert northland.regions == 2
    assert northland.population == 15.0
    assert dict(northland.statistics) == {
        "democracy": 6.5,
        "cohesion": 5.0,
        "unrest": 1.5,
        "inequality": 0.3,
        "education": Unknown(),
        "militaryTechLevel": Unknown(),
        "GDP": 900.0,
        "spaceFunding_year": Unknown(),
    }


def test_the_full_report_carries_allies_and_default_values() -> None:
    report = build_situation(campaign())

    entry = nation(report, "20").to_dict()
    assert [ally["ref"] for ally in entry["allies"]] == ["nation:21"]
    assert {"alien", "wars", "federation"} <= set(nation(report, "21").to_dict())


def test_a_nation_reports_whether_it_is_the_alien_administration() -> None:
    states = [state(NATION, "30", AFTER, alienNation=True), state(NATION, "31", AFTER, alienNation=False)]
    report = build_situation(snapshot(AFTER, *states))

    assert (nation(report, "30").alien, nation(report, "31").alien) == (True, False)
    assert nation(report, "30").to_dict()["alien"] is True
    assert nation(build_situation(campaign()), "20").alien is False


def test_unknown_control_and_regions_stay_unknown() -> None:
    report = build_situation(campaign())

    southland = nation(report, "21")
    assert southland.executive == UNRESOLVED
    assert southland.seat_basis == "position_0"
    assert (southland.control_points, southland.unresolved_points, southland.shares) == (1, 1, FrozenMap())
    assert southland.federation is None
    assert southland.allies == Unknown()
    assert (southland.regions, southland.population) == (Unknown(), Unknown())

    empty = nation(report, "22")
    assert (empty.executive, empty.control_points, empty.shares) == (None, 0, FrozenMap())
    assert empty.seat_basis is None
    assert (empty.regions, empty.population) == (0, 0.0)

    unlisted = nation(report, "23")
    assert unlisted.executive == unlisted.control_points == unlisted.shares == unlisted.unresolved_points == Unknown()
    assert unlisted.federation == Unknown()

    seatless = nation(report, "24")
    assert seatless.executive == Unknown()
    assert seatless.shares == FrozenMap((("faction:2", 1),))


def test_wars_list_both_sides_and_their_dates() -> None:
    report = build_situation(campaign())

    (war,) = report.wars
    assert (war.attacker, war.defender) == (named(nation_ref("20")), named(nation_ref("21")))
    assert war.attacking_alliance == (named(nation_ref("20")),)
    assert war.defending_alliance == (named(nation_ref("21")), named(nation_ref("22")))
    assert war.start_date == "2031-01-15T00:00:00"
    assert war.last_fighting == Unknown()
    own = named(war_ref("50"))
    assert nation(report, "20").wars == (WarParty(own, "attacker"),)
    assert nation(report, "22").wars == (WarParty(own, "defender"),)
    assert nation(report, "23").wars == ()


def test_federations_list_their_members() -> None:
    (federation,) = build_situation(campaign()).federations

    assert federation.name == "Fixture Union"
    assert federation.members == (named(nation_ref("20")),)


def test_factions_count_habs_per_body_fleets_ships_and_projects() -> None:
    report = build_situation(campaign())

    resistance, aliens, unnamed = report.factions
    assert (resistance.kind, aliens.kind, unnamed.kind) == ("human", "alien", None)
    assert resistance.habs == 3
    assert resistance.habs_by_body == (BodyHabs(named(body_ref("70")), 2),)
    assert (resistance.fleets, resistance.ships, resistance.finished_projects) == (1, 2, 3)
    assert aliens.habs_by_body == (BodyHabs(named(body_ref("71")), 1),)
    assert aliens.finished_projects == Unknown()
    assert (unnamed.habs, unnamed.fleets, unnamed.ships) == (0, 0, 0)
    assert report.unattributed == Unattributed(habs=1, fleets=1, ships=2)


def test_world_counters_milestones_and_player() -> None:
    report = build_situation(campaign())

    assert report.date == AFTER_DATE
    assert report.player_faction_name == "Fixture Resistance"
    world = report.world
    assert (world.nations, world.nations_with_regions) == (5, Unknown())  # nation 21 has no regions field
    assert (world.population, world.finished_technologies) == (16.0, 3)
    assert world.milestones == (
        Milestone("FirstMilestone", named(faction_ref("1"))),
        Milestone("SecondMilestone", named(faction_ref("2"))),
    )
    assert dict(world.nuclear) == {"nuclearStrikes": 2, "looseNukes": 0, "currentNuclearExchanges": Unknown()}
    assert dict(world.climate)["earthAtmosphericCO2_ppm"] == 420.5
    assert dict(world.climate)["globalSeaLevelRise1Triggered"] == Unknown()


def test_an_empty_snapshot_reports_unknown_never_zero() -> None:
    report = build_situation(snapshot(AFTER))

    assert report.player_faction_name == Unknown()
    assert (report.nations, report.federations, report.wars, report.factions) == ((), (), (), ())
    world = report.world
    assert (world.nations, world.nations_with_regions) == (0, 0)
    assert world.population == world.finished_technologies == world.milestones == Unknown()
    assert all(value == Unknown() for _, value in world.nuclear + world.climate)
    assert report.to_dict()["world"]["milestones"] == {"unknown": "missing"}


def test_nations_with_regions_counts_known_non_empty_lists() -> None:
    states = (
        state(NATION, "20", AFTER, regions=(region_ref("40"),)),
        state(NATION, "21", AFTER, regions=()),
        state(EntityDomain.REGION, "40", AFTER, populationInMillions=1.0),
    )

    assert build_situation(snapshot(AFTER, *states)).world.nations_with_regions == 1


def test_a_nation_reports_its_armies_strength_and_space_assets_and_the_world_its_spaceports() -> None:
    def region(key: str, owner: str, boost: float, **fields: Observed) -> EntityState:
        values: dict[str, Observed] = {
            "nation": nation_ref(owner),
            "boostPerYear_dekatons": boost,
            "missionControl": 3,
            "antiSpaceDefenses": False,
            "numSTOFighters": 0,
            "leadOccupier": None,
            "occupations": FrozenMap(),
        }
        return state(EntityDomain.REGION, key, AFTER, **{**values, **fields})

    states = (
        state(
            NATION,
            "20",
            AFTER,
            regions=(region_ref("40"), region_ref("41")),
            armies=(army_ref("110"), army_ref("111")),
            militaryTechLevel=2.0,
            unrest=1.0,
            numNuclearWeapons=1,
        ),
        state(NATION, "21", AFTER, regions=(region_ref("42"),)),
        region("40", "20", 30.0, antiSpaceDefenses=True, numSTOFighters=2),
        region("41", "20", 0.0),
        region("42", "21", 50.0),
        state(EntityDomain.ARMY, "110", AFTER, deploymentType="Standard", strength=1.0),
        state(EntityDomain.ARMY, "111", AFTER, deploymentType="Naval", strength=1.0),
    )

    report = build_situation(snapshot(AFTER, *states), spaceports=1)

    northland = nation(report, "20")
    assert (northland.armies, northland.navies, northland.boost, northland.mission_control) == (1, 1, 30.0, 6.0)
    assert (northland.space_defence_regions, northland.sto_fighters) == (1, 2.0)
    # 2 regions x 2 x 0.7 + 1 army x 2 x 3 x 1.0 + 1 navy - 1 unrest + 100 + 5
    assert northland.strength == 2.8 + 6.0 + 1.0 - 1.0 + 105.0
    assert nation(report, "21").strength == Unknown(UnknownReason.MISSING)  # no military tech, unrest or weapons
    (spaceport,) = report.world.spaceports
    assert (spaceport.region, spaceport.nation, spaceport.boost) == (
        named(region_ref("42")),
        named(nation_ref("21")),
        50.0,
    )
    assert list(report.to_dict()["world"]["spaceports"][0]) == ["region", "nation", "boost"]


def test_a_nation_reports_its_nuclear_warheads_and_an_absent_count_stays_unknown_not_zero() -> None:
    states = (
        state(NATION, "20", AFTER, numNuclearWeapons=3),
        state(NATION, "21", AFTER, numNuclearWeapons=0),
        state(NATION, "22", AFTER),
    )

    report = build_situation(snapshot(AFTER, *states))

    assert nation(report, "20").nuclear_weapons == 3
    assert nation(report, "21").nuclear_weapons == 0
    assert nation(report, "22").nuclear_weapons == Unknown(UnknownReason.MISSING)


def test_an_unparseable_milestone_record_stays_unknown() -> None:
    entries = Unknown(UnknownReason.UNPARSEABLE, "raw")
    broken = record_set(AFTER, GLOBAL, "globalMilestones", RecordKind.LABELLED_REFERENCES, entries)
    globals_state = state(EntityDomain.GLOBAL_VALUES, "9", AFTER)

    report = build_situation(snapshot(AFTER, globals_state, records=(broken,)))

    assert report.world.milestones == entries


def test_two_builds_are_identical_and_serialize_to_json() -> None:
    built = campaign()
    shuffled = replace(built, nations=tuple(reversed(built.nations)), habs=tuple(reversed(built.habs)))

    first, second = build_situation(built), build_situation(shuffled)

    assert first == second
    rendered = json.dumps(first.to_dict(), sort_keys=False)
    assert rendered == json.dumps(second.to_dict(), sort_keys=False)
    document = json.loads(rendered)
    assert list(document) == [
        "date",
        "player_faction_name",
        "nations",
        "federations",
        "wars",
        "factions",
        "unattributed",
        "world",
    ]
    northland = document["nations"][0]
    assert northland["executive"]["ref"] == "faction:2" and northland["seat_basis"] == "executive_point"
    assert northland["shares"] == {"faction:1": 2, "faction:2": 1}
    assert northland["wars"] == [{"war": document["wars"][0]["war"], "side": "attacker"}]
    assert document["nations"][3]["control_points"] == {"unknown": "missing"}
    assert document["factions"][0]["habs_by_body"][0]["habs"] == 2


# --- Questions ---------------------------------------------------------------------------------------------------

NORTH, SOUTH, EAST, WEST = (support.nation(key) for key in ("20", "21", "22", "23"))
LANDED = 3


def ranked(*rows: NationSituation) -> SituationReport:
    return situation("2032-01-01T00:00:00", nations=rows)


def test_a_report_finds_a_nation_row_by_id() -> None:
    report = ranked(nation_row(NORTH), nation_row(SOUTH))

    assert report.nation(SOUTH.entity_id) == report.nations[1]
    assert report.nation(EAST.entity_id) is None


def test_rank_orders_landed_nations_by_value_with_ties_by_id() -> None:
    report = ranked(
        nation_row(SOUTH, gdp=500.0, regions=LANDED),
        nation_row(NORTH, gdp=500.0, regions=LANDED),
        nation_row(EAST, gdp=900.0, regions=0),
        nation_row(WEST, regions=LANDED),
    )

    assert [report.rank(item.entity_id, GDP) for item in (NORTH, SOUTH, EAST, WEST)] == [1, 2, None, None]


def test_a_nation_without_land_is_not_ranked_by_strength_either() -> None:
    report = ranked(
        nation_row(SOUTH, strength=5.0, regions=LANDED),
        nation_row(NORTH, strength=5.0, regions=LANDED),
        nation_row(EAST, strength=9.0, regions=0),
        nation_row(WEST, regions=LANDED),
    )

    assert [report.rank(item.entity_id, STRENGTH) for item in (NORTH, SOUTH, EAST, WEST)] == [1, 2, None, None]


def test_the_top_leaves_out_a_tie_across_the_boundary_and_a_zero_value() -> None:
    report = ranked(
        nation_row(NORTH, gdp=900.0, regions=LANDED),
        nation_row(SOUTH, gdp=500.0, regions=LANDED),
        nation_row(EAST, gdp=500.0, regions=LANDED),
        nation_row(WEST, gdp=0.0, regions=LANDED),
    )

    assert list(report.top(GDP, 2)) == [NORTH.entity_id]
    assert {key: place.rank for key, place in report.top(GDP, 3).items()} == {
        NORTH.entity_id: 1,
        SOUTH.entity_id: 2,
        EAST.entity_id: 3,
    }
    assert WEST.entity_id not in report.top(GDP, 4)


def test_opposed_wars_are_the_wars_two_nations_fight_on_opposite_sides() -> None:
    against = war_row(support.war("1"), [NORTH], [SOUTH, EAST])
    together = war_row(support.war("2"), [NORTH, SOUTH], [WEST])
    report = situation("2032-01-01T00:00:00", wars=[against, together])

    assert report.opposed_wars(SOUTH.entity_id, NORTH.entity_id) == (against,)
    assert report.opposed_wars(SOUTH.entity_id, EAST.entity_id) == ()


def test_power_shares_of_the_landed_nations_sum_to_one() -> None:
    def row(item: EntityRef, gdp: float, population: float, strength: float, regions: int) -> NationSituation:
        return replace(nation_row(item, gdp=gdp, strength=strength, regions=regions), population=population)

    report = ranked(
        row(NORTH, 900.0, 300.0, 40.0, LANDED),
        row(SOUTH, 400.0, 800.0, 10.0, LANDED),
        row(EAST, 999.0, 999.0, 99.0, 0),
    )

    shares = report.power_shares(PowerSettings())

    assert set(shares) == {NORTH.entity_id, SOUTH.entity_id}
    assert math.fsum(shares.values()) == pytest.approx(1.0)
