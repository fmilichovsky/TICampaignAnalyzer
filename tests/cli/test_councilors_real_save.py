"""Opt-in dossier check over a private campaign (``TINARRATIVE_REAL_SAVE_SEQUENCE``, saves of one campaign)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.narrative.support import loyalty_keys
from tinarrative.cli import EXIT_SUCCESS, main

pytestmark = pytest.mark.real_save

ENV_VAR = "TINARRATIVE_REAL_SAVE_SEQUENCE"


def test_the_dossier_of_a_real_campaign(tmp_path: Path) -> None:
    paths = [part for part in os.environ.get(ENV_VAR, "").split(os.pathsep) if part]
    if len(paths) < 2:
        pytest.skip(f"{ENV_VAR} does not list at least two saves (separated by {os.pathsep!r})")
    assert main(["councilors", *paths, "--output", str(tmp_path)]) == EXIT_SUCCESS
    text = (tmp_path / "dossier.json").read_text(encoding="utf-8")
    document = json.loads(text)
    assert loyalty_keys(document) == []
    assert document["councilors"]
    assert any(entry["player"] for entry in document["councilors"])
    assert all(org["category"] for entry in document["councilors"] for org in entry["orgs"])
    assert all(entry["tenure_years"] >= 1 for entry in document["councilors"])
