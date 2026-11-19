"""The golden calibration table is current, and holds the cases the replay and server tests rely on."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tests.benchmarking.calibration_golden import GOLDEN, golden_index, golden_tables
from tests.golden import AssertGolden
from tinarrative.benchmarking.calibration.replay import cutoff_offsets, default_state, load, replay
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
    free = replay(index, tables, replace(code, clamp=False))["cutoffs"]["power"]
    assert len(free) > len(cutoff_offsets(index["constants"], clamp=True))
    assert {event["decided_by"] for event in replay(index, tables, code)["campaigns"]["alpha"]["events"]} > {"land"}
