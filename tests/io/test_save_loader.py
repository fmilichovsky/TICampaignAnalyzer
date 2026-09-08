import json

import pytest

from tests.fixtures import fixture_path
from tinarrative.io.save_loader import load_save


@pytest.mark.fixture
def test_load_save_reads_the_synthetic_minimal_save_fixture() -> None:
    save_path = fixture_path("io", "v0", "minimal_save.save")
    metadata_path = fixture_path("io", "v0", "minimal_save.save.json")

    assert load_save(save_path) == b"synthetic Terra Invicta save fixture\n"
    assert json.loads(metadata_path.read_text(encoding="utf-8"))["synthetic"] is True
