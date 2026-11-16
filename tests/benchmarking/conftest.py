"""The calibration table of each sample campaign, extracted once per session."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.samples import SAMPLES, save_paths
from tinarrative.benchmarking.calibration.table import (
    build_index,
    extract_campaign,
    type_kinds,
    write_campaign,
    write_index,
)
from tinarrative.benchmarking.manifest import prefix_of

TableFor = Callable[[str, Path], Path]


@pytest.fixture(scope="session")
def calibration_tables(tmp_path_factory: pytest.TempPathFactory) -> TableFor:
    """The table directory of a named, decompressed sample campaign; extracted on first use."""
    cache: dict[str, Path] = {}

    def table_for(name: str, saves: Path) -> Path:
        if name not in cache:
            directory = tmp_path_factory.mktemp(f"calibration-{name}")
            rows = extract_campaign(save_paths(saves))
            write_campaign(directory, name, rows)
            kinds = type_kinds(row["type"] for row in rows)
            write_index(directory, build_index([name], key="samples", extracted_at="", kinds=kinds))
            cache[name] = directory
        return cache[name]

    return table_for


@pytest.fixture
def calibration_table(sample_campaign: Path, request: pytest.FixtureRequest, calibration_tables: TableFor) -> Path:
    """The calibration table directory of the sample campaign under test; prefix campaigns are skipped."""
    name: str = request.node.callspec.params["sample_campaign"]
    if prefix_of(SAMPLES, name) is not None:
        pytest.skip("a prefix campaign is never extracted")
    return calibration_tables(name, sample_campaign)
