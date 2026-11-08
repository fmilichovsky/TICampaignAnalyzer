"""``save inspect`` on every save of the committed benchmark campaigns."""

from pathlib import Path

import pytest

from tests.samples import run_cli, run_json, save_paths

pytestmark = pytest.mark.samples


def test_inspect_reports_the_documented_envelope_deterministically(sample_campaign: Path) -> None:
    paths = save_paths(sample_campaign)
    argv = ("save", "inspect", paths[0], "--format", "json")
    assert run_cli(*argv) == run_cli(*argv)
    for path in paths:
        report = run_json("save", "inspect", path, "--format", "json")
        assert report["status"] == "ok", path.name
        assert report["root_type"] == "object", path.name
        assert [entry["key"] for entry in report["top_level"]] == ["currentID", "gamestates"], path.name
        assert report["second_level"]["gamestates"], path.name
        assert report["diagnostics"] == [], path.name
