"""Shared invariants of a calibration table, checked on the fixture sequence and on the sample campaigns."""

from __future__ import annotations

from typing import Any

from tinarrative.benchmarking.calibration.table import layers
from tinarrative.model.events import SCORE_BANDS, Significance

ROW_FIELDS = {
    "id",
    "type",
    "tier",
    "interval",
    "date",
    "label",
    "base",
    "stakes",
    "entities",
    "cited",
    "score",
    "level",
}


def check_rows(rows: list[dict[str, Any]]) -> None:
    """Every row has the schema, a score inside its level's band, and cites only rows of an earlier layer."""
    assert rows
    by_id = {row["id"]: row for row in rows}
    assert len(by_id) == len(rows)
    layer_of = layers()
    for row in rows:
        assert set(row) == ROW_FIELDS
        assert row["tier"] in {"atomic", "reconstructed", "narrative"}
        low, high = SCORE_BANDS[Significance(row["level"])]
        assert low <= row["score"] <= high
        if row["tier"] != "narrative":
            assert row["cited"] == []
        own = layer_of.get(row["type"], 0) if row["tier"] == "narrative" else 0
        for cited in row["cited"]:
            assert cited in by_id
            other = by_id[cited]
            assert (layer_of.get(other["type"], 0) if other["tier"] == "narrative" else 0) < own
