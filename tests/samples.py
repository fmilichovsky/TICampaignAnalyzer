"""The committed benchmark campaigns as test data: the ``sample_campaign`` fixture and a CLI runner.

Each campaign is decompressed once per session into a temporary directory, which is removed after its last test.
The fixture is registered by ``tests/conftest.py``; tests using it carry the ``samples`` marker.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tinarrative.benchmarking.manifest import decompress_samples, sample_files
from tinarrative.cli import EXIT_SUCCESS, main

SAMPLES = Path(__file__).resolve().parents[1] / "benchmarks" / "samples"
CAMPAIGNS = sample_files(SAMPLES)


def selected_campaigns(selection: str, campaigns: dict[str, Path]) -> list[str]:
    """Return selected campaign names, or all names when the selection is empty."""
    if not selection.strip():
        return sorted(campaigns)

    requested = [name.strip() for name in selection.split(",")]
    if any(not name for name in requested):
        raise pytest.UsageError("sample campaign selection contains an empty name")
    unknown = sorted(set(requested) - campaigns.keys())
    if unknown:
        raise pytest.UsageError(
            f"unknown sample campaign(s): {', '.join(unknown)}; available: {', '.join(sorted(campaigns))}"
        )
    return sorted(set(requested))


@pytest.fixture(scope="session")
def sample_campaign(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The directory of one benchmark campaign's decompressed saves; every campaign in turn."""
    campaign: str = request.param
    directory = tmp_path_factory.mktemp(campaign)
    decompress_samples(CAMPAIGNS[campaign], directory)
    yield directory
    shutil.rmtree(directory)


def save_paths(campaign: Path) -> list[Path]:
    """The saves of a decompressed campaign, in name order."""
    return sorted(campaign.iterdir())


def run_cli(*argv: str | Path) -> str:
    """Run the CLI in this process, assert it succeeded and return its stdout; usable from session fixtures."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main([str(arg) for arg in argv])
    assert code == EXIT_SUCCESS
    return out.getvalue()


def run_json(*argv: str | Path) -> Any:
    """Run a CLI command that prints JSON and return the parsed document."""
    return json.loads(run_cli(*argv))
