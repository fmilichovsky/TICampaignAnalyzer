"""Situation reports built from synthetic snapshots: every section, the ``Unknown`` paths and determinism."""

from __future__ import annotations

import json
from dataclasses import replace

from tests.analyzers.support import (
    AFTER,
    AFTER_DATE,
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
        "GDP": 900.0,
        "spaceFunding_year": Unknown(),
    }


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
