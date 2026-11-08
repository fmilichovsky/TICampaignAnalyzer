"""The space narrative rules over synthetic qualified streams."""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import replace

from tests.narrative.support import atomic, faction, ref, situation
from tinarrative.analyzers.render import describe_event
from tinarrative.config import NarrativeSettings, SpaceSettings
from tinarrative.model.entities import EntityDomain, EntityRef
from tinarrative.model.events import DateBasis, Event, EventStatus, Role, Significance
from tinarrative.model.values import FrozenMap, Observed
from tinarrative.narrative import NARRATIVE_RULES, aggregate, narrative_rules
from tinarrative.narrative.milestones import MILESTONE_TEMPLATES
from tinarrative.narrative.situation import SituationReport

K0 = "2032-01-01T00:00:00"
K1 = "2032-04-01T00:00:00"
K2 = "2032-07-01T00:00:00"
K3 = "2034-07-01T00:00:00"
K4 = "2036-07-01T00:00:00"
PREVIOUS = {K1: K0, K2: K1, K3: K2, K4: K3}
UNION = faction("15", "Union")
ALIENS = faction("16", "Aliens")
ACADEMY = faction("17", "Academy")
LUNA = ref(EntityDomain.SPACE_BODY, "1", "Luna")
MARS = ref(EntityDomain.SPACE_BODY, "2", "Mars")
CERES = ref(EntityDomain.SPACE_BODY, "3", "Ceres")
FLEET = ref(EntityDomain.FLEET, "50")


def make(
    raw_id: str,
    key: str,
    entities: Sequence[EntityRef] = (),
    attributes: Sequence[tuple[str, Observed]] = (),
    status: EventStatus = EventStatus.INFERRED,
    **overrides: object,
) -> Event:
    return atomic(
        raw_id,
        key,
        not_before=PREVIOUS[key],
        entities=entities,
        attributes=attributes,
        status=status,
        **overrides,  # type: ignore[arg-type]
    )


def outcome(
    key: str, killer: EntityRef = UNION, victim: EntityRef = ALIENS, constituents: Sequence[Event] = (), **counts: int
) -> Event:
    values = {"habs_lost": 0, "fleets_lost": 1, "combats_won": 1, "combats_lost": 0, **counts}
    return replace(
        make(
            f"faction.battle_outcome/{killer.entity_id}/{victim.entity_id}",
            key,
            [killer, victim],
            [("victim", victim), ("faction_kinds", FrozenMap(((str(victim.entity_id), "alien"),))), *values.items()],
        ),
        constituents=tuple(event.id for event in constituents),
    )


def combat(key: str, number: int, *sides: EntityRef) -> Event:
    return make(
        f"faction.combat_recorded/{number}",
        key,
        sides,
        [("sides", tuple((side, "") for side in sides))],
    )


def first_hab(key: str, body: EntityRef, owner: EntityRef = UNION, first: bool = False) -> Event:
    return make(
        f"faction.first_hab_on_body/{owner.entity_id}/{body.entity_id}",
        key,
        [owner, body],
        [("body", body), ("habs", ()), ("hab_count", 1), ("first_of_any_faction", first)],
    )


def ship(key: str, number: int, hull: str | None = "Frigate", owner: EntityRef = UNION) -> Event:
    attributes = [("side", "after")] + ([("hull", hull)] if hull else [])
    return make(f"ship.appeared/ship:{number}", key, [ref(EntityDomain.SHIP, str(number)), FLEET, owner], attributes)


def charge(key: str, holder: EntityRef, label: str, date: str) -> Event:
    return make(
        f"faction.transaction_recorded/{holder.entity_id}/{label}",
        key,
        [holder],
        [("label", label), ("recorded_on", date)],
        EventStatus.OBJECTIVE,
        date=date,
        date_basis=DateBasis.RECORD,
    )


def plain(*keys: str) -> list[SituationReport]:
    return [situation(key) for key in keys]


def built(stream: Sequence[Event], situations: Sequence[SituationReport] | None = None, **settings: int) -> list[Event]:
    rules = narrative_rules(NarrativeSettings(space=SpaceSettings(**settings))) if settings else NARRATIVE_RULES
    return aggregate(stream, situations or plain(K0, K1, K2, K3, K4), rules)


def of_type(events: Sequence[Event], event_type: str) -> list[Event]:
    return [item for item in events if item.event_type == event_type]


# --- faction.space_campaign --------------------------------------------------------------------------------------


def test_outcomes_of_one_pair_form_a_campaign_with_summed_counts() -> None:
    habs = make(
        "hab.destroyed/hab:9",
        K2,
        [ref(EntityDomain.SPACE_OBJECT, "9"), ALIENS, LUNA, UNION],
        [("body", LUNA), ("ambiguous", False)],
    )
    lost_fleet = make("fleet.disappeared/fleet:50", K1, [FLEET, ALIENS], [("side", "before")])
    stream = [outcome(K1, habs_lost=1), outcome(K2, habs_lost=2, fleets_lost=0), habs, lost_fleet]

    [campaign] = of_type(built(stream), "faction.space_campaign")

    assert campaign.attribute("battles") == 2
    assert campaign.attribute("habs_lost") == 3
    assert campaign.attribute("fleets_lost") == 1
    assert campaign.attribute("combats_won") == 2
    assert campaign.attribute("victim_kind") == "alien"
    assert campaign.attribute("bodies") == (LUNA,)
    assert [(role, ref_.entity_id.key) for role, ref_ in campaign.roles] == [
        (Role.ACTOR, "15"),
        (Role.TARGET, "16"),
        (Role.BODY, "1"),
    ]
    assert campaign.significance is Significance.MAJOR
    assert habs.id in campaign.constituents and lost_fleet.id in campaign.constituents
    assert "Luna" in describe_event(campaign) and "the aliens" in describe_event(campaign)


def test_bodies_include_habs_known_only_through_a_destruction_entry() -> None:
    direct = make(
        "hab.destroyed/hab:9",
        K1,
        [ref(EntityDomain.SPACE_OBJECT, "9"), ALIENS, LUNA, UNION],
        [("body", LUNA), ("ambiguous", False)],
    )
    entry = make(
        "faction.hab_destruction_recorded/16/0",
        K1,
        [ALIENS, MARS, UNION],
        [("space_body", MARS), ("destroyer", UNION)],
    )

    [campaign] = of_type(
        built([outcome(K1, habs_lost=2, constituents=[entry]), direct, entry]), "faction.space_campaign"
    )

    assert campaign.attribute("bodies") == (LUNA, MARS)
    assert [ref_.entity_id.key for role, ref_ in campaign.roles if role is Role.BODY] == ["1", "2"]
    assert entry.id in campaign.constituents


def test_the_two_campaigns_of_a_pair_name_each_other() -> None:
    shared = combat(K1, 1, UNION, ALIENS)
    forward = outcome(K1, UNION, ALIENS)
    backward = outcome(K1, ALIENS, UNION, fleets_lost=0, combats_won=0, combats_lost=1)
    third = outcome(K1, ACADEMY, ALIENS)

    campaigns = {
        (c.roles[0][1].entity_id.key, c.roles[1][1].entity_id.key): c
        for c in of_type(built([forward, backward, third, shared]), "faction.space_campaign")
    }

    assert campaigns[("15", "16")].attribute("mirror") == campaigns[("16", "15")].id
    assert campaigns[("16", "15")].attribute("mirror") == campaigns[("15", "16")].id
    assert "mirror" not in dict(campaigns[("17", "16")].attributes)


def test_a_gap_beyond_the_campaign_window_splits_the_campaign() -> None:
    campaigns = of_type(built([outcome(K1), outcome(K4)]), "faction.space_campaign")

    assert len(campaigns) == 2


def test_other_pairs_and_ambiguous_destructions_are_not_attached() -> None:
    other = make(
        "hab.destroyed/hab:8",
        K1,
        [ref(EntityDomain.SPACE_OBJECT, "8"), ALIENS, LUNA, ACADEMY],
        [("body", LUNA), ("ambiguous", False)],
    )
    unsure = make(
        "hab.destroyed/hab:7", K1, [ref(EntityDomain.SPACE_OBJECT, "7"), ALIENS, LUNA, UNION], [("ambiguous", True)]
    )

    [campaign] = of_type(built([outcome(K1), other, unsure]), "faction.space_campaign")

    assert campaign.constituents == (outcome(K1).id,)


def test_no_campaign_without_an_outcome() -> None:
    habs = make(
        "hab.destroyed/hab:9", K1, [ref(EntityDomain.SPACE_OBJECT, "9"), ALIENS, LUNA, UNION], [("ambiguous", False)]
    )

    assert of_type(built([habs]), "faction.space_campaign") == []


# --- faction.colonisation_wave -----------------------------------------------------------------------------------


def test_two_bodies_within_the_window_are_a_wave() -> None:
    stream = [first_hab(K1, LUNA, first=True), first_hab(K2, MARS)]

    [wave] = of_type(built(stream), "faction.colonisation_wave")

    assert wave.attribute("bodies") == (LUNA, MARS)
    assert wave.attribute("hab_count") == 2
    assert wave.attribute("first_of_any_faction") == (True, False)
    assert "Luna" in describe_event(wave) and "Mars" in describe_event(wave)


def test_a_wave_attaches_the_establishment_of_its_habs_not_their_launch() -> None:
    luna_hab, mars_hab = ref(EntityDomain.SPACE_OBJECT, "60"), ref(EntityDomain.SPACE_OBJECT, "61")
    stream = [
        replace(first_hab(K1, LUNA), attributes=(("body", LUNA), ("habs", (luna_hab,)), ("hab_count", 1))),
        replace(first_hab(K2, MARS), attributes=(("body", MARS), ("habs", (mars_hab,)), ("hab_count", 1))),
        make("hab.established/space object:60", K1, [luna_hab, UNION, LUNA]),
        make("hab.established/space object:61", K2, [mars_hab, UNION, MARS]),
        make("hab.appeared/space object:61", K1, [mars_hab, UNION], status=EventStatus.OBJECTIVE),
    ]

    [wave] = of_type(built(stream), "faction.colonisation_wave")

    attached = [event_id for event_id in wave.constituents if event_id.startswith("hab.")]
    assert sorted(attached) == [
        f"hab.established/space object:60@{K1}",
        f"hab.established/space object:61@{K2}",
    ]


def test_a_single_body_or_a_distant_second_is_no_wave() -> None:
    assert of_type(built([first_hab(K1, LUNA)]), "faction.colonisation_wave") == []
    assert of_type(built([first_hab(K1, LUNA), first_hab(K4, MARS)]), "faction.colonisation_wave") == []


def test_the_wave_window_is_configurable() -> None:
    stream = [first_hab(K1, LUNA), first_hab(K4, MARS)]

    assert len(of_type(built(stream, colonisation_window_days=2000), "faction.colonisation_wave")) == 1


# --- campaign.first_milestone ------------------------------------------------------------------------------------


def milestone(key: str, holder: EntityRef = UNION) -> Event:
    return make(
        "campaign.global_milestone_recorded/gv:1/FirstWarship",
        key,
        [ref(EntityDomain.GLOBAL_VALUES, "1"), holder],
        [("milestone", "FirstWarship"), ("faction", holder)],
        EventStatus.OBJECTIVE,
        significance=Significance.CAMPAIGN_DEFINING,
    )


def test_a_milestone_is_interval_dated_without_a_charge() -> None:
    [first] = of_type(built([milestone(K1)]), "campaign.first_milestone")

    assert first.date == K1 and first.date_basis is DateBasis.INTERVAL
    assert first.significance is Significance.CAMPAIGN_DEFINING


def test_a_single_candidate_charge_dates_the_milestone() -> None:
    stream = [milestone(K1), charge(K1, UNION, "Global Milestone", "2032-02-10T00:00:00")]

    [first] = of_type(built(stream), "campaign.first_milestone")

    assert first.date == "2032-02-10T00:00:00" and first.date_basis is DateBasis.RECORD
    assert len(first.constituents) == 2


def test_a_charge_shared_with_another_faction_does_not_date_it() -> None:
    stream = [
        milestone(K1),
        charge(K1, UNION, "Global Milestone", "2032-02-10T00:00:00"),
        charge(K1, ACADEMY, "Global Milestone", "2032-02-11T00:00:00"),
    ]

    [first] = of_type(built(stream), "campaign.first_milestone")

    assert first.date == K1 and len(first.constituents) == 1


# --- faction.fleet_buildup ---------------------------------------------------------------------------------------


def test_five_ships_of_one_hull_are_a_buildup_with_corroboration() -> None:
    ships = [ship(K1, number) for number in range(1, 6)]
    stream = [*ships, charge(K1, UNION, "Ship Construction", "2032-02-01T00:00:00")]

    [buildup] = of_type(built(stream), "faction.fleet_buildup")

    assert buildup.attribute("hull") == "Frigate" and buildup.attribute("count") == 5
    assert len(buildup.constituents) == 6
    assert "5 ships" in describe_event(buildup)


def test_fewer_ships_other_hulls_or_unknown_hulls_are_no_buildup() -> None:
    stream = [ship(K1, 1), ship(K1, 2), ship(K1, 3, "Corvette"), ship(K2, 4), ship(K1, 5, None), ship(K1, 6, None)]

    assert of_type(built(stream), "faction.fleet_buildup") == []
    assert len(of_type(built(stream, buildup_min_ships=2), "faction.fleet_buildup")) == 1


# --- technology.milestone ----------------------------------------------------------------------------------------


def completion(name: str) -> Event:
    """A completion as the significance pass ranks it: a technology of its own, a project of ``UNION``."""
    tier = MILESTONE_TEMPLATES[name].significance if name in MILESTONE_TEMPLATES else Significance.MINOR
    if name.startswith("Project_"):
        return make(
            f"faction.project_completed/faction:15/{name}",
            K1,
            [UNION],
            [("project", name)],
            EventStatus.OBJECTIVE,
            significance=tier,
        )
    return make(
        f"technology.completed/technology:{name}",
        K1,
        [ref(EntityDomain.TECHNOLOGY, name)],
        [("side", "after")],
        significance=tier,
    )


def test_listed_completions_are_milestones_at_their_tier_and_others_are_not() -> None:
    names = ["DeuteriumTritiumFusion", "Project_Warships", "PrinciplesofSpaceWarfare", "Project_SpaceTugs"]

    found = of_type(built([completion(name) for name in names]), "technology.milestone")

    assert {str(item.attribute("template")): item.significance for item in found} == {
        "DeuteriumTritiumFusion": Significance.CAMPAIGN_DEFINING,
        "Project_Warships": Significance.MAJOR,
        "PrinciplesofSpaceWarfare": Significance.MINOR,
    }
    assert all(
        item.attribute("rationale") == MILESTONE_TEMPLATES[str(item.attribute("template"))].rationale for item in found
    )


def test_factions_completing_one_project_together_are_separate_milestones() -> None:
    academy = replace(
        completion("Project_TheirSignatures"),
        id=completion("Project_TheirSignatures").id.replace("faction:15", "faction:17"),
        entities=(ACADEMY,),
    )

    found = of_type(built([completion("Project_TheirSignatures"), academy]), "technology.milestone")

    assert sorted(str(ref.entity_id) for item in found for role, ref in item.roles if role is Role.ACTOR) == [
        "faction:15",
        "faction:17",
    ]


def test_a_project_milestone_names_its_faction_and_a_technology_milestone_has_no_actor() -> None:
    found = of_type(built([completion("Project_Warships"), completion("SpaceNavies")]), "technology.milestone")
    actors = {
        str(item.attribute("template")): [ref for role, ref in item.roles if role is Role.ACTOR] for item in found
    }

    assert actors == {"Project_Warships": [UNION], "SpaceNavies": []}


# --- All rules ---------------------------------------------------------------------------------------------------


def test_results_do_not_depend_on_stream_order() -> None:
    stream = [
        outcome(K1),
        outcome(K2),
        first_hab(K1, LUNA),
        first_hab(K2, MARS),
        *(ship(K1, number) for number in range(1, 6)),
        milestone(K1),
    ]
    expected = [item.id for item in built(stream)]
    assert expected
    shuffled = list(stream)
    random.Random(7).shuffle(shuffled)

    assert [item.id for item in built(shuffled)] == expected


def test_every_event_cites_only_stream_events() -> None:
    stream = [outcome(K1), first_hab(K1, LUNA), first_hab(K2, MARS), milestone(K1)]
    ids = {item.id for item in stream}

    for item in built(stream):
        assert item.constituents and set(item.constituents) <= ids
