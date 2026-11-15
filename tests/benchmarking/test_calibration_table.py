"""The calibration table over the synthetic politics sequence: rows, wrapper files and the index."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.benchmark_support import synthetic_samples
from tests.benchmarking.calibration_support import check_rows
from tests.fixtures import fixture_path
from tinarrative.benchmarking.calibration.table import (
    CalibrationTableError,
    build_index,
    extract_all,
    extract_campaign,
    read_campaign,
    read_index,
    write_campaign,
)
from tinarrative.benchmarking.manifest import MANIFEST, extractable_campaigns, prefix_of
from tinarrative.narrative import default_member_gates
from tinarrative.narrative.measures import MEASURES
from tinarrative.sequence import narrative_events, plan_sequence, run_sequence, survey

SEQUENCE = ("politics_before.json", "politics_after.json", "politics_reverted.json")


def saves() -> list[Path]:
    return [fixture_path("io", "terra_invicta_json_v1", name) for name in SEQUENCE]


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    return extract_campaign(saves())


def test_every_event_becomes_a_row_with_its_own_score_and_level(rows: list[dict]) -> None:
    intervals = list(run_sequence(plan_sequence([survey(path) for path in saves()]), inferred=True))
    events = [event for interval in intervals for event in interval.events()] + narrative_events(intervals)

    assert [row["id"] for row in rows].count(events[0].id) == 1
    assert sorted(row["id"] for row in rows) == sorted(event.id for event in events)
    expected = {event.id: (event.score, event.significance.value) for event in events}
    assert {row["id"]: (row["score"], row["level"]) for row in rows} == expected
    check_rows(rows)


def test_a_stake_row_keeps_the_unrounded_share(rows: list[dict]) -> None:
    shares = [stake["share"] for row in rows for stake in row["stakes"]]

    assert all(isinstance(share, float) for share in shares)
    assert all(not row["stakes"] or len(row["stakes"]) == 1 for row in rows)


def test_a_campaign_file_round_trips_exactly(tmp_path: Path, rows: list[dict]) -> None:
    path = write_campaign(tmp_path, "politics", rows)

    assert path.read_text(encoding="utf-8").startswith('window.TI_CALIBRATION.campaigns["politics"] = {')
    assert read_campaign(path) == {"events": json.loads(json.dumps(rows)), "drafts": []}


@pytest.mark.parametrize(
    "text",
    [
        "{}",
        'window.TI_CALIBRATION.campaigns["politics"] = {"events":[]}',
        'window.TI_CALIBRATION.campaigns["other"] = {"events":[]};',
        'window.TI_CALIBRATION.campaigns["politics"] = {"events":[;',
        'window.TI_CALIBRATION.campaigns["politics"] = [];',
    ],
)
def test_a_malformed_wrapper_fails_with_a_clear_error(tmp_path: Path, text: str) -> None:
    path = tmp_path / "politics.js"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(CalibrationTableError, match="politics.js"):
        read_campaign(path)


def test_the_index_carries_the_registry_the_rules_and_the_caller_key() -> None:
    index = build_index(["politics"], key="k1", extracted_at="2030-01-01T00:00:00+00:00")

    assert set(index) == {
        "schema_version",
        "campaigns",
        "key",
        "extracted_at",
        "layers",
        "member_gates",
        "constants",
        "measures",
        "drafts",
    }
    assert index["key"] == "k1"
    assert set(index["measures"]) == {measure.value for measure in MEASURES}
    assert {gate["member_type"] for gate in index["member_gates"]} == {
        gate.member_type for gate in default_member_gates().values()
    }
    assert index["layers"] and min(index["layers"].values()) >= 1
    assert index["constants"]["score_min"] == 0
    assert index["constants"]["score_max"] == 100


def test_extraction_writes_the_index_and_skips_a_prefix_campaign(tmp_path: Path) -> None:
    samples = synthetic_samples(tmp_path)
    manifest = json.loads((samples / MANIFEST).read_text(encoding="utf-8"))
    manifest["campaigns"]["politics"]["prefix_of"] = "longer"
    (samples / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    assert prefix_of(samples, "politics") == "longer"
    assert extractable_campaigns(samples) == {}

    del manifest["campaigns"]["politics"]["prefix_of"]
    (samples / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    out = tmp_path / "out"
    names = extract_all(samples, out, key="k", now=datetime(2030, 1, 1, tzinfo=UTC))

    assert names == ["politics"]
    assert read_index(out / "index.js")["campaigns"] == ["politics"]
    check_rows(read_campaign(out / "tables" / "politics.js")["events"])
