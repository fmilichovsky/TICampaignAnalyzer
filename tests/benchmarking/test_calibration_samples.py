"""The calibration table extracts every sample campaign with a consistent row schema and replays to the pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.benchmarking.calibration_support import check_parity, check_rows
from tinarrative.benchmarking.calibration.replay import load

pytestmark = pytest.mark.samples


def test_a_sample_campaign_extracts_to_consistent_rows_that_replay_to_the_pipeline(calibration_table: Path) -> None:
    _, tables, drafts = load(calibration_table)
    [rows] = tables.values()
    [shadows] = drafts.values()

    check_rows(rows, shadows)
    check_parity(rows)
