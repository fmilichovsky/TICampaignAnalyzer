"""Coverage for tinarrative.narrator.chapters: the chapter plan, chapter packages and continuity.

The packages here are hand-built in the shape of ``events --narrative --format json``; sizes are set with padding
attributes so that each case falls on one step of the planner, with budgets measured against the system prompt.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any

import pytest

from tinarrative.config import NarratorSettings
from tinarrative.narrator.chapters import (
    ChapterPlan,
    OverBudget,
    _Planner,
    base_options,
    derive_period,
    estimate,
    period_label,
    plan_chapters,
    validate,
)
from tinarrative.narrator.request import system_prompt

QUARTERS = ["2032-01-01T00:00:00", "2032-04-01T00:00:00", "2032-07-01T00:00:00", "2032-10-01T00:00:00"]
QUARTERS.append("2033-01-01T00:00:00")
MONTHS = ["2031-12-01T00:00:00", "2032-01-01T00:00:00", "2032-02-01T00:00:00", "2032-03-01T00:00:00"]
NATIONS = [("nation:1", "Northland", 900.0), ("nation:2", "Southland", 100.0), ("nation:3", "Eastland", None)]
RESISTANCE = {"ref": "faction:15", "name": "Fixture Resistance"}
GLOSSARY = [
    {"ref": "faction:15", "domain": "faction", "name": "Fixture Resistance", "kind": "TIFactionState"},
    {"ref": "faction:16", "domain": "faction", "name": "Fixture Servants", "kind": "TIFactionState"},
    {
        "ref": "nation:1",
        "domain": "nation",
        "name": "Northland",
        "kind": "TINationState",
        "regions": [{"ref": "region:10", "name": "North"}],
    },
    {"ref": "nation:2", "domain": "nation", "name": "Southland", "kind": "TINationState", "regions": []},
    {"ref": "nation:3", "domain": "nation", "name": "Eastland", "kind": "TINationState", "regions": []},
    {"ref": "region:10", "domain": "region", "name": "North", "kind": "TIRegionState"},
]


def _situation(date: str) -> dict[str, Any]:
    return {
        "date": date,
        "player_faction_name": "Fixture Resistance",
        "nations": [
            {
                "nation": {"ref": ref, "name": name},
                "shares": {},
                "statistics": {"GDP": {"unknown": "missing"} if gdp is None else gdp},
            }
            for ref, name, gdp in NATIONS
        ],
        "world": {"nations": len(NATIONS)},
    }


def _package(
    dates: list[str], narrative: list[dict[str, Any]], atomic: dict[int, list[dict[str, Any]]] | None = None
) -> dict[str, Any]:
    atomic = atomic or {}
    return {
        "campaign": {"key": "fixture"},
        "saves": [{"key": date, "sha256": "0" * 64, "date": date, "situation": _situation(date)} for date in dates],
        "min_significance": "major",
        "include_constituents": True,
        "settings": {"narrative": {}},
        "narrative": narrative,
        "narrative_omitted": 0,
        "intervals": [
            {
                "index": position,
                "key": dates[position + 1],
                "not_before": dates[position],
                "date": dates[position + 1],
                "events": atomic.get(position, []),
                "inferred": [],
                "omitted": {"objective": 0, "inferred": 0},
            }
            for position in range(len(dates) - 1)
        ],
        "glossary": GLOSSARY,
    }


def _development(
    identifier: str,
    start: Any,
    end: Any,
    *,
    start_basis: str = "record",
    significance: str = "major",
    open: bool = False,
    intervals: tuple[str, ...] = (),
    constituents: tuple[str, ...] = (),
    roles: list[dict[str, Any]] | None = None,
    padding: int = 0,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "event_type": "faction.takeover",
        "significance": significance,
        "start": start,
        "start_basis": start_basis,
        "end": end,
        "open": open,
        "intervals": list(intervals),
        "roles": roles if roles is not None else [{"role": "actor", "entity": RESISTANCE}],
        "attributes": {"note": "x" * padding},
        "constituents": list(constituents),
    }


def _atomic(identifier: str, *, padding: int = 0, constituents: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "id": identifier,
        "event_type": "nation.control_changed",
        "entities": [],
        "attributes": {"note": "y" * padding},
        "constituents": list(constituents),
    }


def _budget(extra: int, **changes: int) -> NarratorSettings:
    """Character-counted settings: the system prompt plus ``extra`` characters."""
    return replace(NarratorSettings(), max_input_tokens=len(system_prompt()) + extra, chars_per_token=1, **changes)


def _plan(package: dict[str, Any], settings: NarratorSettings, **options: str) -> ChapterPlan:
    plan = plan_chapters(package, base_options(package, settings, **options), settings)
    assert isinstance(plan, ChapterPlan)
    return plan


def _embedded(plan: ChapterPlan, index: int) -> dict[str, Any]:
    content = plan.chapters[index].request["messages"][0]["content"]
    return json.loads(content.partition("```json\n")[2].rpartition("\n```")[0])  # type: ignore[no-any-return]


def _block(plan: ChapterPlan, index: int) -> str:
    return str(plan.chapters[index].request["messages"][0]["content"]).partition("\n\n")[0]


def _quarterly(padding: dict[int, int] | None = None) -> dict[str, Any]:
    """One development per quarter, each built from one atomic event of its interval."""
    padding = padding or {}
    narrative = [
        _development(
            f"dev{position}@{QUARTERS[position + 1]}",
            QUARTERS[position],
            QUARTERS[position + 1],
            intervals=(QUARTERS[position + 1],),
            constituents=(f"atom{position}@{QUARTERS[position + 1]}",),
        )
        for position in range(4)
    ]
    atomic = {
        position: [_atomic(f"atom{position}@{QUARTERS[position + 1]}", padding=padding.get(position, 0))]
        for position in range(4)
    }
    return _package(QUARTERS, narrative, atomic)


def test_a_small_package_is_one_whole_chapter() -> None:
    package = _quarterly()

    plan = _plan(package, NarratorSettings())

    assert len(plan.chapters) == 1
    chapter = plan.chapters[0]
    assert (chapter.part, chapter.chapter.reduction, chapter.periods) == (
        "whole",
        None,
        ("2032-Q2", "2032-Q3", "2032-Q4", "2033-Q1"),
    )
    assert _block(plan, 0) == "chapter: 1 of 1\npart: whole\ncovers: 2032-01-01 to 2033-01-01\nperiod: quarter"
    embedded = _embedded(plan, 0)
    assert embedded["narrative"] == package["narrative"]
    assert embedded["chapter"] == {
        "index": 1,
        "count": 1,
        "part": "whole",
        "covers": {"from": QUARTERS[0], "to": QUARTERS[-1]},
    }
    assert embedded["continuity"] == {"continuing": [], "earlier": [], "earlier_omitted": 0}


def test_chapters_are_runs_of_whole_periods_within_the_budget() -> None:
    package = _quarterly({position: 20_000 for position in range(4)})
    settings = _budget(30_000)

    plan = _plan(package, settings)

    assert [chapter.part for chapter in plan.chapters] == ["first", "middle", "middle", "last"]
    assert [chapter.periods for chapter in plan.chapters] == [("2032-Q2",), ("2032-Q3",), ("2032-Q4",), ("2033-Q1",)]
    assert [chapter.covers for chapter in plan.chapters] == list(zip(QUARTERS, QUARTERS[1:], strict=False))
    assert all(chapter.chapter.reduction is None for chapter in plan.chapters)
    assert all(chapter.estimate <= settings.max_input_tokens for chapter in plan.chapters)
    for position, chapter in enumerate(plan.chapters):
        assert estimate(chapter.request, 1) == chapter.estimate
        assert [event["id"] for event in _embedded(plan, position)["narrative"]] == [
            package["narrative"][position]["id"]
        ]
    assert _block(plan, 1).startswith("chapter: 2 of 4\npart: middle\ncovers: 2032-04-01 to 2032-07-01\n")


def test_periods_that_fit_together_share_a_chapter() -> None:
    package = _quarterly({0: 10_000, 1: 10_000, 2: 20_000, 3: 5_000})

    plan = _plan(package, _budget(30_000))

    assert [chapter.periods for chapter in plan.chapters] == [("2032-Q2", "2032-Q3"), ("2032-Q4", "2033-Q1")]


def test_a_period_over_budget_loses_its_atomic_stream_first() -> None:
    package = _quarterly({1: 50_000})

    plan = _plan(package, _budget(30_000))

    assert [chapter.periods for chapter in plan.chapters] == [("2032-Q2",), ("2032-Q3",), ("2032-Q4", "2033-Q1")]
    assert [chapter.chapter.reduction for chapter in plan.chapters] == [None, "atomic_dropped", None]
    reduced = _embedded(plan, 1)
    assert [interval["events"] for interval in reduced["intervals"]] == [[]]
    assert reduced["narrative"] == [package["narrative"][1]]
    assert [interval["events"] for interval in _embedded(plan, 2)["intervals"]] == [
        package["intervals"][2]["events"],
        package["intervals"][3]["events"],
    ]


def _monthly(padding: int) -> dict[str, Any]:
    """One quarter of three monthly intervals, each holding a development of ``padding`` characters."""
    narrative = [
        _development(f"dev{position}@{MONTHS[position + 1]}", MONTHS[position], MONTHS[position + 1], padding=padding)
        for position in range(3)
    ]
    return _package(MONTHS, narrative)


def test_a_period_still_over_budget_is_split_at_saves() -> None:
    package = _monthly(12_000)
    settings = _budget(30_000)

    plan = _plan(package, settings)

    assert [chapter.covers for chapter in plan.chapters] == [(MONTHS[0], MONTHS[2]), (MONTHS[2], MONTHS[3])]
    assert [chapter.periods for chapter in plan.chapters] == [("2032-Q1",), ("2032-Q1",)]
    assert [chapter.chapter.reduction for chapter in plan.chapters] == ["split", "split"]
    assert sum(chapter.developments for chapter in plan.chapters) == len(package["narrative"])
    assert all(chapter.estimate <= settings.max_input_tokens for chapter in plan.chapters)
    assert "covers: 2032-02-01 to 2032-03-01" in _block(plan, 1)


def test_an_interval_is_labelled_by_its_closing_save() -> None:
    package = _package(["2026-11-01T00:00:00", "2027-02-01T00:00:00", "2027-05-01T00:00:00"], [])

    plan = _plan(package, NarratorSettings())

    assert plan.chapters[0].periods == ("2027-Q1", "2027-Q2")


def test_a_development_is_filed_by_a_recorded_start_else_by_its_end() -> None:
    dates = ["2026-11-01T00:00:00", "2027-01-01T00:00:00", "2027-04-01T00:00:00", "2027-07-01T00:00:00"]
    narrative = [
        _development("interval", dates[1], dates[2], start_basis="interval"),
        _development("record", dates[1], dates[2], start_basis="record"),
        _development("known", dates[0], dates[3], start_basis="interval"),
    ]
    planner = _Planner(_package(dates, narrative), {"period": "quarter"}, NarratorSettings(), None)

    assert planner.starts == [1, 1, 2]


def test_an_interval_that_cannot_fit_stops_the_plan_with_the_budget_it_needs() -> None:
    package = _monthly(12_000)
    package["narrative"][1]["attributes"]["note"] = "x" * 40_000
    settings = _budget(30_000)

    result = plan_chapters(package, base_options(package, settings), settings)

    assert isinstance(result, OverBudget)
    assert result.interval == MONTHS[2]
    assert result.budget == settings.max_input_tokens
    assert result.needed > len(system_prompt()) + 40_000


def test_the_atomic_stream_keeps_the_constituents_followed_transitively() -> None:
    date = QUARTERS[1]
    package = _package(
        QUARTERS[:2],
        [_development(f"dev@{date}", QUARTERS[0], date, constituents=(f"inferred@{date}",))],
        {0: [_atomic(f"objective@{date}"), _atomic(f"stray@{date}")]},
    )
    package["intervals"][0]["inferred"] = [_atomic(f"inferred@{date}", constituents=(f"objective@{date}",))]

    interval = _embedded(_plan(package, NarratorSettings()), 0)["intervals"][0]

    assert [event["id"] for event in interval["events"]] == [f"objective@{date}"]
    assert interval["inferred"] == package["intervals"][0]["inferred"]
    assert interval["omitted"] == package["intervals"][0]["omitted"]


def test_situations_keep_the_referenced_nations_and_the_largest_economies() -> None:
    roles = [{"role": "target", "entity": {"ref": "nation:3", "name": "Eastland"}}]
    package = _package(QUARTERS[:3], [_development("dev", QUARTERS[0], QUARTERS[1], roles=roles)])

    embedded = _embedded(_plan(package, replace(NarratorSettings(), top_economies=1)), 0)

    assert [save["key"] for save in embedded["saves"]] == [QUARTERS[0], QUARTERS[2]]
    for save, original in zip(embedded["saves"], (package["saves"][0], package["saves"][2]), strict=True):
        assert [nation["nation"]["ref"] for nation in save["situation"]["nations"]] == ["nation:1", "nation:3"]
        assert save["situation"]["world"] == original["situation"]["world"]
        assert save["situation"]["nations"][0] == original["situation"]["nations"][0]
    assert [entry["ref"] for entry in embedded["glossary"]] == ["nation:1", "nation:3", "region:10"]


def _landless(package: dict[str, Any], ref: str) -> dict[str, Any]:
    """``package`` with ``ref`` holding no region, and every other nation holding one, in every save."""
    for save in package["saves"]:
        for nation in save["situation"]["nations"]:
            nation["regions"] = 0 if nation["nation"]["ref"] == ref else 1
    return package


def _listed(embedded: dict[str, Any]) -> list[list[str]]:
    return [[nation["nation"]["ref"] for nation in save["situation"]["nations"]] for save in embedded["saves"]]


def test_a_nation_without_regions_takes_no_economy_slot() -> None:
    package = _landless(_package(QUARTERS[:3], [_development("dev", QUARTERS[0], QUARTERS[1])]), "nation:1")

    embedded = _embedded(_plan(package, replace(NarratorSettings(), top_economies=1)), 0)

    assert _listed(embedded) == [["nation:2"], ["nation:2"]]


def test_a_nation_without_regions_stays_when_a_development_of_the_chapter_names_it() -> None:
    roles = [{"role": "target", "entity": {"ref": "nation:3", "name": "Eastland"}}]
    package = _landless(
        _package(QUARTERS[:3], [_development("dev", QUARTERS[0], QUARTERS[1], roles=roles)]), "nation:3"
    )

    embedded = _embedded(_plan(package, replace(NarratorSettings(), top_economies=1)), 0)

    assert _listed(embedded) == [["nation:1", "nation:3"], ["nation:1", "nation:3"]]


def test_a_nation_without_regions_named_only_by_an_earlier_digest_is_left_out() -> None:
    package = _landless(_quarterly({position: 20_000 for position in range(4)}), "nation:3")
    package["narrative"][0]["roles"] = [{"role": "target", "entity": {"ref": "nation:3", "name": "Eastland"}}]

    embedded = _embedded(_plan(package, _budget(30_000, top_economies=1)), 1)

    assert [digest["id"] for digest in embedded["continuity"]["earlier"]] == [f"dev0@{QUARTERS[1]}"]
    assert _listed(embedded) == [["nation:1"], ["nation:1"]]
    assert "nation:3" in {entry["ref"] for entry in embedded["glossary"]}


def test_ally_refs_reach_the_chapter_glossary() -> None:
    package = _package(QUARTERS[:3], [_development("dev", QUARTERS[0], QUARTERS[1])])
    for save in package["saves"]:
        save["situation"]["nations"][0]["allies"] = ["nation:2"]

    embedded = _embedded(_plan(package, replace(NarratorSettings(), top_economies=1)), 0)

    assert _listed(embedded) == [["nation:1"], ["nation:1"]]
    assert "nation:2" in {entry["ref"] for entry in embedded["glossary"]}


def test_a_later_chapter_opens_on_the_closing_save_of_the_one_before() -> None:
    plan = _plan(_quarterly({position: 20_000 for position in range(4)}), _budget(30_000))

    assert [save["key"] for save in _embedded(plan, 0)["saves"]] == QUARTERS[0:2]
    assert [save["key"] for save in _embedded(plan, 2)["saves"]] == QUARTERS[2:4]


def test_continuity_carries_running_developments_in_full_and_recalls_the_rest() -> None:
    package = _quarterly({position: 20_000 for position in range(4)})
    package["narrative"][:0] = [
        _development("open", QUARTERS[0], QUARTERS[-1], open=True, intervals=(QUARTERS[1],)),
        _development("long", QUARTERS[0], QUARTERS[2], intervals=(QUARTERS[1], QUARTERS[2])),
        _development("defining", QUARTERS[0], QUARTERS[1], significance="campaign_defining"),
        _development("minor", QUARTERS[0], QUARTERS[1], significance="minor"),
    ]

    plan = _plan(package, _budget(30_000))

    second = _embedded(plan, 1)["continuity"]
    assert [event["id"] for event in second["continuing"]] == ["open", "long"]
    assert second["continuing"][0] == package["narrative"][0]
    assert [event["id"] for event in second["earlier"]] == ["defining", f"dev0@{QUARTERS[1]}"]
    assert second["earlier"][0] == {
        "id": "defining",
        "event_type": "faction.takeover",
        "significance": "campaign_defining",
        "start": QUARTERS[0],
        "end": QUARTERS[1],
        "roles": [{"role": "actor", "entity": RESISTANCE}],
    }
    third = _embedded(plan, 2)["continuity"]
    assert [event["id"] for event in third["continuing"]] == ["open"]
    assert [event["id"] for event in third["earlier"]] == [
        "long",
        "defining",
        f"dev0@{QUARTERS[1]}",
        f"dev1@{QUARTERS[2]}",
    ]
    assert (plan.chapters[2].continuing, plan.chapters[2].recalled) == (1, 4)


def test_the_recall_keeps_the_most_significant_then_the_latest() -> None:
    package = _quarterly({position: 20_000 for position in range(4)})
    package["narrative"][:0] = [_development("defining", QUARTERS[0], QUARTERS[1], significance="campaign_defining")]

    plan = _plan(package, _budget(30_000, recalled_developments=2))

    last = _embedded(plan, 3)["continuity"]
    assert [event["id"] for event in last["earlier"]] == ["defining", f"dev2@{QUARTERS[3]}"]
    assert last["earlier_omitted"] == 2
    off = _embedded(_plan(package, _budget(30_000, recalled_developments=0)), 3)["continuity"]
    assert (off["earlier"], off["earlier_omitted"]) == ([], 4)


def test_an_undated_development_belongs_to_its_first_interval() -> None:
    package = _quarterly({position: 20_000 for position in range(4)})
    package["narrative"].append(_development("undated", {"unknown": "missing"}, None, intervals=(QUARTERS[3],)))

    plan = _plan(package, _budget(30_000))

    assert [event["id"] for event in _embedded(plan, 2)["narrative"]] == [f"dev2@{QUARTERS[3]}", "undated"]
    assert sum(chapter.developments for chapter in plan.chapters) == len(package["narrative"])


def test_the_length_is_shared_by_significance_weighted_developments() -> None:
    package = _quarterly({position: 20_000 for position in range(4)})
    package["narrative"][0]["significance"] = "campaign_defining"
    package["narrative"][3]["significance"] = "minor"
    settings = _budget(30_000)

    plan = plan_chapters(package, base_options(package, settings), settings, length=1000)

    assert isinstance(plan, ChapterPlan)
    lengths = [_block(plan, position).rpartition("length: about ")[2] for position in range(4)]
    assert lengths == ["445 words", "222 words", "222 words", "111 words"]
    assert plan.to_dict()["request"]["length"] == 1000


def test_the_same_inputs_give_the_same_plan_and_requests() -> None:
    package = _quarterly({position: 20_000 for position in range(4)})
    settings = _budget(30_000)

    first = plan_chapters(package, base_options(package, settings), settings, length=800)
    second = plan_chapters(copy.deepcopy(package), base_options(package, settings), settings, length=800)

    assert isinstance(first, ChapterPlan) and isinstance(second, ChapterPlan)
    assert json.dumps(first.to_dict()) == json.dumps(second.to_dict())
    assert [chapter.request for chapter in first.chapters] == [chapter.request for chapter in second.chapters]


@pytest.mark.parametrize(
    ("last", "period"),
    [("2033-12-31T00:00:00", "quarter"), ("2036-12-30T00:00:00", "half"), ("2037-01-02T00:00:00", "year")],
)
def test_the_period_follows_the_campaign_span(last: str, period: str) -> None:
    package = _package(["2032-01-01T00:00:00", last], [])

    assert derive_period(package, NarratorSettings()) == period
    assert base_options(package, NarratorSettings(), period="year")["period"] == "year"


def test_an_insider_account_focuses_on_the_player_faction_unless_told_otherwise() -> None:
    package = _package(QUARTERS[:2], [])

    assert base_options(package, NarratorSettings(), audience="insider")["focus"] == "Fixture Resistance"
    assert base_options(package, NarratorSettings(), audience="insider", focus="ESA")["focus"] == "ESA"
    assert "focus" not in base_options(package, NarratorSettings(), audience="public")


@pytest.mark.parametrize(
    ("date", "period", "label"),
    [
        ("2032-06-30T00:00:00", "year", "2032"),
        ("2032-06-30T00:00:00", "half", "2032-H1"),
        ("2032-07-01T00:00:00", "half", "2032-H2"),
        ("2032-10-01T00:00:00", "quarter", "2032-Q4"),
    ],
)
def test_period_labels(date: str, period: str, label: str) -> None:
    assert period_label(date, period) == label


def test_a_document_that_is_not_a_package_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="not a narrator package"):
        validate({"narrative": [], "glossary": []})
    with pytest.raises(ValueError, match="no key or dates"):
        validate({"saves": [], "intervals": [{"key": "k"}], "narrative": [], "glossary": []})
    with pytest.raises(ValueError, match="no interval"):
        plan_chapters(_package(QUARTERS[:1], []), {}, NarratorSettings())
