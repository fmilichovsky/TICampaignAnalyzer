"""Coverage for tinarrative.narrator.brief: the councilor brief keeps the dossier's values, drops its audit data and
names no faction."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import Any

from tinarrative.narrator.brief import (
    AUDIT_KEYS,
    HEADER_KEYS,
    NAMED_AUDIT_KEYS,
    ORG_AUDIT_KEYS,
    VISIBILITY_AUDIT_KEYS,
    councilor_brief,
    stance_of,
)

ENTRY: dict[str, Any] = {
    "id": "councilor:1",
    "name": "Ada One",
    "faction": "Fixture Resistance",
    "player": True,
    "profession": "diplomat",
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
    "policy_influence": {"focus": "focused", "causes": [{"cause": "science", "strength": "leading"}]},
    "visibility": {"level": "private", "concealment": 14},
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
        "types": [{"mission": "Advise", "count": 2, "regions": [{"name": "Hefei", "count": 2}]}],
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
    assert all(ORG_AUDIT_KEYS.isdisjoint(org) for org in councilor["orgs"])
    assert all(NAMED_AUDIT_KEYS.isdisjoint(ref) for ref in councilor["home"].values())
    assert not any(path[-1] == "id" for path in _keys(brief))


def test_the_brief_passes_every_other_value_through_as_the_dossier_has_it() -> None:
    councilor = councilor_brief(DOSSIER, ENTRY)["councilor"]

    kept = set(ENTRY) - AUDIT_KEYS - {"faction"}
    assert [key for key in councilor if key in kept] == [key for key in ENTRY if key in kept]
    for key in kept - {"visibility", "orgs", "career", "home"}:
        assert councilor[key] == ENTRY[key]
    assert councilor["visibility"]["level"] == ENTRY["visibility"]["level"]
    org = councilor["orgs"][0]
    assert {key: org[key] for key in ("name", "tier", "nation", "origin", "category")} == {
        key: ENTRY["orgs"][0][key] for key in ("name", "tier", "nation", "origin", "category")
    }
    assert councilor["home"]["nation"] == {"name": ENTRY["home"]["nation"]["name"]}


def test_the_brief_leaves_the_dossier_untouched() -> None:
    before = copy.deepcopy(DOSSIER)

    councilor_brief(DOSSIER, ENTRY)

    assert DOSSIER == before


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
