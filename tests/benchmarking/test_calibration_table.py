"""The calibration table over the synthetic politics sequence: rows, wrapper files and the index."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.benchmark_support import synthetic_samples
from tests.benchmarking.calibration_support import check_rows
from tests.fixtures import fixture_path
from tests.narrative.support import atomic, faction, nation, situation, unification
from tinarrative.benchmarking.calibration.table import (
    SCHEMA_VERSION,
    CalibrationTableError,
    _row,
    build_index,
    explained_by,
    extract_all,
    extract_campaign,
    name_history,
    read_campaign,
    read_index,
    type_kinds,
    write_campaign,
)
from tinarrative.benchmarking.manifest import MANIFEST, extractable_campaigns, prefix_of
from tinarrative.kinds import KINDS
from tinarrative.kinds.registry import kind_for
from tinarrative.model.events import SIGNIFICANCE_ORDER, Role
from tinarrative.narrative import NARRATIVE_RULES, default_member_gates
from tinarrative.narrative.measures import MEASURES
from tinarrative.narrative.significance import decide
from tinarrative.sequence import narrative_events, plan_sequence, run_sequence, survey

SEQUENCE = ("politics_before.json", "politics_after.json", "politics_reverted.json")


def saves() -> list[Path]:
    return [fixture_path("io", "terra_invicta_json_v1", name) for name in SEQUENCE]


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    return extract_campaign(saves())["events"]


def test_every_event_becomes_a_row_with_its_own_score_and_level(rows: list[dict]) -> None:
    intervals = list(run_sequence(plan_sequence([survey(path) for path in saves()]), inferred=True))
    events = [event for interval in intervals for event in interval.events()] + narrative_events(intervals)

    assert [row["id"] for row in rows].count(events[0].id) == 1
    assert sorted(row["id"] for row in rows) == sorted(event.id for event in events)
    expected = {event.id: (event.score, event.significance.value) for event in events}
    assert {row["id"]: (row["score"], row["level"]) for row in rows} == expected
    assert {row["id"]: row["rule"] for row in rows} == {event.id: event.context_rule for event in events}
    check_rows(rows)


def test_a_share_row_keeps_the_unrounded_share(rows: list[dict]) -> None:
    shares = [share["share"] for row in rows for share in row["shares"]]

    assert all(isinstance(share, float) for share in shares)
    assert all(not row["shares"] or len(row["shares"]) == 1 for row in rows)


def test_a_campaign_file_round_trips_exactly(tmp_path: Path, rows: list[dict]) -> None:
    path = write_campaign(tmp_path, "politics", {"events": rows, "drafts": []})

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
    index = build_index(["politics"], key="k1", extracted_at="2030-01-01T00:00:00+00:00", kinds={})

    assert set(index) == {
        "names",
        "schema_version",
        "campaigns",
        "key",
        "extracted_at",
        "layers",
        "member_gates",
        "constants",
        "measures",
        "kinds",
        "drafts",
    }
    assert index["schema_version"] == SCHEMA_VERSION
    assert index["key"] == "k1"
    assert set(index["measures"]) == {measure.value for measure in MEASURES}
    assert {gate["member_type"] for gate in index["member_gates"]} == {
        gate.member_type for gate in default_member_gates().values()
    }
    emitted = {rule.name: sorted(rule.emitted_types) for rule in NARRATIVE_RULES}
    assert all(gate["group_types"] == emitted[gate["rule"]] for gate in index["member_gates"])
    assert index["layers"] and min(index["layers"].values()) >= 1
    assert index["constants"]["score_min"] == 0
    assert index["constants"]["score_max"] == 100
    assert index["constants"]["neighbours"] == 5
    assert index["constants"]["package_level"] in index["constants"]["level_bands"]


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
    index = read_index(out / "index.js")
    events = read_campaign(out / "tables" / "politics.js")["events"]
    assert index["campaigns"] == ["politics"]
    assert set(index["kinds"]) == {row["type"] for row in events}
    check_rows(events)


def test_the_kinds_map_holds_each_types_code_base_level_and_rule() -> None:
    ruled, plain = KINDS["councilor.appeared"], KINDS["faction.transaction_recorded"]
    kinds = type_kinds([ruled.event_type, plain.event_type, ruled.event_type])

    assert ruled.rule is not None and plain.rule is None
    assert kinds == {
        ruled.event_type: {"base": ruled.base.value, "rule": ruled.rule.value},
        plain.event_type: {"base": plain.base.value, "rule": None},
    }
    with pytest.raises(CalibrationTableError, match="no.such"):
        type_kinds(["no.such"])


def test_a_narrative_row_without_a_share_keeps_its_own_base_when_cited_events_raise_its_level() -> None:
    intervals = list(run_sequence(plan_sequence([survey(path) for path in saves()]), inferred=True))
    event = next(item for item in narrative_events(intervals) if item.significance_basis is None)
    own = decide(kind_for(event.event_type), event)[0]
    top = SIGNIFICANCE_ORDER[-1]
    # Through the row seam: no fixture has a share-less narrative event that its cited events raise.
    raised = _row(replace(event, significance=top, score=top.band[1]), "narrative")

    assert own is not top
    assert raised["base"] == own.base


def test_a_row_lists_its_entities_as_id_and_name_or_null() -> None:
    # Through the row seam: the plain label itself is covered in tests/kinds/test_plain_lines.py.
    named, unnamed = nation("20", "Northland"), nation("21")
    event = atomic(
        "nation.appeared/nation:20", "2032-01-01T00:00:00", entities=(named, unnamed), attributes=(("side", "after"),)
    )
    row = _row(event, "atomic")

    assert row["entities"] == [
        {"id": "nation:20", "name": "Northland", "role": None},
        {"id": "nation:21", "name": None, "role": None},
    ]


def test_a_narrative_row_names_each_entitys_role_the_target_count_and_its_interval_dates(rows: list[dict]) -> None:
    takeover = next(row for row in rows if row["id"].startswith("faction.takeover/nation:20/faction:15@"))
    claims = next(row for row in rows if row["id"].startswith("nation.claims_declared/"))
    atomic_row = next(row for row in rows if row["tier"] == "atomic")

    assert {entity["id"]: entity["role"] for entity in takeover["entities"]} == {
        "faction:15": "actor",
        "nation:20": "target",
        "faction:16": "loser",
    }
    assert takeover["targets"] == claims["targets"] == 1
    assert takeover["intervals"] == [
        {"key": "2032-04-01T00:00:00", "start": "2032-01-01T00:00:00", "end": "2032-04-01T00:00:00"}
    ]
    assert {entity["role"] for entity in atomic_row["entities"]} <= {None}
    assert atomic_row["targets"] is None
    assert [item["key"] for item in atomic_row["intervals"]] == [atomic_row["interval"]]


def test_a_multi_interval_row_lists_every_interval_with_its_own_dates(rows: list[dict]) -> None:
    wave = next(row for row in rows if len(row["intervals"]) > 1)

    assert all(item["start"] < item["end"] for item in wave["intervals"])
    assert [item["end"] for item in wave["intervals"]] == sorted(item["end"] for item in wave["intervals"])


def test_an_event_a_reading_or_a_shift_covers_is_explained_by_it() -> None:
    key = "2032-04-01T00:00:00"
    north, south, resistance = nation("20", "North"), nation("21", "South"), faction("15", "Resistance")
    gain = atomic("nation.territory_gained/nation:21", key, entities=(south,), attributes=(("counterparts", (north,)),))
    elsewhere = atomic("nation.territory_gained/nation:20", key, entities=(north,))
    reading = unification(key, south, north, not_before="2032-01-01T00:00:00")
    crossing = atomic(
        "nation.band_crossed/nation:20",
        key,
        entities=(north,),
        attributes=(("statistic", "unrest"),),
    )
    takeover = replace(
        atomic("faction.takeover/nation:20/faction:15", key, entities=(resistance, north)),
        intervals=(key,),
        roles=((Role.ACTOR, resistance), (Role.TARGET, north)),
    )

    found = explained_by([gain, elsewhere, crossing], [reading, takeover])

    assert found == {gain.id: reading.id, crossing.id: takeover.id}


def test_a_renamed_entity_lists_its_names_with_the_saves_that_show_them() -> None:
    old, new = nation("30", "Russia"), nation("30", "Eurasian Union")
    steady = nation("31", "Steady")
    reports = [
        situation("2032-01-01T00:00:00", nations=[old, steady]),
        situation("2032-04-01T00:00:00", nations=[old, steady]),
        situation("2032-07-01T00:00:00", nations=[new, steady]),
    ]

    assert name_history(reports) == {
        "nation:30": [
            {"name": "Russia", "first": "2032-01-01T00:00:00", "last": "2032-04-01T00:00:00"},
            {"name": "Eurasian Union", "first": "2032-07-01T00:00:00", "last": "2032-07-01T00:00:00"},
        ]
    }


def test_the_index_carries_each_campaigns_name_history() -> None:
    history = {"politics": {"nation:30": [{"name": "Russia", "first": "a", "last": "b"}]}}
    index = build_index(["politics"], key="k", extracted_at="t", kinds={}, names=history)

    assert index["names"] == history
    assert build_index(["politics"], key="k", extracted_at="t", kinds={})["names"] == {}
