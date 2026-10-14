"""The unknowns registry: merge, prune, delta, canonical text and validation."""

import json
from datetime import date
from pathlib import Path

import pytest

from tinarrative.maintenance.registry import (
    NO_GAME_VERSION,
    PRIVACY_NOTE,
    EntryKey,
    Registry,
    RegistryEntry,
    RegistryError,
    Triage,
    TriageStatus,
    delta,
    dump,
    empty_registry,
    load_or_empty,
    load_registry,
    merge,
    prune_known,
    record,
    registry_from_document,
    validate_document,
    write_registry,
)
from tinarrative.parsing.unknowns import ShapeSummary, UnknownCollector, UnknownReport

DAY_ONE = date(2026, 10, 13)
DAY_TWO = date(2026, 10, 14)


def report(*fields: tuple[str, object], state_type: str = "TINationState") -> UnknownReport:
    collector = UnknownCollector()
    for name, value in fields:
        collector.field(state_type, name, value)
    return collector.report()


def key(field: str, state_type: str = "TINationState") -> EntryKey:
    return EntryKey("unknown_field", state_type, field, None)


def test_merge_creates_entries_from_one_save_and_keeps_untouched_entries() -> None:
    first = merge(empty_registry(), report(("alpha", 1), ("beta", {"x": 1})), game_version=None, today=DAY_ONE)
    assert [entry.key for entry in first.entries] == [key("alpha"), key("beta")]
    alpha = first.entries[0]
    assert (alpha.max_occurrences, alpha.saves_seen, alpha.first_seen, alpha.last_seen) == (1, 1, DAY_ONE, DAY_ONE)
    assert alpha.game_versions == (NO_GAME_VERSION,) and alpha.triage is None
    assert alpha.shape == ShapeSummary(("number",))

    second = merge(first, report(("beta", {"y": 1})), game_version="0.4.99", today=DAY_TWO)
    assert [entry.key for entry in second.entries] == [key("alpha"), key("beta")]
    assert second.entries[0] == alpha  # not mentioned by the second save: untouched
    beta = second.entries[1]
    assert (beta.max_occurrences, beta.saves_seen, beta.first_seen, beta.last_seen) == (1, 2, DAY_ONE, DAY_TWO)
    assert beta.shape == ShapeSummary(("object",), ("x", "y"))
    assert beta.game_versions == ("0.4.99", NO_GAME_VERSION)


def test_re_merging_the_same_save_keeps_the_per_save_maximum() -> None:
    collector = UnknownCollector()
    for _ in range(3):
        collector.field("TINationState", "alpha", 1)
    big = collector.report()
    registry = merge(empty_registry(), big, game_version=None, today=DAY_ONE)
    registry = merge(registry, big, game_version=None, today=DAY_ONE)
    registry = merge(registry, report(("alpha", 1)), game_version=None, today=DAY_ONE)
    (entry,) = registry.entries
    assert entry.max_occurrences == 3 and entry.saves_seen == 3


def test_triage_survives_merge_and_prune() -> None:
    triaged = RegistryEntry(
        key("alpha"), None, 1, 1, DAY_ONE, DAY_ONE, (NO_GAME_VERSION,), Triage(TriageStatus.INVESTIGATING, "why", "#8")
    )
    registry = Registry(entries=(triaged,))
    merged = merge(registry, report(("alpha", 1), ("beta", 1)), game_version=None, today=DAY_TWO)
    assert merged.entries[0].triage == triaged.triage and merged.entries[0].shape == ShapeSummary(("number",))
    pruned, dropped = prune_known(merged, lambda finding_key: finding_key[2] == "beta")
    assert dropped == (key("beta"),)
    assert [entry.key for entry in pruned.entries] == [key("alpha")] and pruned.entries[0].triage == triaged.triage


def test_delta_reports_added_updated_and_pruned_keys_only() -> None:
    before = merge(empty_registry(), report(("alpha", 1), ("gone", 1)), game_version=None, today=DAY_ONE)
    after = merge(before, report(("alpha", 1), ("new", 1)), game_version=None, today=DAY_TWO)
    after, _ = prune_known(after, lambda finding_key: finding_key[2] == "gone")
    changes = delta(before, after)
    assert changes.added == (key("new"),)
    assert changes.updated == (key("alpha"),)
    assert changes.pruned == (key("gone"),)
    assert changes.changed is True
    assert delta(before, before).changed is False


def test_dump_is_canonical_and_round_trips(tmp_path: Path) -> None:
    registry = merge(empty_registry(), report(("alpha", 1), ("beta", [{"k": 1}])), game_version=None, today=DAY_ONE)
    registry = Registry(registry.format, DAY_ONE, registry.entries)
    text = dump(registry)
    assert text.endswith("\n") and text.isascii()
    assert json.loads(text) == registry.to_document()
    assert list(json.loads(text)) == ["schema_version", "format", "last_scan", "privacy_note", "entries"]
    assert list(json.loads(text)["entries"][0]) == [
        "kind",
        "state_type",
        "field",
        "detail",
        "shape",
        "max_occurrences",
        "saves_seen",
        "first_seen",
        "last_seen",
        "game_versions",
    ]
    path = tmp_path / "nested" / "registry.json"
    write_registry(path, registry)
    assert path.read_text(encoding="utf-8") == text
    assert load_registry(path) == registry
    assert dump(load_registry(path)) == text
    assert dump(registry_from_document(json.loads(text))) == text
    assert load_or_empty(tmp_path / "absent.json") == empty_registry()
    assert validate_document(json.loads(text)) == []


def test_empty_registry_dumps_an_empty_entry_list() -> None:
    text = dump(empty_registry())
    assert json.loads(text) == {
        "schema_version": 1,
        "format": "terra_invicta_json_v1",
        "last_scan": None,
        "privacy_note": PRIVACY_NOTE,
        "entries": [],
    }


def _valid_document() -> dict[str, object]:
    registry = merge(empty_registry(), report(("alpha", {"k": 1})), game_version=None, today=DAY_ONE)
    document = registry.to_document()
    entries = document["entries"]
    assert isinstance(entries, list)
    entries[0]["triage"] = {"status": "open", "notes": ""}
    return document


@pytest.mark.parametrize(
    ("mutate", "problem"),
    [
        (lambda d: d.update(schema_version=2), "schema_version is not 1"),
        (lambda d: d.update(privacy_note="trimmed"), "privacy_note is missing or altered"),
        (lambda d: d.update(last_scan="yesterday"), "last_scan is neither null nor an ISO date"),
        (lambda d: d["entries"][0].update(kind="made_up"), "unknown kind"),
        (lambda d: d["entries"][0].update(state_type="Fixture Resistance"), "state_type is not a safe string"),
        (lambda d: d["entries"][0].update(field="has space"), "field is neither null nor a safe string"),
        (lambda d: d["entries"][0]["shape"].update(object_keys=["b", "a"]), "object_keys is not sorted and unique"),
        (lambda d: d["entries"][0]["shape"].update(types=["thing"]), "types has an unknown type label"),
        (lambda d: d["entries"][0].update(max_occurrences=-1), "max_occurrences is not a non-negative integer"),
        (lambda d: d["entries"][0].update(saves_seen=0), "saves_seen is not a positive integer"),
        (lambda d: d["entries"][0].update(first_seen="2026-13-01"), "first_seen is not an ISO date"),
        (lambda d: d["entries"][0].update(game_versions=[]), "game_versions is empty"),
        (lambda d: d["entries"][0]["triage"].update(status="done"), "triage status is not one of"),
        (lambda d: d["entries"].append(dict(d["entries"][0])), "entries repeat a key"),
        (lambda d: d.update(extra=1), "document keys are not"),
    ],
)
def test_validate_document_rejects_bad_registries(mutate, problem: str) -> None:  # type: ignore[no-untyped-def]
    document = _valid_document()
    assert validate_document(document) == []
    mutate(document)
    problems = validate_document(document)
    assert any(problem in item for item in problems), problems
    with pytest.raises(RegistryError, match="not a valid unknowns registry"):
        registry_from_document(document)


def test_unsorted_entries_are_rejected() -> None:
    registry = merge(empty_registry(), report(("beta", 1), ("alpha", 1)), game_version=None, today=DAY_ONE)
    document = registry.to_document()
    entries = document["entries"]
    assert isinstance(entries, list)
    entries.reverse()
    assert "entries are not sorted by kind, state_type, field, detail" in validate_document(document)


def test_duplicate_keys_cannot_be_constructed() -> None:
    entry = RegistryEntry(key("alpha"), None, 1, 1, DAY_ONE, DAY_ONE, (NO_GAME_VERSION,))
    with pytest.raises(RegistryError, match="repeat a key"):
        Registry(entries=(entry, entry))


def test_record_writes_prunes_and_rejects_other_formats(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    scans = [(report(("alpha", 1), ("GDP", 1)), None), (report(("alpha", 1)), None)]
    update = record(path, scans, today=DAY_ONE)
    # "GDP" is a copied field: pruned before it ever reaches the file, so it is neither added nor pruned.
    assert (update.added, update.updated, update.pruned, update.total) == (1, 0, 0, 1)
    registry = load_registry(path)
    assert registry.last_scan == DAY_ONE and [entry.key for entry in registry.entries] == [key("alpha")]
    assert registry.entries[0].saves_seen == 2

    again = record(path, scans[:1], today=DAY_TWO)
    assert (again.added, again.updated, again.pruned, again.total) == (0, 1, 0, 1)
    assert load_registry(path).entries[0].saves_seen == 3

    with pytest.raises(RegistryError, match="does not match"):
        record(path, scans, format="other_format", today=DAY_TWO)
    with pytest.raises(RegistryError, match="cannot read registry"):
        record(tmp_path, scans, today=DAY_TWO)
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    with pytest.raises(RegistryError, match="not valid JSON"):
        record(tmp_path / "bad.json", scans, today=DAY_TWO)
