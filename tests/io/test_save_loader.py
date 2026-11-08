from pathlib import Path

import pytest

from tests.fixtures import fixture_path
from tinarrative.io.save_loader import load_raw_save, load_save


def test_load_save_returns_the_file_bytes_unchanged() -> None:
    save_path = fixture_path("io", "terra_invicta_json_v1", "not_json.save")

    assert load_save(save_path) == save_path.read_bytes()


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
