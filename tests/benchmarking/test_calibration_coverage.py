"""Coverage labels: occurrences per campaign of each event type and measure, and which of them read thin."""

from __future__ import annotations

from typing import Any

import pytest

from tests.benchmarking.calibration_support import row
from tinarrative.benchmarking.calibration.coverage import THIN_TOTAL, coverage, coverage_label

INDEX: dict[str, Any] = {
    "kinds": {"a.many": {}, "a.once": {}, "a.few": {}, "a.none": {}},
    "measures": {"power": {}, "fleet": {}, "nuclear": {}},
}


def _rows(prefix: str, count: int, type: str, *shares: tuple[str, float]) -> list[dict[str, Any]]:
    return [row(f"{prefix}{type}{n}", type, shares=shares) for n in range(count)]


def test_the_label_is_thin_for_one_campaign_or_a_small_total() -> None:
    assert coverage_label({}) == "thin"
    assert coverage_label({"one": 40, "two": 0}) == "thin"
    assert coverage_label({"one": 2, "two": 2}) == "thin"
    assert coverage_label({"one": THIN_TOTAL - 1}) == "thin"
    assert coverage_label({"one": 4, "two": 1}) == "covered"
    assert coverage_label({"one": 1, "two": 4}) == "covered"


def test_a_type_is_thin_by_campaign_count_and_by_total() -> None:
    tables = {
        "one": _rows("1", 6, "a.many") + _rows("1", 9, "a.once") + _rows("1", 2, "a.few"),
        "two": _rows("2", 5, "a.many") + _rows("2", 2, "a.few"),
    }

    types = coverage(INDEX, tables)["types"]

    assert types["a.many"] == {"campaigns": {"one": 6, "two": 5}, "total": 11, "label": "covered"}
    assert types["a.once"] == {"campaigns": {"one": 9, "two": 0}, "total": 9, "label": "thin"}, "one campaign only"
    assert types["a.few"] == {"campaigns": {"one": 2, "two": 2}, "total": 4, "label": "thin"}, "fewer than 5 in total"
    assert types["a.none"]["total"] == 0 and types["a.none"]["label"] == "thin"


def test_a_measure_counts_the_rows_that_carry_a_share_on_it() -> None:
    tables = {
        "one": _rows("1", 5, "a.many", ("power", 0.1)) + _rows("1", 5, "a.once", ("fleet", 0.2)),
        "two": _rows("2", 5, "a.many", ("power", 0.3), ("fleet", 0.1)) + _rows("2", 3, "a.few"),
    }

    measures = coverage(INDEX, tables)["measures"]

    assert measures["power"] == {"campaigns": {"one": 5, "two": 5}, "total": 10, "label": "covered"}
    assert measures["fleet"] == {"campaigns": {"one": 5, "two": 5}, "total": 10, "label": "covered"}
    assert measures["nuclear"] == {"campaigns": {"one": 0, "two": 0}, "total": 0, "label": "thin"}


@pytest.mark.parametrize("campaigns", [{"only": 7}, {"a": 1, "b": 1}])
def test_the_threshold_is_five_occurrences(campaigns: dict[str, int]) -> None:
    assert THIN_TOTAL == 5
    assert coverage_label(campaigns) == "thin"
