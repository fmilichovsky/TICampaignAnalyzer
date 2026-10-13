"""Scanning files and directories for unknown structures, and recording the result."""

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from tests.fixtures import fixture_path
from tinarrative.maintenance.registry import dump, load_registry, record
from tinarrative.maintenance.scan import EMPTY_DIRECTORY, expand_inputs, merge_reports, scan_inputs, scan_save
from tinarrative.parsing.unknowns import ShapeSummary, UnknownCollector

FIXTURE_SET = ("io", "terra_invicta_json_v1")
FIXTURES = ("political_control.json", "campaign_assets.json", "malformed_truncated.json", "unknown_state_type.json")


@pytest.fixture
def save_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "saves"
    directory.mkdir()
    (directory / "nested").mkdir()
    for name in FIXTURES:
        shutil.copy(fixture_path(*FIXTURE_SET, name), directory / name)
    shutil.copy(fixture_path(*FIXTURE_SET, "political_control.json"), directory / "nested" / "ignored.json")
    return directory


@pytest.mark.fixture
def test_expand_inputs_is_sorted_and_one_level_deep(save_dir: Path, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    inputs = expand_inputs([save_dir, tmp_path / "missing.json", empty])
    assert [(item.path.name, item.explicit, item.empty_directory) for item in inputs] == [
        ("campaign_assets.json", False, False),
        ("malformed_truncated.json", False, False),
        ("political_control.json", False, False),
        ("unknown_state_type.json", False, False),
        ("missing.json", True, False),
        ("empty", True, True),
    ]


@pytest.mark.fixture
def test_scan_inputs_continues_past_failures(save_dir: Path, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    run = scan_inputs(expand_inputs([save_dir, tmp_path / "missing.json", empty]))
    by_name = {result.path.name: result for result in run.results}
    assert by_name["political_control.json"].scanned and by_name["political_control.json"].report is not None
    assert by_name["political_control.json"].report.total == 2
    assert by_name["campaign_assets.json"].report is not None and by_name["campaign_assets.json"].report.total == 0
    malformed = by_name["malformed_truncated.json"]
    assert not malformed.scanned and malformed.error_class == "MalformedSaveError" and not malformed.input_error
    missing = by_name["missing.json"]
    assert missing.error_class == "FileNotFoundError" and missing.input_error and missing.explicit
    assert by_name["empty"].error_class == EMPTY_DIRECTORY and by_name["empty"].input_error
    assert len(run.scanned) == 3
    assert [merged.finding.key for merged in run.findings] == [
        ("unknown_field", "TINationState", "fixtureOnlyUndocumentedField", ""),
        ("unknown_state_type", "Example.ModOrFutureState", "", "pair_map_violation"),
        ("unknown_state_type", "TIFixtureUnknownState", "", ""),
    ]
    assert all(merged.saves == 1 for merged in run.findings)
    assert [game_version for _, game_version in run.scans()] == [None, None, None]


def test_merge_reports_sums_occurrences_unions_shapes_and_counts_saves() -> None:
    def one(value: object) -> UnknownCollector:
        collector = UnknownCollector()
        collector.field("TINationState", "alpha", value)
        return collector

    merged = merge_reports([one({"x": 1}).report(), one({"y": 1}).report(), UnknownCollector().report()])
    (item,) = merged
    assert item.saves == 2 and item.finding.occurrences == 2
    assert item.finding.shape == ShapeSummary(("object",), ("x", "y"))


@pytest.mark.fixture
def test_scan_save_matches_parse(save_dir: Path) -> None:
    report, game_version = scan_save(save_dir / "political_control.json")
    assert game_version is None and report.total == 2


@pytest.mark.fixture
def test_record_from_a_scan_is_canonical_and_names_no_files(save_dir: Path, tmp_path: Path) -> None:
    run = scan_inputs(expand_inputs([save_dir]))
    registry_path = tmp_path / "registry.json"
    first = record(registry_path, run.scans(), today=date(2026, 10, 13))
    assert (first.added, first.pruned, first.total) == (3, 0, 3)
    text = registry_path.read_text(encoding="utf-8")
    assert dump(load_registry(registry_path)) == text
    assert str(tmp_path) not in text and "political_control" not in text and "Fixture Resistance" not in text
    second = record(registry_path, run.scans(), today=date(2026, 10, 13))
    assert (second.added, second.updated, second.pruned, second.total) == (0, 3, 0, 3)
    after = json.loads(registry_path.read_text(encoding="utf-8"))
    assert {entry["saves_seen"] for entry in after["entries"]} == {2}
    assert {entry["max_occurrences"] for entry in after["entries"]} == {1}
