"""Opt-in coverage against a private real save; never reads a hard-coded path.

Run with ``TINARRATIVE_REAL_SAVE=/path/to/save.json python -m pytest -m real_save``.
"""

import json
import os
from pathlib import Path

import pytest

from tinarrative.cli import EXIT_SUCCESS, main

ENV_VAR = "TINARRATIVE_REAL_SAVE"


def real_save_path() -> Path:
    location = os.environ.get(ENV_VAR)
    if not location:
        pytest.skip(f"{ENV_VAR} is not set")
    path = Path(location)
    if not path.is_file():
        pytest.skip(f"{ENV_VAR} does not point to a file")
    return path


@pytest.mark.real_save
def test_inspect_reports_the_documented_envelope_deterministically(
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["inspect", str(real_save_path()), "--format", "json"]

    assert main(argv) == EXIT_SUCCESS
    first = capsys.readouterr().out
    assert main(argv) == EXIT_SUCCESS
    second = capsys.readouterr().out

    assert first == second
    report = json.loads(first)
    assert report["status"] == "ok"
    assert report["root_type"] == "object"
    assert [entry["key"] for entry in report["top_level"]] == [
        "currentID",
        "gamestates",
    ]
    assert report["second_level"]["gamestates"]
    assert report["diagnostics"] == []
