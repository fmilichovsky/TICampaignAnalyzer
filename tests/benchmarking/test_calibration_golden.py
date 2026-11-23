"""The golden calibration table is current, and holds the cases the replay and server tests rely on."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tests.benchmarking.calibration_golden import GOLDEN, golden_index, golden_tables
from tests.golden import AssertGolden
from tinarrative.benchmarking.calibration.replay import (
    SCHEMA_VERSION,
    ReplayError,
    cutoff_offsets,
    default_state,
    load,
    replay,
)
from tinarrative.benchmarking.calibration.table import write_campaign, write_index


def test_the_golden_calibration_table_is_current(assert_golden: AssertGolden, tmp_path: Path) -> None:
    write_index(tmp_path, golden_index())
    for name, document in golden_tables().items():
        write_campaign(tmp_path, name, document)

    for path in sorted(tmp_path.rglob("*.js")):
        assert_golden(path.read_text(encoding="utf-8"), GOLDEN / path.relative_to(tmp_path))


def test_the_golden_table_moves_members_and_cut_offs_when_the_state_changes() -> None:
    index, tables, _ = load(GOLDEN)
    code = default_state(index)
    power = code.references["power"]

    def verdicts(factor: float) -> set[str]:
        state = replace(code, references={**code.references, "power": power * factor})
        return {member["verdict"] for member in replay(index, tables, state)["campaigns"]["alpha"]["members"]}

    assert verdicts(1.0) == {"keeps_members"}
    assert verdicts(10**-0.2) == {"keeps_members", "loses_members", "falls_apart"}
    assert "could_become_member" in verdicts(10**0.5)
    assert len(replay(index, tables, code)["cutoffs"]["power"]) == len(cutoff_offsets())
    assert {event["decided_by"] for event in replay(index, tables, code)["campaigns"]["alpha"]["events"]} > {"land"}


def test_a_table_at_the_previous_schema_is_refused_with_the_rebuild_hint(tmp_path: Path) -> None:
    index, tables, _ = load(GOLDEN)
    old = {**index, "schema_version": index["schema_version"] - 1}
    write_index(tmp_path, old)
    for name, document in golden_tables().items():
        write_campaign(tmp_path, name, document)

    with pytest.raises(ReplayError, match=rf"schema {SCHEMA_VERSION - 1}.*calibrate report --rebuild"):
        load(tmp_path)
