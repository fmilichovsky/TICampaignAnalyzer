"""The councilor dossier of each committed benchmark campaign."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.narrative.support import loyalty_keys
from tests.samples import run_cli

pytestmark = pytest.mark.samples


def test_the_dossier_of_a_sample_campaign(sample_campaign: Path, tmp_path: Path) -> None:
    run_cli("councilors", sample_campaign, "--output", tmp_path)
    document = json.loads((tmp_path / "dossier.json").read_text(encoding="utf-8"))
    assert loyalty_keys(document) == []
    assert document["councilors"]
    assert any(entry["player"] for entry in document["councilors"])
    assert all(org["category"] for entry in document["councilors"] for org in entry["orgs"])
    assert all(entry["tenure_years"] >= 1 for entry in document["councilors"])
