"""Unit coverage for the entity-identity census."""

import pytest

from tinarrative.identity import ENTITY_DOMAINS, STATE_PREFIX, analyze_identity
from tinarrative.inspection import inspect_bytes, render_text
from tinarrative.model.entities import EntityDomain

FACTION = STATE_PREFIX + "TIFactionState"
NATION = STATE_PREFIX + "TINationState"


def pair(key: object, inner: object) -> dict[str, object]:
    return {"Key": {"value": key}, "Value": {"ID": {"value": inner}}}


def census(gamestates: dict[str, object], current_id: object = 100) -> dict[str, object]:
    report = analyze_identity({"currentID": {"value": current_id}, "gamestates": gamestates})
    assert report is not None
    domain = next(item for item in report.domains if item.domain.domain is EntityDomain.FACTION)
    return {"type": domain.types[0], "report": report}


@pytest.mark.parametrize("root", [[], {}, {"gamestates": []}, {"gamestates": None}])
def test_no_gamestates_object_gives_no_identity(root: object) -> None:
    assert analyze_identity(root) is None


def test_matching_ids_are_counted() -> None:
    result = census({FACTION: [pair(1, 1), pair(5, 5)]})
    item = result["type"]
    assert (item.entries, item.id_matches, item.min_id, item.max_id) == (2, 2, 1, 5)  # type: ignore[attr-defined]


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
    item = census({FACTION: entries})["type"]
    assert getattr(item, field) == count


def test_absent_and_empty_types() -> None:
    result = census({FACTION: {}})
    assert result["type"].present and result["type"].entries == 0  # type: ignore[attr-defined]
    absent = census({})["type"]
    assert not absent.present  # type: ignore[attr-defined]


def test_ids_shared_across_types_and_current_id() -> None:
    report = census({FACTION: [pair(1, 1)], NATION: [pair(1, 1)], "Other": [pair(9, 9)]}, current_id=4)["report"]
    assert report.ids_shared_across_types == 1  # type: ignore[attr-defined]
    assert report.total_ids == 2  # type: ignore[attr-defined]
    assert report.max_observed_id == 9  # type: ignore[attr-defined]
    assert report.current_id == 4  # type: ignore[attr-defined]


def test_every_documented_domain_is_present() -> None:
    assert {domain.domain for domain in ENTITY_DOMAINS} == set(EntityDomain)
    assert {domain.domain.value for domain in ENTITY_DOMAINS} == {
        "faction",
        "nation",
        "region",
        "councilor",
        "army",
        "fleet",
        "ship",
        "space object",
        "organization",
        "technology",
    }


def test_inspection_reports_anomalies() -> None:
    save = (
        '{"currentID":{"value":1},"gamestates":{"' + FACTION + '":[{"Key":{"value":2},"Value":{"ID":{"value":3}}}]}}'
    ).encode()
    report = inspect_bytes(save, "x.json")
    codes = {diagnostic.code for diagnostic in report.diagnostics}
    assert {"id_key_mismatch", "current_id_behind"} <= codes
    text = render_text(report)
    assert "identity:" in text
    assert "TIFactionState: 1 entries" in text
