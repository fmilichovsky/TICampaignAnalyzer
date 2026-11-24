"""The calibration table extracts every sample campaign with a consistent row schema and replays to the pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.benchmarking.calibration_support import (
    check_cached_answers,
    check_parity,
    check_rows,
    page_session,
    random_states,
)
from tinarrative.benchmarking.calibration.replay import load

pytestmark = pytest.mark.samples


def test_a_sample_campaign_extracts_to_consistent_rows_that_replay_to_the_pipeline(calibration_table: Path) -> None:
    _, tables, drafts = load(calibration_table)
    [rows] = tables.values()
    [shadows] = drafts.values()

    check_rows(rows, shadows)
    check_parity(rows)


def test_a_long_lived_server_answers_a_sample_campaign_as_a_fresh_server_does(calibration_table: Path) -> None:
    index, tables, _ = load(calibration_table)

    session = page_session(index, tables)
    # Every few sweep steps, for the run time, then every state after the sweep.
    bodies = [*session[:13:3], *session[13:], *random_states(index, tables, 683, 3)]

    check_cached_answers(calibration_table, bodies)
