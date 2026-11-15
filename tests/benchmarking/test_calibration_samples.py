"""The calibration table extracts every sample campaign with a consistent row schema, and replays to the pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.benchmarking.calibration_support import check_parity, check_rows
from tests.samples import SAMPLES, save_paths
from tinarrative.benchmarking.calibration.table import extract_campaign
from tinarrative.benchmarking.manifest import prefix_of

pytestmark = pytest.mark.samples


def test_a_sample_campaign_extracts_to_consistent_rows_that_replay_to_the_pipeline(
    sample_campaign: Path, request: pytest.FixtureRequest
) -> None:
    if prefix_of(SAMPLES, request.node.callspec.params["sample_campaign"]) is not None:
        pytest.skip("a prefix campaign is never extracted")

    rows = extract_campaign(save_paths(sample_campaign))

    check_rows(rows)
    check_parity(rows)
