"""Unit coverage for the entity-identity census."""

import pytest

from tinarrative.identity import ENTITY_DOMAINS, STATE_PREFIX, IdentityReport, TypeIdentity, analyze_identity
from tinarrative.model.entities import EntityDomain

FACTION = STATE_PREFIX + "TIFactionState"
NATION = STATE_PREFIX + "TINationState"


def pair(key: object, inner: object) -> dict[str, object]:
    return {"Key": {"value": key}, "Value": {"ID": {"value": inner}}}


def census_report(gamestates: dict[str, object], current_id: object = 100) -> IdentityReport:
    report = analyze_identity({"currentID": {"value": current_id}, "gamestates": gamestates})
    assert report is not None
    return report


def faction_census(gamestates: dict[str, object]) -> TypeIdentity:
    domain = next(item for item in census_report(gamestates).domains if item.domain.domain is EntityDomain.FACTION)
    return domain.types[0]


@pytest.mark.parametrize("root", [[], {}, {"gamestates": []}, {"gamestates": None}])
def test_no_gamestates_object_gives_no_identity(root: object) -> None:
    assert analyze_identity(root) is None


def test_matching_ids_are_counted() -> None:
    item = faction_census({FACTION: [pair(1, 1), pair(5, 5)]})
    assert (item.entries, item.id_matches, item.min_id, item.max_id) == (2, 2, 1, 5)


@pytest.mark.parametrize(
    ("entries", "field", "count"),
    [
        ([pair(1, 2)], "id_mismatches", 1),
        ([pair(1, 1), pair(1, 1)], "id_duplicates", 1),
        ([pair("1", 1)], "id_missing", 1),
        ([pair(True, True)], "id_missing", 1),
        ([{"Key": {"value": 3}}], "id_missing", 1),
        (["not an entry"], "id_missing", 1),
    ],
)
def test_anomalies_are_counted(entries: list[object], field: str, count: int) -> None:
    assert getattr(faction_census({FACTION: entries}), field) == count


def test_absent_and_empty_types() -> None:
    empty = faction_census({FACTION: {}})
    assert empty.present and empty.entries == 0
    assert not faction_census({}).present


def test_ids_shared_across_types_and_current_id() -> None:
    report = census_report({FACTION: [pair(1, 1)], NATION: [pair(1, 1)], "Other": [pair(9, 9)]}, current_id=4)
    assert report.ids_shared_across_types == 1
    assert report.total_ids == 2
    assert report.max_observed_id == 9
    assert report.current_id == 4


def test_every_documented_domain_is_present() -> None:
    assert {domain.domain for domain in ENTITY_DOMAINS} == set(EntityDomain)
    assert {domain.domain.value for domain in ENTITY_DOMAINS} == {
        "faction",
        "nation",
        "region",
        "control point",
        "councilor",
        "mission",
        "army",
        "fleet",
        "ship",
        "space body",
        "space object",
        "organization",
        "technology",
        "war",
        "federation",
        "region alien state",
        "global values",
        "notification queue",
    }
