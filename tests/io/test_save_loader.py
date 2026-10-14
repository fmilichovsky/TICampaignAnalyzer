import json
from pathlib import Path

import pytest

from tests.fixtures import fixture_path
from tinarrative.io.save_loader import load_raw_save, load_save


@pytest.mark.fixture
def test_load_save_reads_the_synthetic_minimal_save_fixture() -> None:
    save_path = fixture_path("io", "v0", "minimal_save.save")
    metadata_path = fixture_path("io", "v0", "minimal_save.save.json")

    assert load_save(save_path) == b"synthetic Terra Invicta save fixture\n"
    assert json.loads(metadata_path.read_text(encoding="utf-8"))["synthetic"] is True


@pytest.mark.fixture
def test_load_raw_save_keeps_source_path_and_root() -> None:
    save_path = fixture_path("io", "terra_invicta_json_v1", "representative_campaign.json")

    raw = load_raw_save(save_path)

    assert raw.source == str(save_path)
    assert raw.size_bytes == save_path.stat().st_size
    assert raw.root["currentID"] == {"value": 9001}


def test_load_raw_save_lets_path_errors_propagate(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        load_raw_save(tmp_path / "missing.json")
    with pytest.raises(OSError):
        load_raw_save(tmp_path)
