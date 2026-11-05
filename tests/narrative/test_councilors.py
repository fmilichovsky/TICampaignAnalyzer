"""The councilor dossier: selection, exclusions, ranking, org nature, missions, career and the loyalty rule."""

from __future__ import annotations

from typing import Any

from tests.analyzers.support import (
    AFTER,
    councilor_ref,
    faction_ref,
    nation_ref,
    org_ref,
    record_set,
    ref,
    region_ref,
    snapshot,
    state,
)
from tests.narrative.support import loyalty_keys
from tinarrative.config import CouncilorSettings
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import Confidence, DateBasis, Event, EventStatus
from tinarrative.model.records import NotificationEntry, RecordKind
from tinarrative.model.values import freeze
from tinarrative.narrative.councilors import build_dossier

PLAYER = EntityId(EntityDomain.FACTION, "1")
NOW = "2031-06-01T00:00:00"
LONG_AGO = "2029-01-01T00:00:00"
SKILLS = {"Persuasion": 3, "Investigation": 2, "Loyalty": 9, "ApparentLoyalty": 4}


def _faction(key: str, template: str = "Council") -> Any:
    return state(EntityDomain.FACTION, key, AFTER, templateName=template)


def _councilor(
    key: str, faction: str | None, *, recruited: str | None = LONG_AGO, orgs: tuple[str, ...] = (), **extra: Any
) -> Any:
    fields: dict[str, Any] = {
        "faction": None if faction is None else faction_ref(faction),
        "recruitDate": recruited,
        "dateBorn": "1990-03-01T00:00:00",
        "attributes": freeze(SKILLS),
        "XP": 10,
        "orgs": tuple(org_ref(org) for org in orgs),
        "traitTemplateNames": ("Famous",),
        "typeTemplateName": "Operative",
        "gender": "Female",
        "homeRegion": region_ref("40"),
    }
    fields.update(extra)
    return state(EntityDomain.COUNCILOR, key, AFTER, **fields)


def _org(key: str, tier: int, template: str = "RandomResearch11", **stats: Any) -> Any:
    return state(EntityDomain.ORGANIZATION, key, AFTER, templateName=template, tier=tier, **stats)


def _world(*extra: Any) -> Any:
    return snapshot(
        AFTER,
        _faction("1"),
        _faction("2"),
        _faction("3"),
        _faction("9", "AlienCouncil"),
        state(EntityDomain.REGION, "40", AFTER, nation=nation_ref("20")),
        state(EntityDomain.NATION, "20", AFTER),
        *extra,
        date=NOW,
    )


def _ids(dossier: dict[str, Any]) -> list[str]:
    return [entry["id"] for entry in dossier["councilors"]]


def _build(snap: Any, settings: CouncilorSettings | None = None, **kwargs: Any) -> dict[str, Any]:
    return build_dossier(snap, PLAYER, kwargs.pop("career", ()), settings or CouncilorSettings(), "save.json", **kwargs)


def test_tenure_cut_excludes_recent_recruits_and_unknown_dates() -> None:
    snap = _world(
        _councilor("100", "1"),
        _councilor("101", "1", recruited="2031-01-01T00:00:00"),
        _councilor("102", "1", recruited=None),
    )
    assert _ids(_build(snap)) == ["councilor:100"]
    assert _ids(_build(snap, CouncilorSettings(min_tenure_days=0))) == ["councilor:100", "councilor:101"]


def test_alien_unemployed_and_departed_councilors_are_excluded() -> None:
    snap = _world(
        _councilor("100", "1"),
        _councilor("101", "9"),
        _councilor("102", None),
        _councilor("103", "1", archived=True),
        _councilor("104", "1", exists=False),
    )
    assert _ids(_build(snap)) == ["councilor:100"]


def test_rivals_are_the_top_n_of_each_other_faction_and_player_councilors_are_all_in() -> None:
    snap = _world(
        _org("70", 3),
        _org("71", 1),
        _councilor("100", "1"),
        _councilor("101", "1"),
        _councilor("102", "1"),
        _councilor("110", "2", orgs=("71",)),
        _councilor("111", "2", orgs=("70",)),
        _councilor("112", "2"),
        _councilor("120", "3"),
    )
    dossier = _build(snap, CouncilorSettings(rivals_per_faction=1))
    assert _ids(dossier) == ["councilor:100", "councilor:101", "councilor:102", "councilor:111", "councilor:120"]
    assert [entry["player"] for entry in dossier["councilors"]] == [True, True, True, False, False]
    rank = {entry["id"]: entry["prominence"]["rank_in_faction"] for entry in dossier["councilors"]}
    assert rank["councilor:111"] == 1
    assert _ids(_build(snap, CouncilorSettings(rivals_per_faction=0))) == _ids(_build(snap, player_only=True))


def test_player_only_drops_rivals() -> None:
    snap = _world(_councilor("100", "1"), _councilor("110", "2"))
    assert _ids(_build(snap, player_only=True)) == ["councilor:100"]
    assert dict(_build(snap, player_only=True)["selection"])["player_only"] is True


def test_ranking_orders_by_org_tier_squared_then_skills_then_xp_then_id() -> None:
    snap = _world(
        _org("70", 2),
        _councilor("110", "2"),
        _councilor("111", "2", orgs=("70",)),
        _councilor("112", "2", attributes=freeze({"Persuasion": 9})),
        _councilor("113", "2", XP=50),
        _councilor("114", "2", XP=50),
    )
    dossier = _build(snap, CouncilorSettings(rivals_per_faction=5))
    assert _ids(dossier) == ["councilor:111", "councilor:112", "councilor:113", "councilor:114", "councilor:110"]
    assert dossier["councilors"][0]["prominence"] == {"org_tier2": 4, "skill_sum": 5, "rank_in_faction": 1}


def test_no_loyalty_anywhere() -> None:
    snap = _world(_councilor("100", "1", traitTemplateNames=("LoyaltyMonitor",)), _councilor("110", "2"))
    dossier = _build(snap)
    assert loyalty_keys(dossier) == []
    assert dossier["councilors"][0]["skills"] == {"Persuasion": 3, "Investigation": 2}
    assert dossier["councilors"][0]["traits"] == {}


def test_portrait_facts() -> None:
    snap = _world(_org("70", 2, template="RandomCriminal23"), _councilor("100", "1", orgs=("70",)))
    entry = _build(snap)["councilors"][0]
    assert entry["age"] == 41
    assert entry["tenure_years"] == 2.4
    assert entry["home"] == {
        "region": {"id": "region:40", "name": "Fixture region 40"},
        "nation": {"id": "nation:20", "name": "Fixture nation 20"},
    }
    assert entry["traits"] == {"reputation": ["Famous"]}
    assert entry["orgs"][0]["category"] == "criminal"
    assert entry["gender"] == "female"
    assert entry["profession"] == "security contractor"


def test_traits_are_grouped_display_names_without_the_hidden_ones() -> None:
    templates = ("Wealthy", "Averse", "Datajack", "PhysicistII", "SecondWave", "FooBar", "Government", "Paranoid")
    entry = _build(_world(_councilor("100", "1", traitTemplateNames=templates)))["councilors"][0]
    assert entry["traits"] == {
        "temperament": ["Cautious", "Paranoid"],
        "expertise": ["Senior Physicist"],
        "reputation": ["Wealthy"],
        "affiliation": ["Government"],
        "other": ["Foo Bar"],
    }
    assert list(entry["traits"]) == ["temperament", "expertise", "reputation", "affiliation", "other"]


def test_profession_is_plain_language_and_unknown_types_are_split_into_words() -> None:
    snap = _world(
        _councilor("100", "1", typeTemplateName="Spy"),
        _councilor("101", "1", typeTemplateName="DeepSeaDiver"),
        _councilor("102", "1", typeTemplateName=None),
    )
    assert [entry["profession"] for entry in _build(snap)["councilors"]] == [
        "intelligence officer",
        "deep sea diver",
        None,
    ]


def test_gender_is_lowercased_and_the_saves_none_is_null() -> None:
    snap = _world(_councilor("100", "1", gender="Male"), _councilor("101", "1", gender="None"))
    first, second = _build(snap)["councilors"]
    assert first["gender"] == "male"
    assert second["gender"] is None


def test_generated_org_category_comes_from_the_template() -> None:
    nature = {
        key: _build(_world(_org(key, 1, template), _councilor("100", "1", orgs=(key,))))["councilors"][0]["orgs"][0]
        for key, template in (("70", "RandomNGO22"), ("71", "RandomUnheardOf11"))
    }
    assert (nature["70"]["origin"], nature["70"]["category"], nature["70"]["basis"]) == ("generated", "ngo", "template")
    assert nature["71"]["category"] == "other"


def test_catalogued_org_category_wins_over_its_stats() -> None:
    cases = {
        "Mossad": ({"command": 1, "incomeOps_month": 3.0, "espionage": 3}, "security_intelligence"),
        "Kopassus": ({"incomeOps_month": 1.0, "security": 1}, "military"),
        "Yamagachi-gumi": ({"incomeMoney_month": 90.0, "spoilsBonus": 0.04, "economyBonus": 0.02}, "criminal"),
        "Al-Qaida": ({"command": 1, "incomeOps_month": 2.0}, "militant"),
    }
    for template, (stats, category) in cases.items():
        snap = _world(_org("70", 2, template, **stats), _councilor("100", "1", orgs=("70",)))
        org = _build(snap)["councilors"][0]["orgs"][0]
        assert (org["origin"], org["category"], org["basis"]) == ("real", category, "catalog")


def test_uncatalogued_org_category_comes_from_its_stats() -> None:
    cases = {
        "Intelligence": (
            {"espionage": 4, "investigation": 2, "administration": 5},
            "security_intelligence",
        ),
        "SpaceInstitute": ({"science": 2, "spaceflightBonus": 0.02}, "aerospace"),
        "AtomicInstitute": ({"incomeResearch_month": 15.0, "science": 2}, "research"),
        "Ministry": ({"administration": 2, "governmentBonus": 0.02}, "government"),
        "Charity": ({"welfareBonus": 0.02}, "public_interest"),
        "Bank": ({"incomeMoney_month": 10.0}, "commercial"),
        "Syndicate": ({"administration": 5, "incomeMoney_month": 50.0, "spoilsBonus": 0.04}, "criminal"),
        "Commandos": ({"command": 1, "incomeOps_month": 3.0, "security": 1}, "military"),
        "Broadcaster": ({"persuasion": 1, "incomeInfluence_month": 2.0, "knowledgeBonus": 0.01}, "media_influence"),
        "Consultancy": ({"administration": 5, "incomeMoney_month": 2.0}, "commercial"),
        "Rangers": ({"incomeOps_month": 1.0, "security": 1}, "military"),
        "Spymasters": (
            {"command": 1, "incomeOps_month": 3.0, "espionage": 3, "investigation": 1},
            "security_intelligence",
        ),
        "Enforcement": ({"incomeOps_month": 1.0, "investigation": 1}, "security_intelligence"),
        "AsteroidMiners": ({"incomeMoney_month": 10.0, "security": 2, "miningBonus": 0.07}, "mining_resources"),
        "Mystery": ({}, "other"),
    }
    for template, (stats, category) in cases.items():
        snap = _world(_org("70", 2, template, **stats), _councilor("100", "1", orgs=("70",)))
        org = _build(snap)["councilors"][0]["orgs"][0]
        assert (org["origin"], org["category"], org["basis"], org["template"]) == ("real", category, "stats", template)


ROUTINE = "{day} May 2031: Name rolled a Success for the {mission} mission in the {region} region of Fixture."
COMPLETED = "<color=#fff>01 May 2031</color>: Name completed their {mission} mission in the {region} region of Fixture."


def _outcome_event(
    councilor: str, date: str, summary: str, outcome: str = "Success", template: str = "LogMissionOutcome"
) -> Event:
    return Event(
        id=f"notification.{template}/{councilor}@{date}",
        event_type=f"notification.{template}",
        status=EventStatus.OBJECTIVE,
        confidence=Confidence.HIGH,
        date=date,
        date_basis=DateBasis.RECORD,
        not_before=None,
        sources=(),
        entities=(
            EntityRef(EntityId(EntityDomain.NOTIFICATION_QUEUE, "0"), IdentityConfidence.IN_SAVE_ID, None, "Log"),
            councilor_ref(councilor),
        ),
        attributes=(("template", template), ("summary", summary), ("outcome", outcome)),
    )


def _mission_world() -> Any:
    return _world(_councilor("100", "1"), _councilor("110", "2"))


def test_missions_come_from_the_outcomes_of_the_whole_career_ranked_by_type_with_regions() -> None:
    def routine(councilor: str, date: str, mission: str, region: str) -> Event:
        return _outcome_event(councilor, date, ROUTINE.format(day="01", mission=mission, region=region))

    career = [
        routine("100", "2031-05-01T00:00:00", "Advise", "Washington"),
        routine("100", "2031-04-01T00:00:00", "Advise", "Washington"),
        routine("100", "2031-03-01T00:00:00", "Advise", "Beijing"),
        routine("100", "2031-02-01T00:00:00", "Advise", "Beijing"),
        routine("100", "2031-01-01T00:00:00", "Advise", "Beijing"),
        routine("100", "2030-12-01T00:00:00", "Advise", "Cairo"),
        routine("100", "2030-11-01T00:00:00", "Advise", "Delhi"),
        routine("100", "2030-10-01T00:00:00", "Turn Councilor", "Lima"),
        routine("100", "2030-09-01T00:00:00", "Turn Councilor", "Lima"),
        routine("100", "2030-08-01T00:00:00", "Inspire", "Oslo"),
        routine("110", "2031-05-01T00:00:00", "Advise", "Washington"),
    ]
    dossier = _build(_mission_world(), CouncilorSettings(missions_per_councilor=2), career=career)
    player, rival = dossier["councilors"]
    assert player["missions"] == {
        "sample": True,
        "window_years": 2,
        "period": {"from": "2030-08-01", "to": "2031-06-01"},
        "outcomes_seen": 10,
        "types": [
            {
                "mission": "Advise",
                "count": 7,
                "regions": [
                    {"name": "Beijing", "count": 3},
                    {"name": "Washington", "count": 2},
                    {"name": "Cairo", "count": 1},
                ],
            },
            {"mission": "Turn Councilor", "count": 2, "regions": [{"name": "Lima", "count": 2}]},
        ],
    }
    assert "missions" not in rival


def test_missions_skip_aborted_unreadable_unattributed_and_old_outcomes() -> None:
    career = [
        _outcome_event("100", "2031-05-01T00:00:00", ROUTINE.format(day="01", mission="Advise", region="Oslo")),
        _outcome_event("100", "2031-05-02T00:00:00", COMPLETED.format(mission="Advise", region="Oslo")),
        _outcome_event("100", "2031-05-03T00:00:00", "Name aborted a pending Inspire mission.", outcome="Aborted"),
        _outcome_event("100", "2031-05-04T00:00:00", "Something else happened."),
        _outcome_event("100", "2028-05-01T00:00:00", ROUTINE.format(day="01", mission="Coup", region="Oslo")),
        _outcome_event("100", "2031-05-05T00:00:00", "x", template="LogNewCouncilorTurn"),
    ]
    missions = _build(_mission_world(), career=career)["councilors"][0]["missions"]
    assert [(item["mission"], item["count"]) for item in missions["types"]] == [("Advise", 2)]
    assert missions["outcomes_seen"] == 2


def test_missions_of_a_single_save_come_from_its_own_log() -> None:
    owner = EntityRef(EntityId(EntityDomain.NOTIFICATION_QUEUE, "0"), IdentityConfidence.IN_SAVE_ID, None, "Log")

    def entry(index: int, subject: Any, summary: str, outcome: str = "Success") -> NotificationEntry:
        return NotificationEntry(
            index,
            "LogMissionOutcome",
            f"2031-05-0{index + 1}T00:00:00",
            summary,
            outcome,
            subject,
            False,
            (),
            (),
        )

    log = record_set(
        AFTER,
        owner,
        "notificationSummaryQueue",
        RecordKind.NOTIFICATION_LOG,
        (
            entry(0, councilor_ref("100"), ROUTINE.format(day="01", mission="Advise", region="Oslo")),
            entry(1, None, ROUTINE.format(day="02", mission="Advise", region="Oslo")),
            entry(2, councilor_ref("100"), "Name aborted a pending Inspire mission.", "Aborted"),
        ),
    )
    snap = snapshot(
        AFTER,
        _faction("1"),
        _faction("2"),
        state(EntityDomain.REGION, "40", AFTER, nation=nation_ref("20")),
        state(EntityDomain.NATION, "20", AFTER),
        _councilor("100", "1"),
        records=(log,),
        date=NOW,
    )
    missions = _build(snap)["councilors"][0]["missions"]
    assert missions["outcomes_seen"] == 1
    assert missions["types"] == [{"mission": "Advise", "count": 1, "regions": [{"name": "Oslo", "count": 1}]}]


def test_missions_of_a_councilor_without_outcomes_are_an_empty_sample() -> None:
    missions = _build(_mission_world())["councilors"][0]["missions"]
    assert missions["types"] == []
    assert missions["outcomes_seen"] == 0
    assert missions["period"] == {"from": None, "to": "2031-06-01"}


def test_the_active_mission_is_the_one_the_councilor_references() -> None:
    def mission(key: str, template: str) -> Any:
        return state(
            EntityDomain.MISSION,
            key,
            AFTER,
            templateName=template,
            councilor=councilor_ref("100"),
            target=nation_ref("20"),
        )

    snap = _world(
        _councilor("100", "1", activeMission=ref(EntityDomain.MISSION, "200")),
        _councilor("101", "1"),
        mission("200", "Propaganda"),
        mission("201", "Coup"),
    )
    first, second = _build(snap)["councilors"]
    assert first["active_mission"] == {
        "mission": "Propaganda",
        "target": {"id": "nation:20", "name": "Fixture nation 20"},
    }
    assert second["active_mission"] is None


def _event(event_type: str, councilor: str, date: str, transition: str = "changed") -> Event:
    return Event(
        id=f"{event_type}/councilor:{councilor}@{date}",
        event_type=event_type,
        status=EventStatus.OBJECTIVE,
        confidence=Confidence.HIGH,
        date=date,
        date_basis=DateBasis.INTERVAL,
        not_before=None,
        sources=(),
        entities=(councilor_ref(councilor),),
        attributes=(("transition", transition),),
    )


def test_career_is_attributed_by_the_first_named_entity_and_limited_to_career_types() -> None:
    snap = _world(_councilor("100", "1"), _councilor("101", "1"))
    career = [
        _event("councilor.faction_changed", "100", "2029-06-01T00:00:00", transition="set"),
        _event("councilor.faction_changed", "100", "2030-01-01T00:00:00"),
        _event("councilor.location_changed", "100", "2030-02-01T00:00:00"),
        _event("councilor.status_changed", "101", "2030-03-01T00:00:00"),
    ]
    first, second = _build(snap, career=career)["councilors"]
    assert [item["type"] for item in first["career"]] == ["councilor.faction_changed"]
    assert first["career"][0]["attributes"] == {"transition": "changed"}
    assert [item["type"] for item in second["career"]] == ["councilor.status_changed"]
    assert _build(snap)["councilors"][0]["career"] == []
