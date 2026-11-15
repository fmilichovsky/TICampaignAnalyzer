"""Coverage for tinarrative.narrator.brief: the councilor brief keeps the dossier's values, drops its audit data and
names no faction."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from typing import Any

from tinarrative.narrative.org_catalog import NAMED_ORG_CATEGORIES
from tinarrative.narrator.brief import (
    AUDIT_KEYS,
    HEADER_KEYS,
    MISSION_PHRASES,
    NAMED_AUDIT_KEYS,
    ORG_ALIASES,
    ORG_AUDIT_KEYS,
    TRAIT_PHRASES,
    VISIBILITY_AUDIT_KEYS,
    councilor_brief,
    stance_of,
)
from tinarrative.trait_names import KEPT_GROUPS, TRAITS

ENTRY: dict[str, Any] = {
    "id": "councilor:1",
    "name": "Ada One",
    "faction": "Fixture Resistance",
    "player": True,
    "profession": "Diplomat",
    "gender": "female",
    "traits": {"reputation": ["Famous"]},
    "skills": {"Persuasion": 9},
    "org_skills": {"Science": 2},
    "xp": 12,
    "born": "1990-01-01T00:00:00",
    "age": 44,
    "home": {"region": {"id": "region:2", "name": "Hefei"}, "nation": {"id": "nation:3", "name": "Fixture Land"}},
    "recruited": "2026-01-01T00:00:00",
    "tenure_years": 8.4,
    "orgs": [
        {
            "id": "organization:4",
            "name": "Fixture Labs",
            "tier": 2,
            "nation": "Fixture Land",
            "template": "RandomResearch12",
            "origin": "generated",
            "category": "research",
            "basis": "template",
        }
    ],
    "policy_influence": {
        "effective_causes": 2.0,
        "causes": [{"field": "knowledgeBonus", "bonus": 0.12}],
    },
    "visibility": {"concealment": 14, "easily_visible": False, "low_profile": False},
    "prominence": {"org_share": 0.01, "skill_sum": 9, "org_skill_sum": 2, "rank_in_faction": 1},
    "career": [
        {
            "event": "event:5",
            "type": "councilor.faction_changed",
            "date": "2030-01-01T00:00:00",
            "attributes": {
                "transition": "changed",
                "before": {"ref": "faction:6", "name": "Fixture Protectorate"},
                "after": {"ref": "faction:7", "name": "Fixture Resistance"},
            },
        }
    ],
    "missions": {
        "sample": True,
        "types": [
            {
                "mission": "Advise",
                "count": 2,
                "regions": [{"name": "Hefei", "nation": "China", "count": 2}],
                "nations": [{"name": "China", "count": 2}],
            }
        ],
    },
}
DOSSIER: dict[str, Any] = {
    "as_of": "2034-06-01T00:00:00",
    "source": "latest.json",
    "player_faction": "Fixture Resistance",
    "factions": {"Fixture Resistance": "ResistCouncil", "Fixture Protectorate": "AppeaseCouncil"},
    "selection": {"article_words": 120},
    "councilors": [ENTRY],
}


def _keys(value: object, path: tuple[str, ...] = ()) -> Iterator[tuple[str, ...]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield (*path, key)
            yield from _keys(item, (*path, key))
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item, path)


def test_the_brief_holds_the_header_date_and_the_entry_without_audit_fields() -> None:
    brief = councilor_brief(DOSSIER, ENTRY)

    assert list(brief) == [*HEADER_KEYS, "councilor"]
    assert brief["as_of"] == DOSSIER["as_of"]
    councilor = brief["councilor"]
    assert AUDIT_KEYS.isdisjoint(councilor)
    assert VISIBILITY_AUDIT_KEYS.isdisjoint(councilor["visibility"])
    assert councilor["visibility"] == {"level": "private"}
    assert all(ORG_AUDIT_KEYS.isdisjoint(org) for org in councilor["orgs"])
    assert all(NAMED_AUDIT_KEYS.isdisjoint(ref) for ref in councilor["home"].values())
    assert not any(path[-1] == "id" for path in _keys(brief))


def test_the_brief_passes_every_other_value_through_as_the_dossier_has_it() -> None:
    councilor = councilor_brief(DOSSIER, ENTRY)["councilor"]

    kept = set(ENTRY) - AUDIT_KEYS - {"faction", "missions"}
    assert [key for key in councilor if key in kept] == [key for key in ENTRY if key in kept]
    for key in kept - {"visibility", "orgs", "career", "home", "policy_influence", "profession", "traits"}:
        assert councilor[key] == ENTRY[key]
    assert councilor["visibility"] == {"level": "private"}
    assert councilor["profession"] == "diplomat"
    assert councilor["traits"] == {"reputation": ["famous"]}
    assert councilor["policy_influence"] == {
        "focus": "focused",
        "causes": [{"cause": "education and research", "strength": "leading"}],
    }
    org = councilor["orgs"][0]
    assert {key: org[key] for key in ("name", "tier", "nation", "origin", "category")} == {
        key: ENTRY["orgs"][0][key] for key in ("name", "tier", "nation", "origin", "category")
    }
    assert councilor["home"]["nation"] == {"name": ENTRY["home"]["nation"]["name"]}


def test_an_aliased_organization_carries_its_public_alias_and_never_the_game_name() -> None:
    game_name = "Fixture Game Name"
    plain = ENTRY["orgs"][0]
    for template, alias in ORG_ALIASES.items():
        entry = copy.deepcopy(ENTRY)
        entry["orgs"] = [{**plain, "name": game_name, "template": template, "origin": "faction"}, plain]

        brief = councilor_brief(DOSSIER, entry)

        orgs = brief["councilor"]["orgs"]
        assert orgs[0]["name"] == alias
        assert orgs[1]["name"] == plain["name"]
        assert game_name not in json.dumps(brief)


def test_every_alias_key_is_a_named_organization_template() -> None:
    assert set(ORG_ALIASES) <= set(NAMED_ORG_CATEGORIES)


def test_a_phrased_trait_carries_its_phrase_and_never_the_game_label() -> None:
    entry = {**ENTRY, "traits": {"circumstance": ["Marked", "Indebted"], "temperament": ["ExpectsVictory"]}}

    brief = councilor_brief(DOSSIER, entry)

    assert brief["councilor"]["traits"] == {
        "circumstance": ["under surveillance worldwide", "deeply in debt"],
        "temperament": ["loss averse"],
    }
    assert "Marked" not in json.dumps(brief)


def test_every_trait_phrase_is_for_a_kept_catalogued_trait() -> None:
    assert all(TRAITS[template][0] in KEPT_GROUPS for template in TRAIT_PHRASES)


def test_the_brief_leaves_the_dossier_untouched() -> None:
    before = copy.deepcopy(DOSSIER)

    councilor_brief(DOSSIER, ENTRY)

    assert DOSSIER == before


def test_unfamiliar_game_names_are_split_into_public_words() -> None:
    entry = {
        **ENTRY,
        "profession": "DeepSeaDiver",
        "traits": {"other": ["FooBar"]},
        "policy_influence": {
            "effective_causes": 3.0,
            "causes": [{"field": "newBonus", "bonus": 0.01}],
        },
    }

    councilor = councilor_brief(DOSSIER, entry)["councilor"]

    assert councilor["profession"] == "deep sea diver"
    assert councilor["traits"] == {"other": ["foo bar"]}
    assert councilor["policy_influence"] == {
        "focus": "broad",
        "causes": [{"cause": "newBonus", "strength": "modest"}],
    }


def test_visibility_bands_are_derived_from_the_measurement_and_profile_flags() -> None:
    expected = {5: "public", 6: "private", 17: "private", 18: "shadow"}
    for concealment, level in expected.items():
        entry = {**ENTRY, "visibility": {"concealment": concealment, "easily_visible": False, "low_profile": False}}
        assert councilor_brief(DOSSIER, entry)["councilor"]["visibility"] == {"level": level}

    shadow = {**ENTRY, "visibility": {"concealment": 25, "easily_visible": True, "low_profile": False}}
    public = {**ENTRY, "visibility": {"concealment": 0, "easily_visible": False, "low_profile": True}}
    assert councilor_brief(DOSSIER, shadow)["councilor"]["visibility"] == {"level": "private"}
    assert councilor_brief(DOSSIER, public)["councilor"]["visibility"] == {"level": "private"}


def test_a_null_home_reference_stays_null() -> None:
    entry = {**ENTRY, "home": {"region": None, "nation": None}}

    assert councilor_brief(DOSSIER, entry)["councilor"]["home"] == {"region": None, "nation": None}


def _career(*items: tuple[str, str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"event": f"event:{n}", "type": kind, "date": date, "attributes": attributes}
        for n, (kind, date, attributes) in enumerate(items)
    ]


def _faction(name: str) -> dict[str, Any]:
    return {"ref": "faction:9", "state_type": "TIFactionState", "confidence": "in-save-id", "name": name}


def test_the_faction_becomes_a_stance_and_former_stances_come_from_the_career() -> None:
    councilor = councilor_brief(DOSSIER, ENTRY)["councilor"]

    assert "faction" not in councilor
    assert councilor["stance"] == "defence-minded"
    assert councilor["former_stances"] == ["accommodationist"]
    assert list(councilor)[:3] == ["name", "stance", "profession"]


def test_an_unknown_faction_gives_no_stance_and_never_its_name() -> None:
    entry = {**ENTRY, "faction": "Fixture Elsewhere", "career": []}

    councilor = councilor_brief(DOSSIER, entry)["councilor"]

    assert "stance" not in councilor and "former_stances" not in councilor
    assert "Fixture Elsewhere" not in str(councilor)
    assert stance_of({}, "Fixture Resistance") is None
    assert stance_of(DOSSIER, None) is None


def test_career_items_become_plain_dated_lines_without_status_or_organization_changes() -> None:
    career = _career(
        (
            "councilor.faction_changed",
            "2030-01-01T00:00:00",
            {
                "transition": "changed",
                "before": _faction("Fixture Protectorate"),
                "after": _faction("Fixture Resistance"),
            },
        ),
        (
            "councilor.faction_changed",
            "2030-02-01T00:00:00",
            {
                "transition": "changed",
                "before": _faction("Fixture Elsewhere"),
                "after": _faction("Fixture Protectorate"),
            },
        ),
        (
            "councilor.faction_changed",
            "2030-03-01T00:00:00",
            {"transition": "changed", "before": _faction("Fixture Resistance"), "after": None},
        ),
        ("councilor.faction_changed", "2030-04-01T00:00:00", {"transition": "cleared"}),
        (
            "councilor.detaining_faction_changed",
            "2031-01-01T00:00:00",
            {"transition": "set", "after": _faction("Fixture Protectorate")},
        ),
        ("councilor.detaining_faction_changed", "2031-02-01T00:00:00", {"transition": "changed"}),
        ("councilor.detaining_faction_changed", "2031-03-01T00:00:00", {"transition": "cleared"}),
        ("councilor.status_changed", "2031-04-01T00:00:00", {"transition": "changed"}),
        ("councilor.orgs_changed", "2031-05-01T00:00:00", {"transition": "added"}),
        ("councilor.detaining_faction_changed", None, {"transition": "set"}),
    )

    lines = councilor_brief(DOSSIER, {**ENTRY, "career": career})["councilor"]["career"]

    assert lines == [
        "2030-01-01: changed stance from accommodationist to defence-minded",
        "2030-02-01: took up an accommodationist stance",
        "2030-03-01: gave up a defence-minded stance",
        "2030-04-01: withdrew from public life",
        "2031-01-01: detained",
        "2031-02-01: transferred to other captors",
        "2031-03-01: released",
        "detained",
    ]
    assert "Fixture" not in str(lines)


SEEN_MISSIONS = (
    "Advise",
    "Investigate Councilor",
    "Public Campaign",
    "Stabilize Nation",
    "Control Nation",
    "Inspire",
    "Hostile Takeover",
    "Defend Interests",
    "Crackdown",
    "Set National Policy",
    "Purge",
    "Surveil Location",
    "Turn Councilor",
    "Assassinate",
    "Go To Ground",
    "Detain Councilor",
    "Increase Unrest",
    "Extract Councilor",
    "Investigate Alien Activity",
    "Assault Alien Asset",
    "Contact",
)
"""The mission types of the resolved-mission log entries in the benchmark campaigns, by their log wording."""


def _mission(name: str, count: int, *regions: tuple[str, str]) -> dict[str, Any]:
    nations: dict[str, int] = {}
    for _, nation in regions:
        nations[nation] = nations.get(nation, 0) + 1
    return {
        "mission": name,
        "count": count,
        "regions": [{"name": region, "nation": nation, "count": 1} for region, nation in regions],
        "nations": [{"name": nation, "count": n} for nation, n in nations.items()],
    }


def _activities(*types: dict[str, Any]) -> object:
    entry = {**ENTRY, "missions": {"sample": True, "outcomes_seen": 9, "types": list(types)}}
    return councilor_brief(DOSSIER, entry)["councilor"].get("activities")


def test_every_mission_type_seen_in_the_samples_has_a_public_phrase() -> None:
    assert [name for name in SEEN_MISSIONS if name not in MISSION_PHRASES] == []


def test_missions_become_activities_placed_by_nation_or_by_region() -> None:
    activities = _activities(
        _mission("Advise", 5, ("Beijing", "China"), ("Shanghai", "China"), ("Almaty", "Kazakhstan")),
        _mission("Assassinate", 2, ("Lisbon", "Portugal"), ("Madrid", "Spain")),
    )

    assert activities == [
        "advising the government of China and Kazakhstan",
        "being nearby when prominent figures died suddenly in Lisbon, Portugal and Madrid, Spain",
    ]
    brief = councilor_brief(DOSSIER, ENTRY)
    assert "missions" not in brief["councilor"]
    assert brief["councilor"]["activities"] == ["advising the government of China"]


def test_an_unphrased_type_is_dropped_and_a_single_sighting_only_stands_alone() -> None:
    assert _activities(_mission("Close the Gate", 4, ("Oslo", "Norway"))) is None
    assert _activities(_mission("Purge", 1, ("Oslo", "Norway"))) == [
        "pushing for changes of leadership in government posts in Oslo, Norway"
    ]
    activities = _activities(
        _mission("Close the Gate", 4, ("Oslo", "Norway")),
        _mission("Public Campaign", 3, ("Lima", "Peru")),
        _mission("Purge", 1, ("Oslo", "Norway")),
    )
    assert activities == ["public campaigning in Peru"]
    assert "Close the Gate" not in json.dumps(
        councilor_brief(DOSSIER, {**ENTRY, "missions": {"types": [_mission("Close the Gate", 4)]}})
    )
