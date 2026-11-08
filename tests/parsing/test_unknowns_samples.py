"""``unknowns`` over the committed benchmark campaigns, and over a wide private save set when one is named.

``TINARRATIVE_REAL_SAVE_DIRECTORY`` names a directory of private saves, possibly of several campaigns; without it the
private scan is skipped.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tests.samples import run_json, save_paths
from tinarrative.io.save_loader import load_raw_save
from tinarrative.maintenance.registry import SAFE_STRING
from tinarrative.parsing import unknowns
from tinarrative.parsing.fields import SERIALIZATION_FIELDS

PRIVATE_SAVES = "TINARRATIVE_REAL_SAVE_DIRECTORY"
STRUCTURAL = ("unknown_state_type", "unknown_envelope_key", "unexpected_container_shape")
"""Finding kinds that mean the parser misreads a save's structure, not merely a field it does not describe."""


def assert_findings_are_schema_only(report: Any) -> None:
    for finding in report["findings"]:
        for value in (finding["state_type"], finding["field"], finding["detail"]):
            assert value is None or SAFE_STRING.match(value), value
        if finding["shape"] is not None:
            for key in (*finding["shape"]["object_keys"], *finding["shape"]["array_item_keys"]):
                assert SAFE_STRING.match(key), key


def assert_scanned_with_fields_only(report: Any) -> None:
    assert report["saves"] and all(save["status"] == "scanned" for save in report["saves"])
    assert [finding for finding in report["findings"] if finding["kind"] in STRUCTURAL] == []
    assert_findings_are_schema_only(report)


@pytest.mark.samples
def test_sample_unknowns_are_fields_only(sample_campaign: Path) -> None:
    assert_scanned_with_fields_only(run_json("unknowns", sample_campaign, "--format", "json"))


@pytest.mark.samples
def test_sample_unknown_fields_leak_no_values(sample_campaign: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The schema may cover every field of the save, so forget the metadata singleton's fields to report real
    # values (among them the player faction name) as unknown and check that none reaches the report.
    monkeypatch.setitem(unknowns.KNOWN_FIELDS, "TIMetadataState", frozenset(SERIALIZATION_FIELDS))
    path = save_paths(sample_campaign)[0]
    rendered = json.dumps(report := run_json("unknowns", path, "--format", "json"))
    metadata = load_raw_save(path).root["gamestates"]["PavonisInteractive.TerraInvicta.TIMetadataState"][0]["Value"]
    player_faction = metadata.get("playerFactionName")
    assert isinstance(player_faction, str) and player_faction not in rendered
    assert any(finding["field"] == "playerFactionName" for finding in report["findings"])
    assert_findings_are_schema_only(report)


def test_private_save_unknowns_are_fields_only() -> None:
    directory = os.environ.get(PRIVATE_SAVES)
    if not directory:
        pytest.skip(f"{PRIVATE_SAVES} does not name a directory of saves")
    report = run_json("unknowns", directory, "--format", "json")
    report["saves"] = [save for save in report["saves"] if save["status"] != "skipped"]
    assert_scanned_with_fields_only(report)
