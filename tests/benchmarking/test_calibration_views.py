"""The package-shape views of the calibration report: periods, the tier rule, the deltas and the two count grids."""

from __future__ import annotations

import json
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from typing import Any

import pytest

from tests.benchmarking.calibration_support import (
    CONSTANTS,
    FIRST,
    GATE,
    GROUP,
    SECOND,
    base,
    members,
    power,
    row,
    saves,
    synthetic_kinds,
    with_oracle,
)
from tests.benchmarking.calibration_support import INDEX as SUPPORT_INDEX
from tests.fixtures import FIXTURES_ROOT
from tests.golden import AssertGolden
from tinarrative import cli
from tinarrative.benchmarking.calibration.readout import override_state
from tinarrative.benchmarking.calibration.replay import default_state, replay
from tinarrative.benchmarking.calibration.table import build_index, extract_campaign
from tinarrative.benchmarking.calibration.views import (
    TIERS,
    ViewError,
    campaign_periods,
    parse_views,
    render_views,
    row_tiers,
    views_document,
)
from tinarrative.config import NarratorSettings
from tinarrative.narrator.chapters import base_options, event_periods


def dated(item: dict[str, Any], start: str, end: str) -> dict[str, Any]:
    """``item`` in the interval from ``start`` to ``end``, keyed by its closing save."""
    return {**item, "interval": end, "intervals": [{"key": end, "start": start, "end": end}]}


GOLDEN = FIXTURES_ROOT / "benchmarking" / "calibration_views"
POWER_RISE = SUPPORT_INDEX["scalings"]["power"]["rise"]
SETTINGS = NarratorSettings(half_span_days=365)
"""Year periods for the short hand-built campaign."""
SAVES = ["2030-01-01T00:00:00", "2030-06-01T00:00:00", "2032-03-01T00:00:00", "2032-09-01T00:00:00"]


def spaced(rows: list[dict[str, Any]], positions: list[int]) -> list[dict[str, Any]]:
    return [dated(item, SAVES[at - 1], SAVES[at]) for item, at in zip(rows, positions, strict=True)]


def table() -> list[dict[str, Any]]:
    """A group in the package with its members, a top-level event citing a narrative and an atomic row, an explained
    row, a narrative row below the package and an atomic row nothing uses."""
    group = members("kept", [0.0] * GATE["minimum"])
    rows = [
        row("evidence", "atomic.thing"),
        row("unused", "atomic.thing"),
        row("explained", "atomic.band"),
        row("step", FIRST, tier="narrative", level="minor", cited=("evidence",)),
        row("quiet", FIRST, tier="narrative", level="trivial"),
        *group,
        row("headline", SECOND, tier="narrative", level="major", shares=power(0), cited=("step",)),
    ]
    rows[2] = {**rows[2], "explained_by": "headline"}
    positions = [1, 1, 1, 1, 3, *([3] * len(group)), 3]
    return spaced(rows, positions)


def index_of(tables: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return build_index(list(tables), key="views", extracted_at="", kinds=synthetic_kinds(tables))


def tiers_of(rows: list[dict[str, Any]], **state: Any) -> dict[str, tuple[str, str] | None]:
    index = index_of({"c": rows})
    result = replay(index, {"c": rows}, replace(default_state(index), **state))
    return {item["id"]: tier for item, tier in zip(rows, row_tiers(index, rows, result["campaigns"]["c"]), strict=True)}


def test_each_row_takes_the_first_tier_that_holds_and_unused_atomic_rows_are_not_counted() -> None:
    found = tiers_of(table())

    assert found["headline"] == ("major", "top-level")
    assert found["kept-group"] == ("major", "top-level")
    assert {found[f"kept-{n}"] for n in range(GATE["minimum"])} == {("major", "member")}
    assert found["step"] == ("minor", "cited only")
    assert found["evidence"] == ("minor", "cited only")
    assert found["explained"] == ("minor", "explained")
    assert found["quiet"] == ("trivial", "below")
    assert found["unused"] is None


def test_a_group_that_falls_apart_is_not_counted_and_keeps_no_members() -> None:
    top = (CONSTANTS["level_bands"]["campaign_defining"][0] - base("major")) - 1
    rows = spaced(with_oracle(members("gone", [top, *([0.0] * (GATE["minimum"] - 1))])), [1] * (GATE["minimum"] + 1))
    index = index_of({"c": rows})
    state = replace(default_state(index), rises={**default_state(index).rises, "power": POWER_RISE / 10**0.2})
    result = replay(index, {"c": rows}, state)
    found = dict(zip((item["id"] for item in rows), row_tiers(index, rows, result["campaigns"]["c"]), strict=True))

    assert [member["verdict"] for member in result["campaigns"]["c"]["members"]] == ["falls_apart"]
    assert found["gone-group"] is None
    # Its members stand on their own: none is a member any more.
    assert all(tier is not None and tier[1] != "member" for name, tier in found.items() if name != "gone-group")


def of_interval(found: Any) -> dict[str, str]:
    return {interval["key"]: label for interval, label in zip(found.intervals, found.labels, strict=True)}


def test_periods_follow_the_closing_save_fill_empty_years_and_mark_long_gaps_low_resolution() -> None:
    found = campaign_periods(table(), settings=SETTINGS)

    assert found.period == "year"
    assert found.keys == ("2030", "2031", "2032")
    assert of_interval(found) == {SAVES[1]: "2030", SAVES[2]: "2032", SAVES[3]: "2032"}
    # The 2030-06 to 2032-03 gap is 639 days and touches every year; the last interval is short but closes in 2032.
    assert dict(found.low_resolution) == {"2030": 639, "2031": 639, "2032": 639}


def test_a_requested_period_is_kept_and_a_derived_one_is_coarsened_where_saves_are_sparse() -> None:
    rows = [
        dated(row(f"r{n}", "atomic.thing"), start, end)
        for n, (start, end) in enumerate(zip(SAVES, SAVES[1:], strict=False))
    ]

    requested = campaign_periods(rows, "quarter")
    derived = campaign_periods(rows, settings=NarratorSettings(quarter_span_days=10_000))

    assert requested.requested and requested.coarsened == ()
    assert requested.keys[0] == "2030-Q2" and requested.keys[-1] == "2032-Q3" and len(requested.keys) == 10
    assert derived.period == "quarter" and not derived.requested
    assert derived.coarsened
    assert set(derived.labels) <= set(derived.keys)


def test_period_placement_is_narrates_on_the_fixture_sequence() -> None:
    rows = extract_campaign(saves())["events"]
    out = StringIO()
    with redirect_stdout(out):
        code = cli.main(["events", *map(str, saves()), "--narrative", "--constituents", "all", "--format", "json"])
    assert code == cli.EXIT_SUCCESS
    package = json.loads(out.getvalue())
    settings = NarratorSettings()
    for period in (None, "quarter", "year"):
        options = base_options(package, settings, period=period)
        narrate = event_periods(package, options, settings, requested=period is not None)
        found = campaign_periods(rows, period, settings)
        assert found.period == options["period"]
        placed = {item["id"]: found.of_row(item) for item in rows if item["id"] in narrate}
        assert {item["tier"] for item in rows if item["id"] in narrate} >= {"atomic", "narrative"}
        assert placed == narrate


def test_the_period_view_counts_every_period_with_deltas_only_away_from_the_codes_state() -> None:
    rows = table()
    tables = {"c": rows}
    index = index_of(tables)
    code = views_document(index, tables, None, default_state(index), views=("period",), settings=SETTINGS)
    lowered = override_state(default_state(index), index, bases=[f"{SECOND}=minor"])
    tried = views_document(index, tables, None, lowered, views=("period",), state_hash="h", settings=SETTINGS)

    campaign = code["views"]["period"]["campaigns"]["c"]
    assert code["code_state"] and [entry["key"] for entry in campaign["periods"]] == ["2030", "2031", "2032"]
    assert campaign["periods"][1]["grid"] == {}
    assert campaign["top_level"] == {"replay": 2, "code": 2}
    moved = tried["views"]["period"]["campaigns"]["c"]
    assert not tried["code_state"]
    assert moved["top_level"]["code"] == 2 and moved["top_level"]["replay"] < 2
    cells = [cell for entry in campaign["periods"] for cells in entry["grid"].values() for cell in cells.values()]
    assert all(cell["replay"] == cell["code"] for cell in cells)


@pytest.mark.parametrize("name", ["code", "lowered"])
def test_the_text_views_are_current(name: str, assert_golden: AssertGolden) -> None:
    tables = {"c": table()}
    index = index_of(tables)
    state = default_state(index)
    if name == "lowered":
        state = override_state(state, index, bases=[f"{SECOND}=minor"])
    document = views_document(index, tables, None, state, views=("period", "tiers"), state_hash=name, settings=SETTINGS)

    assert_golden(render_views(document), GOLDEN / f"{name}.txt")
    assert_golden(json.dumps(document, indent=2) + "\n", GOLDEN / f"{name}.json")


def test_a_period_filter_prints_only_its_periods_and_the_campaign_line_counts_the_full_window() -> None:
    tables = {"c": table()}
    index = index_of(tables)
    whole = views_document(index, tables, None, default_state(index), views=("period", "tiers"), settings=SETTINGS)
    only = views_document(
        index, tables, None, default_state(index), views=("period", "tiers"), periods=["2030"], settings=SETTINGS
    )

    campaign = only["views"]["period"]["campaigns"]["c"]
    assert [entry["key"] for entry in campaign["periods"]] == ["2030"]
    assert campaign["top_level"] == whole["views"]["period"]["campaigns"]["c"]["top_level"]
    assert set(only["views"]["tiers"]["types"]) < set(whole["views"]["tiers"]["types"])
    with pytest.raises(ViewError, match="unknown period"):
        views_document(
            index, tables, None, default_state(index), views=("period",), periods=["1999"], settings=SETTINGS
        )


def test_the_tiers_view_agrees_with_the_period_view_and_follows_the_type_filter() -> None:
    tables = {"c": table()}
    index = index_of(tables)
    document = views_document(index, tables, None, default_state(index), views=("period", "tiers"), settings=SETTINGS)

    def total(grids: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
        summed: dict[tuple[str, str], int] = {}
        for grid in grids:
            for level, cells in grid.items():
                for tier, cell in cells.items():
                    summed[level, tier] = summed.get((level, tier), 0) + cell["replay"]
        return summed

    periods = [entry["grid"] for entry in document["views"]["period"]["campaigns"]["c"]["periods"]]
    types = [entry["grid"] for entry in document["views"]["tiers"]["types"].values()]
    assert total(periods) == total(types)
    assert {tier for _, tier in total(types)} == set(TIERS)
    filtered = views_document(
        index, tables, None, replace(default_state(index), types=(GROUP,)), views=("period", "tiers")
    )
    assert list(filtered["views"]["tiers"]["types"]) == [GROUP]
    assert filtered["views"]["period"]["campaigns"]["c"]["rows"] == sum(1 for item in table() if item["type"] == GROUP)


def test_views_parse_comma_separated_and_repeated_flags_and_reject_unknown_ones() -> None:
    assert parse_views(["tiers", "period"]) == ("period", "tiers")
    assert parse_views(["period,tiers"]) == ("period", "tiers")
    with pytest.raises(ViewError, match="unknown view"):
        parse_views(["shape"])
    with pytest.raises(ViewError, match="twice"):
        parse_views(["period", "period"])
