"""The narrator form of the JSON report: slimmed situation reports, rounded floats and shift entries without IDs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.events import Confidence, DateBasis, Event, EventStatus, Role, Significance
from tinarrative.rendering.json_report import _drop_shift_events, _entry, _narrator_package, _slim, _slim_situations

ALLY = {"ref": "nation:4", "state_type": "TINationState", "confidence": "in_save_id", "name": "Fixture Ally"}


def _saves(nation: dict[str, Any], faction: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"situation": None}, {"situation": {"nations": [nation], "factions": [faction]}}]


def _body(ref: str, habs: int) -> dict[str, Any]:
    return {"body": {"ref": ref, "name": ref}, "habs": habs}


def test_situations_lose_bookkeeping_and_allies() -> None:
    nation = {
        "nation": {"ref": "nation:1"},
        "seat_basis": "executive_point",
        "unresolved_points": 0,
        "allies": [ALLY, {"unknown": "unresolved"}],
    }
    saves = _saves(nation, {"habs_by_body": []})

    _slim_situations(saves)

    assert saves[1]["situation"]["nations"] == [{"nation": {"ref": "nation:1"}}]
    saves = _saves({"allies": {"unknown": "missing"}}, {"habs_by_body": []})

    _slim_situations(saves)

    assert saves[1]["situation"]["nations"] == [{}]


def test_unresolved_points_stay_when_not_zero() -> None:
    for value in (2, {"unknown": "missing"}):
        saves = _saves({"unresolved_points": value}, {"habs_by_body": []})

        _slim_situations(saves)

        assert saves[1]["situation"]["nations"] == [{"unresolved_points": value}]


def test_defaults_are_dropped_and_set_values_stay() -> None:
    defaults = {"alien": False, "wars": [], "federation": None}
    saves = _saves(dict(defaults), {"habs_by_body": []})

    _slim_situations(saves)

    assert saves[1]["situation"]["nations"] == [{}]
    war = {"war": {"ref": "war:1"}, "side": "a"}
    federation = {"ref": "federation:2"}
    unknown = {"unknown": "missing"}
    for set_values in ({"alien": True}, {"wars": [war]}, {"federation": federation}, {"federation": unknown}):
        saves = _saves({**defaults, **set_values}, {"habs_by_body": []})

        _slim_situations(saves)

        assert saves[1]["situation"]["nations"] == [set_values]


def test_shares_are_dropped_only_when_they_repeat_the_executive_and_control_points() -> None:
    executive = {"ref": "faction:1", "name": "Fixture"}
    repeated = {"executive": executive, "control_points": 4, "shares": {"faction:1": 4}}
    kept = [
        {**repeated, "shares": {"faction:1": 3}},
        {**repeated, "shares": {"faction:1": 3, "faction:2": 1}},
        {**repeated, "shares": {"faction:2": 4}},
        {**repeated, "shares": {"unknown": "missing"}},
        {**repeated, "executive": {"unknown": "missing"}},
        {**repeated, "shares": {}},
    ]
    saves = _saves(dict(repeated), {"habs_by_body": []})

    _slim_situations(saves)

    assert saves[1]["situation"]["nations"] == [{"executive": executive, "control_points": 4}]
    for nation in kept:
        saves = _saves(dict(nation), {"habs_by_body": []})

        _slim_situations(saves)

        assert saves[1]["situation"]["nations"] == [nation]


def test_single_hab_bodies_are_counted_not_listed() -> None:
    faction = {
        "faction": {"ref": "faction:15"},
        "habs": 6,
        "habs_by_body": [_body("space_body:1", 1), _body("space_body:2", 3), _body("space_body:3", 1)],
        "fleets": 0,
    }
    saves = _saves({}, faction)

    _slim_situations(saves)

    slimmed = saves[1]["situation"]["factions"][0]
    assert list(slimmed) == ["faction", "habs", "habs_by_body", "other_bodies", "fleets"]
    assert slimmed["habs"] == 6
    assert slimmed["habs_by_body"] == [_body("space_body:2", 3)]
    assert slimmed["other_bodies"] == 2


def test_floats_keep_four_significant_digits() -> None:
    assert _slim(
        {"GDP": 263196806407.196, "democracy": 6.818421, "regions": 12, "flag": True, "small": 0.000123456}
    ) == {
        "GDP": 263200000000.0,
        "democracy": 6.818,
        "regions": 12,
        "flag": True,
        "small": 0.0001235,
    }


def test_shift_entries_lose_their_event_ids_and_nothing_else() -> None:
    entry = {"nation": {"ref": "nation:1"}, "statistic": "GDP", "events": ["nation.statistic_shifted/nation:1@k"]}
    narrative = [
        {"attributes": {"metric_shifts": [entry], "metric_shifts_omitted": 3, "events": ["kept"]}},
        {"attributes": {"region_count": 2}},
    ]

    _drop_shift_events(narrative)

    assert narrative == [
        {
            "attributes": {
                "metric_shifts": [{"nation": {"ref": "nation:1"}, "statistic": "GDP"}],
                "metric_shifts_omitted": 3,
                "events": ["kept"],
            }
        },
        {"attributes": {"region_count": 2}},
    ]


def test_the_narrator_package_drops_the_significance_basis_and_keeps_the_score() -> None:
    scaled = {"id": "a", "score": 70, "significance_basis": {"base": 62}, "sources": []}
    document = {
        "campaign": {},
        "skipped": [],
        "saves": [],
        "narrative": [dict(scaled)],
        "intervals": [{"before": {}, "after": {}, "events": [dict(scaled)], "inferred": [dict(scaled)]}],
    }

    package = _narrator_package(document)

    events = [*package["narrative"], *package["intervals"][0]["events"], *package["intervals"][0]["inferred"]]
    assert events == [{"id": "a", "score": 70}] * 3


def test_a_digested_member_keeps_its_headline_and_names_its_wave() -> None:
    nation = EntityRef(EntityId(EntityDomain.NATION, "1"), IdentityConfidence.IN_SAVE_ID)
    date = datetime(2030, 2, 1).isoformat()
    member = Event(
        id="faction.takeover/nation:1@k",
        event_type="faction.takeover",
        status=EventStatus.INFERRED,
        confidence=Confidence.MEDIUM,
        date=date,
        date_basis=DateBasis.INTERVAL,
        not_before=date,
        sources=(),
        entities=(nation,),
        attributes=(("cause", "Politics"),),
        significance=Significance.MAJOR,
        constituents=("faction.nation_control_changed/nation:1@k",),
        start=date,
        start_basis=DateBasis.INTERVAL,
        end=date,
        end_basis=DateBasis.INTERVAL,
        intervals=("k",),
        roles=((Role.TARGET, nation),),
    )

    digest = _entry(member, {member.id: "faction.takeover_wave/faction:2@k"})

    assert set(digest) == {
        "id", "event_type", "significance", "start", "start_basis", "end", "roles", "intervals", "member_of"
    }  # fmt: skip
    assert digest["member_of"] == "faction.takeover_wave/faction:2@k"
    assert _entry(member, {}) == member.to_dict()
