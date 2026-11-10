"""The councilor dossier of each committed benchmark campaign."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.narrative.support import loyalty_keys
from tests.samples import run_cli
from tinarrative.narrator.brief import AUDIT_KEYS, HEADER_KEYS, ORG_AUDIT_KEYS, VISIBILITY_AUDIT_KEYS

pytestmark = pytest.mark.samples


def test_the_dossier_of_a_sample_campaign(sample_campaign: Path, tmp_path: Path) -> None:
    run_cli("councilors", sample_campaign, "--output", tmp_path)
    document = json.loads((tmp_path / "dossier.json").read_text(encoding="utf-8"))
    assert loyalty_keys(document) == []
    assert document["councilors"]
    assert any(entry["player"] for entry in document["councilors"])
    assert all(org["category"] for entry in document["councilors"] for org in entry["orgs"])
    assert all(entry["tenure_years"] >= 1 for entry in document["councilors"])


def test_the_requests_of_a_sample_campaign_carry_no_audit_field(sample_campaign: Path, tmp_path: Path) -> None:
    run_cli("councilors", sample_campaign, "--output", tmp_path)
    for path in sorted((tmp_path / "requests").iterdir()):
        content = json.loads(path.read_text(encoding="utf-8"))["messages"][0]["content"]
        brief = json.loads(content.partition("```json\n")[2].rpartition("\n```")[0])
        assert list(brief) == [*HEADER_KEYS, "councilor"]
        assert AUDIT_KEYS.isdisjoint(brief["councilor"])
        assert VISIBILITY_AUDIT_KEYS.isdisjoint(brief["councilor"]["visibility"])
        assert all(ORG_AUDIT_KEYS.isdisjoint(org) for org in brief["councilor"]["orgs"])
        assert '"id":' not in content
