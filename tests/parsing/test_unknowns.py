"""Content-free detection of save structures outside the code-form schema."""

import json
import logging
import re
from pathlib import Path

import pytest

from tests.fixtures import fixture_path
from tinarrative.identity import ENTITY_DOMAINS, STATE_PREFIX
from tinarrative.io.save_loader import load_raw_save
from tinarrative.parsing.fields import (
    ACKNOWLEDGED_FIELDS,
    COMMON_FIELDS,
    ENTITY_FIELDS,
    KNOWN_FIELDS,
    PAIR_MAP_FIELDS,
    RECORD_FIELDS,
    RECORD_MEMBER_TARGETS,
    REFERENCE_FIELDS,
    SERIALIZATION_FIELDS,
    SINGLETON_FIELDS,
)
from tinarrative.parsing.inventory import KNOWN_STATE_TYPES, short_state_type
from tinarrative.parsing.unknowns import (
    MAX_ARRAY_ITEMS,
    MAX_OBJECT_KEYS,
    PAIR_MAP_VIOLATION,
    ShapeSummary,
    UnknownCollector,
    UnknownFinding,
    UnknownKind,
    UnknownReport,
    is_known,
    scan_envelope,
    scan_fields,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_SET = ("io", "terra_invicta_json_v1")
EMPTY_SHAPE = ShapeSummary(types=("number",))


def pair(map_id: int, **members: object) -> dict[str, object]:
    return {"Key": {"value": map_id}, "Value": {"ID": {"value": map_id}, **members}}


def only(report: UnknownReport) -> UnknownFinding:
    assert report.total == 1, report.findings
    return report.findings[0]


def test_shape_keeps_type_labels_and_identifier_keys_but_never_values() -> None:
    collector = UnknownCollector()
    collector.field("TIFactionState", "secretField", "Fixture Secret Value")
    collector.field("TIFactionState", "mixedKeys", {"alpha": 1, "Fixture Resistance": 2, "123": 3, "$type": "x"})
    collector.field("TIFactionState", "nullable", None)
    report = collector.report()
    rendered = json.dumps(report.to_dict())
    assert "Secret" not in rendered and "Fixture" not in rendered and "123" not in rendered
    secret, mixed, nullable = (dict(report.findings[index].to_dict()) for index in (2, 0, 1))
    assert secret["shape"] == {
        "types": ["string"],
        "object_keys": [],
        "object_keys_omitted": False,
        "array_item_types": [],
        "array_item_keys": [],
    }
    assert mixed["shape"]["object_keys"] == ["$type", "alpha"]
    assert mixed["shape"]["object_keys_omitted"] is True
    assert nullable["shape"]["types"] == ["null"]


def test_shape_bounds_keys_and_inspected_items() -> None:
    collector = UnknownCollector()
    collector.field("T", "wide", {f"key{index:03d}": index for index in range(MAX_OBJECT_KEYS + 8)})
    items: list[object] = [1] * MAX_ARRAY_ITEMS + [{"lateKey": 1}]
    collector.field("T", "long", items)
    collector.field("T", "mixed", [{"a": 1}, "text", None, [1]])
    report = collector.report()
    long_list, mixed, wide = (finding.shape for finding in report.findings)  # sorted by field name
    assert wide is not None and len(wide.object_keys) == MAX_OBJECT_KEYS and wide.object_keys_omitted
    assert wide.object_keys == tuple(f"key{index:03d}" for index in range(MAX_OBJECT_KEYS))
    assert long_list is not None and long_list.array_item_types == ("number",) and long_list.array_item_keys == ()
    assert mixed is not None and mixed.array_item_types == ("array", "null", "object", "string")
    assert mixed.array_item_keys == ("a",)


def test_shape_merge_is_a_bounded_union() -> None:
    one = ShapeSummary(types=("object",), object_keys=("a", "b"))
    two = ShapeSummary(types=("null",), object_keys=("b", "c"), array_item_types=("number",))
    merged = one.merge(two)
    assert merged == two.merge(one)
    assert merged == ShapeSummary(types=("null", "object"), object_keys=("a", "b", "c"), array_item_types=("number",))
    many = ShapeSummary(object_keys=tuple(f"k{index:03d}" for index in range(MAX_OBJECT_KEYS)))
    assert one.merge(many).object_keys_omitted is True
    assert ShapeSummary.from_dict(merged.to_dict()) == merged


def test_collector_output_is_order_independent_and_json_round_trips() -> None:
    def collect(order: tuple[int, ...]) -> UnknownReport:
        collector = UnknownCollector()
        actions = (
            lambda: collector.field("TINationState", "b", 1),
            lambda: collector.field("TINationState", "a", {"x": 1}),
            lambda: collector.field("TINationState", "a", {"y": 1}),
            lambda: collector.reference_domain("TINationState", "capital", "TIFactionState"),
            lambda: collector.singleton_count("TITimeState", 2),
            lambda: collector.container_shape("TIOrgState"),
            lambda: collector.envelope_key("mods", []),
        )
        for index in order:
            actions[index]()
        return collector.report()

    first = collect((0, 1, 2, 3, 4, 5, 6))
    second = collect((6, 5, 4, 3, 2, 1, 0))
    assert first == second
    assert [finding.key for finding in first.findings] == sorted(finding.key for finding in first.findings)
    assert first.total == 6
    assert first.counts()["unknown_field"] == 2 and first.counts()["unknown_state_type"] == 0
    data = first.to_dict()
    assert json.loads(json.dumps(data)) == data
    merged_field = next(finding for finding in first.findings if finding.field == "a")
    assert merged_field.occurrences == 2 and merged_field.shape == ShapeSummary(("object",), ("x", "y"))
    assert next(finding for finding in first.findings if finding.kind is UnknownKind.REFERENCE_DOMAIN).shape is None


def test_scan_envelope_reports_root_keys_and_state_types_outside_the_inventory() -> None:
    root: dict[str, object] = {
        "currentID": {"value": 1},
        "gamestates": {
            STATE_PREFIX + "TINationState": [pair(1, extra=1)],  # known type: not the envelope scan's business
            STATE_PREFIX + "TIFutureState": [pair(2, alpha=1), pair(3, beta=None)],
            "TIHistoricalData": {},  # bare key in the inventory
            "Mod.State": {},
        },
        "mods": ["Fixture Mod"],
    }
    collector = UnknownCollector()
    scan_envelope(root, collector)
    report = collector.report()
    assert [finding.key for finding in report.findings] == [
        ("unknown_envelope_key", "", "mods", ""),
        ("unknown_state_type", "Mod.State", "", ""),
        ("unknown_state_type", "TIFutureState", "", ""),
    ]
    envelope, mod, future = report.findings
    assert envelope.occurrences == 1 and envelope.shape == ShapeSummary(("array",), array_item_types=("string",))
    assert mod.occurrences == 0 and mod.shape == ShapeSummary(("object",))
    assert future.occurrences == 2
    assert future.shape == ShapeSummary(("object",), ("ID", "alpha", "beta"))
    assert "Fixture Mod" not in json.dumps(report.to_dict())


@pytest.mark.fixture
def test_unknown_state_type_fixture_is_reported_with_its_container_violation() -> None:
    raw = load_raw_save(fixture_path(*FIXTURE_SET, "unknown_state_type.json"))
    collector = UnknownCollector()
    scan_envelope(raw.root, collector)
    finding = only(collector.report())
    assert finding.kind is UnknownKind.STATE_TYPE
    assert finding.state_type == "Example.ModOrFutureState"
    assert finding.detail == PAIR_MAP_VIOLATION
    assert finding.shape is not None and finding.shape.types == ("array",)
    assert finding.shape.array_item_keys == ("Key", "Value")


@pytest.mark.fixture
def test_political_fixture_unknown_type_exposes_its_member_names() -> None:
    raw = load_raw_save(fixture_path(*FIXTURE_SET, "political_control.json"))
    collector = UnknownCollector()
    scan_envelope(raw.root, collector)
    finding = only(collector.report())
    assert finding.key == ("unknown_state_type", "TIFixtureUnknownState", "", "")
    assert finding.occurrences == 1
    assert finding.shape is not None
    assert finding.shape.object_keys == ("$type", "ID", "archived", "displayName", "exists", "templateName")


def test_scan_fields_skips_unscanned_types_and_known_members() -> None:
    collector = UnknownCollector()
    scan_fields("TIMissionState", {"anything": 1}, collector)  # not normalized: never scanned
    scan_fields("TISpaceShipState", {"fleet": 1, "$type": "x", "damagePoints": {}, "newField": 1}, collector)
    scan_fields("TITimeState", {"currentDateTime": {}, "archived": False, "nextTurn": 1}, collector)
    report = collector.report()
    assert [finding.key for finding in report.findings] == [
        ("unknown_field", "TISpaceShipState", "newField", ""),
        ("unknown_field", "TITimeState", "nextTurn", ""),
    ]
    assert collector.field_count("TISpaceShipState") == 1 and collector.field_count("TIMissionState") == 0


def test_log_summary_gives_counts_only(caplog: pytest.LogCaptureFixture) -> None:
    collector = UnknownCollector()
    collector.field("TINationState", "secretName", "Fixture Value")
    collector.field("TINationState", "other", 1)
    collector.entity_with_unknown_fields("TINationState")
    with caplog.at_level(logging.DEBUG, logger="tinarrative"):
        collector.log_summary()
    assert (
        "INFO tinarrative.parsing.unknowns: unknown structures total=2 state_types=0 fields=2 envelope_keys=0 "
        "field_shapes=0 reference_domains=0 singletons=0 containers=0"
    ) in [f"{record.levelname} {record.name}: {record.getMessage()}" for record in caplog.records]
    assert "unknown fields state_type=TINationState fields=2 entities=1" in caplog.text
    assert "secretName" not in caplog.text and "Fixture" not in caplog.text


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (("unknown_state_type", "TINationState", "", ""), True),
        (("unknown_state_type", "TIHistoricalData", "", ""), True),
        (("unknown_state_type", "TIFixtureUnknownState", "", ""), False),
        (("unknown_envelope_key", "", "currentID", ""), True),
        (("unknown_envelope_key", "", "mods", ""), False),
        (("unknown_field", "TINationState", "GDP", ""), True),
        (("unknown_field", "TINationState", "$type", ""), True),
        (("unknown_field", "TISpaceShipState", "damagePoints", ""), True),
        (("unknown_field", "TINationState", "fixtureOnlyUndocumentedField", ""), False),
        (("unknown_field", "TIFactionState", "Transactions", ""), True),
        (("unknown_field", "TINationState", "lastExecutiveChange", ""), True),
        (("unexpected_field_shape", "TIFactionState", "Transactions", "object"), False),
        (("unexpected_field_shape", "TIFactionState", "Kills", "pair_map"), False),
        (("unexpected_reference_domain", "TIFactionState", "knownAlienSites", "TIRegionState"), True),
        (("unexpected_reference_domain", "TIFactionState", "knownAlienSites", "TIHabState"), True),
        (("unexpected_reference_domain", "TIFactionState", "knownAlienSites", "TIFactionState"), False),
        (("unexpected_reference_domain", "TIFactionState", "lostControlPoints", "TINationState"), False),
        (("unexpected_reference_domain", "TIFactionState", "HabDestructionLog.Destroyer", "TINationState"), False),
        (("unexpected_reference_domain", "TIFactionState", "HabDestructionLog.Destroyer", "TIFactionState"), True),
        (("unexpected_reference_domain", "TIFactionState", "milestones", "TINationState"), True),
        (("unexpected_reference_domain", "TINationState", "lastExecutiveChange.newExecutive", "TINationState"), False),
        (("unexpected_reference_domain", "TINationState", "HabDestructionLog.Destroyer", "TINationState"), True),
        (("unexpected_reference_domain", "TICouncilorState", "location", "TISpaceShipState"), True),
        (("unexpected_reference_domain", "TICouncilorState", "assassinations", "TINationState"), False),
        (("unexpected_reference_domain", "TICouncilorState", "assassinations", "TIFactionState"), True),
        (("unexpected_field_shape", "TICouncilorState", "assassinations", "pair_map"), False),
        (("unexpected_reference_domain", "TINationState", "factionUnrestAttempts", "TINationState"), False),
        (("unexpected_reference_domain", "TINationState", "tracker_PCGDP_ByQuarter", "TINationState"), True),
        (("unexpected_field_shape", "TINationState", "tracker_PCGDP_ByQuarter", "pair_map"), False),
        (("unknown_field", "TIMissionState", "anything", ""), True),  # no longer scanned: cannot recur
        (("unexpected_field_shape", "TINationState", "regions", "array_of_references"), False),
        (("unexpected_field_shape", "TINationState", "notAField", "array"), True),
        (("unexpected_field_shape", "TISpaceShipState", "damagePoints", "array"), True),
        (("unexpected_reference_domain", "TINationState", "capital", "TIFactionState"), False),
        (("unexpected_reference_domain", "TINationState", "capital", "TIRegionState"), True),
        (("unexpected_reference_domain", "TINationState", "GDP", "TIRegionState"), True),
        (("unexpected_reference_domain", "TINationState", "capital", "TIMissionState"), False),
        (("unexpected_reference_domain", "TISpaceFleetState", "displayNameByFaction", "TINationState"), False),
        (("unexpected_reference_domain", "TISpaceFleetState", "currentOperations", "TIHabState"), True),  # raw
        (("unexpected_singleton_count", "TITimeState", "", ""), False),
        (("unexpected_singleton_count", "TINationState", "", ""), True),
        (("unexpected_container_shape", "TIOrgState", "", PAIR_MAP_VIOLATION), False),
        (("unexpected_container_shape", "TIWarState", "", PAIR_MAP_VIOLATION), False),
        (("unexpected_container_shape", "TIMissionState", "", PAIR_MAP_VIOLATION), True),
        (("made_up_kind", "TINationState", "", ""), False),
    ],
)
def test_is_known_says_whether_the_schema_can_still_produce_a_finding(key: tuple[str, str, str, str], expected: bool):
    assert is_known(key) is expected


def test_schema_tables_are_consistent() -> None:
    for state_type, acknowledged in ACKNOWLEDGED_FIELDS.items():
        assert state_type in ENTITY_FIELDS or state_type in SINGLETON_FIELDS
        copied = ENTITY_FIELDS.get(state_type, COMMON_FIELDS + SINGLETON_FIELDS.get(state_type, ()))
        assert not set(acknowledged) & set(copied)
        assert not set(acknowledged) & set(SERIALIZATION_FIELDS)
    for state_type, copied in ENTITY_FIELDS.items():
        assert not set(SERIALIZATION_FIELDS) & set(copied)
        assert KNOWN_FIELDS[state_type] >= set(copied) | set(SERIALIZATION_FIELDS)
    for state_type, records in RECORD_FIELDS.items():
        assert state_type in ENTITY_FIELDS
        assert not set(records) & set(ENTITY_FIELDS[state_type])
        assert not set(records) & set(ACKNOWLEDGED_FIELDS.get(state_type, {}))
        assert not set(records) & set(SERIALIZATION_FIELDS)
        assert not set(records) & set(REFERENCE_FIELDS.get(state_type, {}))
        assert KNOWN_FIELDS[state_type] >= set(records)
    for state_type, pair_maps in PAIR_MAP_FIELDS.items():
        assert set(pair_maps) <= set(ENTITY_FIELDS[state_type])
        assert not set(pair_maps) & set(REFERENCE_FIELDS.get(state_type, {}))
    for qualified in RECORD_MEMBER_TARGETS:
        field, _member = qualified.split(".", 1)
        assert any(field in records for records in RECORD_FIELDS.values())
    for state_type in (*ENTITY_FIELDS, *SINGLETON_FIELDS):
        assert STATE_PREFIX + state_type in KNOWN_STATE_TYPES
    for strategy in ENTITY_DOMAINS:
        for state_type in strategy.state_types:
            assert STATE_PREFIX + state_type in KNOWN_STATE_TYPES
    assert short_state_type(STATE_PREFIX + "TINationState") == "TINationState"
    assert short_state_type("TIHistoricalData") == "TIHistoricalData"


def test_known_state_types_match_the_documented_inventory() -> None:
    text = (REPO_ROOT / "docs" / "game-data-notes" / "state-type-inventory.md").read_text(encoding="utf-8")
    documented = {
        line.strip()
        for block in re.findall(r"```text\n(.*?)```", text, re.S)
        for line in block.splitlines()
        if line.strip()
    }
    assert documented == set(KNOWN_STATE_TYPES)
    assert len(KNOWN_STATE_TYPES) == 76
