"""``save diff`` on two saves of each committed benchmark campaign."""

from pathlib import Path

import pytest

from tests.samples import run_cli, run_json, save_paths

pytestmark = pytest.mark.samples


def test_diff_is_deterministic_and_locates_every_change_in_both_saves(sample_campaign: Path) -> None:
    before, after = save_paths(sample_campaign)[:2]
    argv = ("save", "diff", before, after, "--format", "json")
    assert run_cli(*argv) == run_cli(*argv)
    report = run_json(*argv)
    assert report["changes"]
    for change in report["changes"]:
        assert change["before_location"]["save_id"] == str(before), change["entity_id"]
        assert change["after_location"]["save_id"] == str(after), change["entity_id"]
        assert (change["field"] is None) == (change["kind"] in ("appeared", "disappeared")), change["entity_id"]
