"""Opt-in privacy and coverage check of unknown detection against a private save (``TINARRATIVE_REAL_SAVE``)."""

import json
import os
from pathlib import Path

import pytest

from tinarrative.io.save_loader import load_raw_save
from tinarrative.maintenance.registry import SAFE_STRING
from tinarrative.parsing import unknowns
from tinarrative.parsing.fields import SERIALIZATION_FIELDS
from tinarrative.parsing.normalization import normalize
from tinarrative.parsing.raw_save import RawSave
from tinarrative.parsing.unknowns import UnknownCollector, UnknownReport

pytestmark = pytest.mark.real_save


@pytest.fixture
def raw() -> RawSave:
    location = os.environ.get("TINARRATIVE_REAL_SAVE")
    if not location:
        pytest.skip("TINARRATIVE_REAL_SAVE is not set")
    return load_raw_save(Path(location))


def scan(raw: RawSave) -> UnknownReport:
    collector = UnknownCollector()
    normalize(raw, collector=collector)
    return collector.report()


def test_real_save_unknowns_are_fields_only(raw: RawSave) -> None:
    counts = scan(raw).counts()
    assert counts["unknown_state_type"] == 0
    assert counts["unknown_envelope_key"] == 0
    assert counts["unexpected_container_shape"] == 0


def test_real_save_unknown_fields_leak_no_values(raw: RawSave, monkeypatch: pytest.MonkeyPatch) -> None:
    # The schema may cover every field of the save, so forget the metadata singleton's fields to report real
    # values (among them the player faction name) as unknown and check that none reaches the report.
    known = {**unknowns.KNOWN_FIELDS, "TIMetadataState": frozenset(SERIALIZATION_FIELDS)}
    monkeypatch.setattr(unknowns, "KNOWN_FIELDS", known)
    report = scan(raw)
    assert report.counts()["unknown_field"] > 0
    rendered = json.dumps(report.to_dict())
    metadata = raw.root["gamestates"]["PavonisInteractive.TerraInvicta.TIMetadataState"][0]["Value"]
    player_faction = metadata.get("playerFactionName")
    assert isinstance(player_faction, str) and player_faction not in rendered
    assert any(finding.field == "playerFactionName" for finding in report.findings)
    for finding in report.findings:
        for value in (finding.state_type, finding.field, finding.detail):
            assert value is None or SAFE_STRING.match(value), value
        if finding.shape is not None:
            for key in (*finding.shape.object_keys, *finding.shape.array_item_keys):
                assert SAFE_STRING.match(key), key
