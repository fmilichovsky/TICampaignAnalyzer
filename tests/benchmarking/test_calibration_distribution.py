"""The distribution view: percentiles of each kind's shares per scaling, the world quantity beside them, drafts and
the samples a profile marks non-standard."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest

from tests.benchmarking.calibration_support import (
    DRAFT_INDEX,
    FIRST,
    POWER,
    SECOND,
    drafted,
    power,
    row,
    saves,
    synthetic_kinds,
)
from tests.fixtures import FIXTURES_ROOT
from tests.golden import AssertGolden
from tinarrative.benchmarking.calibration.readout import override_state
from tinarrative.benchmarking.calibration.replay import default_state
from tinarrative.benchmarking.calibration.stats import percentiles
from tinarrative.benchmarking.calibration.table import build_index, extract_campaign
from tinarrative.benchmarking.calibration.views import render_views, views_document

GOLDEN = FIXTURES_ROOT / "benchmarking" / "calibration_distribution"


def dated(item: dict[str, Any], key: str) -> dict[str, Any]:
    return {**item, "interval": key, "intervals": [{"key": key, "start": "2030-01-01", "end": key}]}


def spread(types: tuple[str, str], scales: list[float]) -> list[dict[str, Any]]:
    """Rows alternating between two types, the nth with its power share ``POWER * 10 ** (scale / 10)``, in the
    intervals ``2030-06-01`` (the first save), ``2031-06-01`` and ``2032-06-01`` (the last), thirds of the rows each."""
    keys = ["2030-06-01", "2031-06-01", "2032-06-01"]
    return [
        dated(row(f"r{n}", types[n % 2], tier="narrative", shares=power(scale)), keys[n * 3 // len(scales)])
        for n, scale in enumerate(scales)
    ]


def index_of(tables: dict[str, list[dict[str, Any]]], **extra: Any) -> dict[str, Any]:
    return build_index(list(tables), key="d", extracted_at="", kinds=synthetic_kinds(tables), **extra)


def test_percentiles_interpolate_between_ranks_and_say_how_many() -> None:
    found = percentiles([5.0, 1.0, 3.0, 2.0, 4.0])

    assert found == {"n": 5, "p10": 1.4, "p25": 2.0, "p50": 3.0, "p75": 4.0, "p90": 4.6}
    assert percentiles([7.0]) == {"n": 1, "p10": 7.0, "p25": 7.0, "p50": 7.0, "p75": 7.0, "p90": 7.0}
    assert percentiles([]) is None


def test_a_kinds_share_percentiles_are_read_at_the_first_save_the_last_and_over_all_events() -> None:
    rows = spread((FIRST, SECOND), [-10, -8, -6, 0, 2, 4, 10, 12, 14])
    tables = {"c": rows}
    index = index_of(tables)
    document = views_document(index, tables, None, default_state(index), views=("distribution",))

    power_scaling = document["views"]["distribution"]["scalings"]["power"]
    kind = power_scaling["kinds"][FIRST]["campaigns"]["c"]
    shares = {item["id"]: item["shares"][0]["share"] for item in rows if item["type"] == FIRST}
    assert kind["all"]["n"] == len(shares)
    assert kind["first"]["n"] == 2 and kind["last"]["n"] == 2
    assert kind["first"]["p50"] == pytest.approx((shares["r0"] + shares["r2"]) / 2)
    assert kind["last"]["p50"] == pytest.approx((shares["r6"] + shares["r8"]) / 2)
    assert kind["all"]["p10"] < kind["all"]["p50"] < kind["all"]["p90"]


def test_the_rise_and_drop_shares_are_marked_and_the_median_lands_on_a_level_beside_its_base() -> None:
    rows = spread((FIRST, SECOND), [-30, -30, 0, 0, 30, 30])
    tables = {"c": rows}
    index = index_of(tables)
    document = views_document(index, tables, None, default_state(index), views=("distribution",))
    scaling = document["views"]["distribution"]["scalings"]["power"]

    assert scaling["rise"] == index["scalings"]["power"]["rise"]
    assert scaling["drop"] < POWER < scaling["rise"]
    first = scaling["kinds"][FIRST]
    assert first["at_rise"] == 1 and first["at_drop"] == 1
    text = render_views(document)
    assert "^" in text and "v" in text
    assert f"{FIRST} - base {first['base']}" in text and "lands on" in text


def test_a_scalings_reason_comes_with_its_status_and_the_kinds_median_span() -> None:
    rows = spread((FIRST, SECOND), [-20, 20, -20, 20, -20, 20])
    tables = {"c": rows}
    index = index_of(tables)
    principle = next(iter(index["principles"]))
    current = index["principles"][principle]["revision"]
    stale = {"principle": principle, "because": "a regional power", "revision": current - 1, "status": "examined"}
    index = {**index, "scalings": {**index["scalings"], "power": {**index["scalings"]["power"], "reason": stale}}}
    document = views_document(index, tables, None, default_state(index), views=("distribution",))
    scaling = document["views"]["distribution"]["scalings"]["power"]

    assert scaling["reason"]["status"] == "stale"
    assert f"(stale r{current - 1}→r{current})" in scaling["reason"]["text"]
    assert scaling["median_span"] == pytest.approx(
        scaling["kinds"][SECOND]["pooled"]["p50"] / scaling["kinds"][FIRST]["pooled"]["p50"]
    )
    assert "unexamined" in render_views(
        views_document(index_of(tables), tables, None, default_state(index_of(tables)), views=("distribution",))
    )


def test_a_tried_rise_share_moves_the_marks_and_the_filters_narrow_the_kinds() -> None:
    rows = spread((FIRST, SECOND), [-30, -30, 0, 0, 30, 30])
    tables = {"c": rows}
    index = index_of(tables)
    tried = override_state(default_state(index), index, rises=["power=0.001"])
    document = views_document(index, tables, None, tried, views=("distribution",))
    scaling = document["views"]["distribution"]["scalings"]["power"]

    assert scaling["rise"] == 0.001
    assert scaling["kinds"][FIRST]["at_rise"] > 1
    only = views_document(index, tables, None, replace(default_state(index), types=(FIRST,)), views=("distribution",))
    assert list(only["views"]["distribution"]["scalings"]["power"]["kinds"]) == [FIRST]


def test_a_draft_share_gets_its_full_distribution_under_the_scaling_it_reads() -> None:
    rows, shadows = drafted()
    tables = {"one": rows}
    document = views_document(
        DRAFT_INDEX,
        tables,
        {"one": shadows},
        replace(default_state(DRAFT_INDEX), campaigns=("one",)),
        views=("distribution",),
    )
    scalings = document["views"]["distribution"]["scalings"]

    held = scalings["power"]["kinds"]["draft:held"]
    assert held["base"] == "minor" and held["pooled"]["n"] == 3
    assert set(held["campaigns"]["one"]) == {"first", "last", "all"}
    assert scalings["population"]["kinds"]["draft:moved"]["pooled"]["n"] == 1
    assert "draft:held - base minor" in render_views(document)


def test_a_sample_marked_non_standard_is_left_out_unless_asked_for() -> None:
    tables = {
        "std": spread((FIRST, SECOND), [0, 0, 0, 0, 0, 0]),
        "odd": spread((FIRST, SECOND), [30, 30, 30, 30, 30, 30]),
    }
    index = index_of(tables)
    marks = {"odd": ["research_speed"]}
    state = default_state(index)

    default = views_document(index, tables, None, state, views=("distribution",), non_standard=marks)
    included = views_document(
        index, tables, None, state, views=("distribution",), non_standard=marks, include_non_standard=True
    )

    view = default["views"]["distribution"]
    assert view["campaigns"] == ["std"] and view["left_out"] == {"odd": ["research_speed"]}
    assert list(view["scalings"]["power"]["kinds"][FIRST]["campaigns"]) == ["std"]
    assert "left out" in render_views(default) and "odd (research_speed)" in render_views(default)
    assert included["views"]["distribution"]["campaigns"] == ["std", "odd"]
    assert included["views"]["distribution"]["left_out"] == {"odd": ["research_speed"]}
    assert (
        included["views"]["distribution"]["scalings"]["power"]["kinds"][FIRST]["pooled"]["p90"]
        > view["scalings"]["power"]["kinds"][FIRST]["pooled"]["p90"]
    )


def test_the_world_quantity_of_a_measure_stands_beside_its_scaling() -> None:
    world = {"c": {"power": {"first": percentiles([0.01, 0.02, 0.4]), "last": percentiles([0.02]), "moved": None}}}
    tables = {"c": spread((FIRST, SECOND), [0, 0, 0, 0, 0, 0])}
    index = index_of(tables, world=world)
    document = views_document(index, tables, None, default_state(index), views=("distribution",))

    assert document["views"]["distribution"]["scalings"]["power"]["world"]["c"]["first"]["n"] == 3
    assert "world quantity - c" in render_views(document)


def test_extraction_records_the_world_quantity_of_the_first_and_last_save() -> None:
    world = extract_campaign(saves())["world"]

    assert "population" in world
    power_world = world["population"]
    assert power_world["first"]["n"] >= 2 and power_world["last"]["n"] >= 2
    assert power_world["first"]["p10"] <= power_world["first"]["p50"] <= power_world["first"]["p90"]
    assert power_world["moved"] is None or power_world["moved"]["p50"] > 0


def test_the_text_view_is_current(assert_golden: AssertGolden) -> None:
    name = "code"
    tables = {
        "std": spread((FIRST, SECOND), [-30, -12, -6, 0, 2, 4, 10, 40, 44]),
        "odd": spread((FIRST, SECOND), [30] * 6),
    }
    world = {
        "std": {
            "power": {
                "first": percentiles([0.002, 0.01, 0.03, 0.2]),
                "last": percentiles([0.01, 0.4]),
                "moved": percentiles([0.5, 1.0, 2.0]),
            }
        }
    }
    index = index_of(tables, world=world)
    document = views_document(
        index,
        tables,
        None,
        default_state(index),
        views=("distribution",),
        state_hash=name,
        non_standard={"odd": ["scenario"]},
    )

    assert_golden(render_views(document), GOLDEN / f"{name}.txt")
    assert_golden(json.dumps(document, indent=2) + "\n", GOLDEN / f"{name}.json")
