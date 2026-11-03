"""The councilor dossier: selection, exclusions, ranking, org nature, missions, career and the loyalty rule."""

from __future__ import annotations

from typing import Any

from tests.analyzers.support import (
    AFTER,
    councilor_ref,
    faction_ref,
    nation_ref,
    org_ref,
    region_ref,
    snapshot,
    state,
)
from tests.narrative.support import loyalty_keys
from tinarrative.config import CouncilorSettings
from tinarrative.model.entities import EntityDomain, EntityId
from tinarrative.model.events import Confidence, DateBasis, Event, EventStatus
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
        "traitTemplateNames": ("Charming",),
        "typeTemplateName": "Operative",
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
    assert dossier["councilors"][0]["traits"] == ["LoyaltyMonitor"]


def test_portrait_facts() -> None:
    snap = _world(_org("70", 2, template="RandomCriminal23"), _councilor("100", "1", orgs=("70",)))
    entry = _build(snap)["councilors"][0]
    assert entry["age"] == 41
    assert entry["tenure_years"] == 2.4
    assert entry["home"] == {
        "region": {"id": "region:40", "name": "Fixture region 40"},
        "nation": {"id": "nation:20", "name": "Fixture nation 20"},
    }
    assert entry["traits"] == ["Charming"]
    assert entry["orgs"][0]["category"] == "criminal"


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


def test_missions_are_player_only_and_counted_by_mission_and_target() -> None:
    def mission(key: str, councilor: str, template: str, target: str) -> Any:
        return state(
            EntityDomain.MISSION,
            key,
            AFTER,
            templateName=template,
            councilor=councilor_ref(councilor),
            target=nation_ref(target),
        )

    snap = _world(
        _councilor("100", "1"),
        _councilor("110", "2"),
        mission("200", "100", "Propaganda", "20"),
        mission("201", "100", "Propaganda", "20"),
        mission("202", "100", "Coup", "20"),
        mission("203", "110", "Coup", "20"),
    )
    dossier = _build(snap, CouncilorSettings(missions_per_councilor=1))
    player, rival = dossier["councilors"]
    assert player["missions"] == [
        {"mission": "Propaganda", "target": {"id": "nation:20", "name": "Fixture nation 20"}, "count": 2}
    ]
    assert "missions" not in rival


def _event(event_type: str, councilor: str, date: str) -> Event:
    return Event(
        id=f"{event_type}/councilor:{councilor}",
        event_type=event_type,
        status=EventStatus.OBJECTIVE,
        confidence=Confidence.HIGH,
        date=date,
        date_basis=DateBasis.INTERVAL,
        not_before=None,
        sources=(),
        entities=(councilor_ref(councilor),),
        attributes=(("transition", "changed"),),
    )


def test_career_is_attributed_by_the_first_named_entity_and_limited_to_career_types() -> None:
    snap = _world(_councilor("100", "1"), _councilor("101", "1"))
    career = [
        _event("councilor.faction_changed", "100", "2030-01-01T00:00:00"),
        _event("councilor.location_changed", "100", "2030-02-01T00:00:00"),
        _event("councilor.status_changed", "101", "2030-03-01T00:00:00"),
    ]
    first, second = _build(snap, career=career)["councilors"]
    assert [item["type"] for item in first["career"]] == ["councilor.faction_changed"]
    assert first["career"][0]["attributes"] == {"transition": "changed"}
    assert [item["type"] for item in second["career"]] == ["councilor.status_changed"]
    assert _build(snap)["councilors"][0]["career"] == []
