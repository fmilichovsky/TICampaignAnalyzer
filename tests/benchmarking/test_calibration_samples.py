"""The calibration table extracts every sample campaign with a consistent row schema, replays to the pipeline, and
replays the same in the browser."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from tests.benchmarking.browser_replay import assert_readouts_agree, assert_replays_agree
from tests.benchmarking.calibration_support import check_parity, check_rows
from tinarrative.benchmarking.calibration.replay import default_state, load

pytestmark = pytest.mark.samples


def test_a_sample_campaign_extracts_to_consistent_rows_that_replay_to_the_pipeline(calibration_table: Path) -> None:
    _, tables, drafts = load(calibration_table)
    [rows] = tables.values()
    [shadows] = drafts.values()

    check_rows(rows, shadows)
    check_parity(rows)


@pytest.mark.browser_replay
def test_replay_js_and_readout_js_match_python_on_a_sample_campaign(calibration_table: Path) -> None:
    index, tables, _ = load(calibration_table)
    [rows] = tables.values()
    code = default_state(index)
    references = code.references

    def moved(**factors: float) -> dict[str, float]:
        return {**references, **{measure: references[measure] * factor for measure, factor in factors.items()}}

    others = {measure: 10**-0.5 for measure in references if measure != "power"}
    common = Counter(row["type"] for row in rows if row["tier"] == "narrative").most_common(1)[0][0]
    states = [
        code,
        replace(code, references={**references, "power": 0.002}),
        replace(code, references=moved(power=10**0.5)),
        replace(code, references=moved(power=10**-0.5)),
        replace(code, references=moved(**others)),
        replace(code, clamp=False),
        replace(code, clamp=False, references=moved(power=10**-2)),
        replace(code, types=(common,)),
    ]

    assert_replays_agree(calibration_table, states)
    assert_readouts_agree(calibration_table, states)
