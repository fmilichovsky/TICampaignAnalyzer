"""Golden-output, exit-code and logging coverage for ``tinarrative diff``."""

import json
from pathlib import Path

import pytest

from tests.fixtures import FIXTURES_ROOT, fixture_path
from tinarrative.cli import EXIT_INPUT_ERROR, EXIT_SUCCESS, EXIT_UNSUPPORTED_INPUT, EXIT_USAGE_ERROR, main

FIXTURE_SET = "terra_invicta_json_v1"
FIXTURE_DIR = FIXTURES_ROOT / "io" / FIXTURE_SET
EXPECTED_ROOT = FIXTURES_ROOT / "diff"
GOLDEN_PAIRS = [("interval_before.json", "interval_after.json"), ("records_before.json", "records_after.json")]


def golden_path(before: str, after: str, suffix: str) -> Path:
    return EXPECTED_ROOT / FIXTURE_SET / f"{before}__{after}.expected.{suffix}"


@pytest.mark.parametrize(("before", "after"), GOLDEN_PAIRS)
@pytest.mark.parametrize("fmt", ["txt", "json"])
def test_diff_matches_the_golden_report(
    before: str, after: str, fmt: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(FIXTURE_DIR)  # bare file names keep machine paths out of the golden
    argv = ["save", "diff", before, after] + (["--format", "json"] if fmt == "json" else [])
    expected = golden_path(before, after, fmt).read_text(encoding="utf-8")

    assert main(argv) == EXIT_SUCCESS
    first = capsys.readouterr()
    assert main(argv) == EXIT_SUCCESS
    second = capsys.readouterr()

    assert first.out == expected
    assert second.out == first.out
    assert first.err == ""


def test_every_golden_report_belongs_to_existing_fixtures() -> None:
    goldens = sorted(EXPECTED_ROOT.rglob("*.expected.*"))
    assert len(goldens) == 2 * len(GOLDEN_PAIRS)
    for golden in goldens:
        stem = golden.name.split(".expected.")[0]
        before, after = stem.split("__")
        assert (FIXTURES_ROOT / "io" / golden.parent.name / before).is_file(), golden
        assert (FIXTURES_ROOT / "io" / golden.parent.name / after).is_file(), golden


def test_json_report_carries_kind_detail_and_evidence(capsys: pytest.CaptureFixture[str]) -> None:
    before = fixture_path("io", FIXTURE_SET, "interval_before.json")
    after = fixture_path("io", FIXTURE_SET, "interval_after.json")
    assert main(["save", "diff", "--format", "json", str(before), str(after)]) == EXIT_SUCCESS
    report = json.loads(capsys.readouterr().out)
    assert (report["before"], report["after"]) == (str(before), str(after))
    assert report["before_date"] == "2031-03-01T00:00:00"
    kinds = {change["kind"] for change in report["changes"]}
    assert kinds == {"appeared", "disappeared", "value", "membership", "map", "unknown"}
    for change in report["changes"]:
        assert set(change) >= {"domain", "entity_id", "field", "kind", "before", "after", "detail", "description"}
        assert change["before_location"]["save_id"] == str(before)
        assert change["after_location"]["save_id"] == str(after)
        if change["kind"] in ("appeared", "disappeared"):
            assert change["field"] is None
            assert "destroy" not in change["description"]
    by_key = {(c["entity_id"], c["field"]): c for c in report["changes"]}
    assert by_key[("nation:20", "allies")]["detail"] == {
        "added": [{"ref": "nation:22", "state_type": "TINationState", "confidence": "in-save-id"}],
        "removed": [{"ref": "nation:21", "state_type": "TINationState", "confidence": "in-save-id"}],
    }
    assert ("control point:10", "defended") not in by_key
    assert ("faction:15", "resources") not in by_key


def test_record_changes_carry_entries_in_json_but_only_counts_in_text(capsys: pytest.CaptureFixture[str]) -> None:
    before = fixture_path("io", FIXTURE_SET, "records_before.json")
    after = fixture_path("io", FIXTURE_SET, "records_after.json")
    assert main(["save", "diff", "--format", "json", str(before), str(after)]) == EXIT_SUCCESS
    report = json.loads(capsys.readouterr().out)
    by_key = {(c["entity_id"], c["field"]): c for c in report["changes"]}
    kills = by_key[("faction:15", "Kills")]
    assert (kills["kind"], kills["before"], kills["after"]) == ("records", 0, 1)
    assert kills["detail"]["added"][0]["value"] == ["Fixture Hull A"]
    assert kills["before_location"]["path"].endswith("/Value/Kills")
    assert kills["description"] == "Kills records changed: 1 added, 0 removed, 0 changed"
    ledger = by_key[("faction:15", "Transactions")]
    assert [entry["label"] for entry in ledger["detail"]["added"]] == ["Coup", "Purge"]
    assert ledger["detail"]["removed"] == []
    executive = by_key[("nation:20", "lastExecutiveChange")]
    assert [pair["after"]["key"] for pair in executive["detail"]["changed"]] == ["cause", "date", "newExecutive"]
    assert ("faction:15", "abductions") not in by_key
    assert ("faction:15", "intelSharingFactions") not in by_key
    assert ("faction:16", "Transactions") not in by_key  # unknown on both sides: nothing to compare

    assert main(["save", "diff", str(before), str(after)]) == EXIT_SUCCESS
    text = capsys.readouterr().out
    assert "  faction:15 Kills: +1 entries\n" in text
    assert "  faction:15 lastExecutiveChange" not in text and "  nation:20 lastExecutiveChange: ~3 entries\n" in text
    for content in ("Fixture Hull A", "Coup", "Purge", "FixtureMilestone"):
        assert content not in text


def test_diffing_a_save_with_itself_reports_no_changes(capsys: pytest.CaptureFixture[str]) -> None:
    save = str(fixture_path("io", FIXTURE_SET, "interval_before.json"))
    assert main(["save", "diff", save, save]) == EXIT_SUCCESS
    out = capsys.readouterr().out
    assert out.endswith("changes: 0\n")
    assert "changes:\n" not in out


@pytest.mark.parametrize(
    ("option", "message"),
    [
        (["--format", "markdown"], "invalid choice"),
        (["--min-significance", "major"], "unrecognized arguments"),
        (["--inferred"], "unrecognized arguments"),
    ],
)
def test_analysis_options_are_a_usage_error(
    option: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as result:
        main(["save", "diff", *option, "a.json", "b.json"])
    assert result.value.code == EXIT_USAGE_ERROR
    assert message in capsys.readouterr().err


def test_unreadable_and_unsupported_inputs_name_the_failing_file(capsys: pytest.CaptureFixture[str]) -> None:
    good = str(fixture_path("io", FIXTURE_SET, "interval_before.json"))
    assert main(["save", "diff", good, "does-not-exist.json"]) == EXIT_INPUT_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("tinarrative save diff: cannot read does-not-exist.json")
    bad = str(fixture_path("io", FIXTURE_SET, "malformed_truncated.json"))
    assert main(["save", "diff", bad, good]) == EXIT_UNSUPPORTED_INPUT
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"tinarrative save diff: {bad}:")
    assert "Traceback" not in captured.err


def test_missing_arguments_are_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as result:
        main(["save", "diff", "only-one.json"])
    assert result.value.code == EXIT_USAGE_ERROR
    capsys.readouterr()


def test_debug_log_reports_aggregates_without_save_values(capsys: pytest.CaptureFixture[str]) -> None:
    before = fixture_path("io", FIXTURE_SET, "interval_before.json")
    after = fixture_path("io", FIXTURE_SET, "interval_after.json")
    assert main(["--log-level", "debug", "save", "diff", str(before), str(after)]) == EXIT_SUCCESS
    err = capsys.readouterr().err
    lines = err.splitlines()
    assert lines[0] == "INFO tinarrative.cli: save diff start before=interval_before.json after=interval_after.json"
    assert lines[-1] == (
        "INFO tinarrative.cli: save diff done before=interval_before.json after=interval_after.json changes=48 exit=0"
    )
    assert (
        "DEBUG tinarrative.diff.state_diff: collection compared collection=nations before=3 after=3 matched=3 "
        "appeared=0 disappeared=0 value=3 membership=5 map=0 unknown=0 records=0" in lines
    )
    assert any(line.startswith("DEBUG tinarrative.diff.state_diff: singletons compared ") for line in lines)
    for value in ("Fixture", "FixtureTech", "Project_Fixture", str(before.parent)):
        assert value not in err
