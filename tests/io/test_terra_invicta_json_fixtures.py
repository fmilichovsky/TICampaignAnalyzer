"""Raw-loader coverage for sanitized Terra Invicta-shaped fixtures."""

import json

import pytest

from tests.fixtures import fixture_path
from tinarrative.io.save_loader import load_save


FIXTURE_PARTS = ("io", "terra_invicta_json_v1")


@pytest.mark.fixture
@pytest.mark.parametrize(
    "fixture_name",
    ["representative_campaign.json", "unknown_state_type.json", "malformed_truncated.json"],
)
def test_load_save_preserves_each_realistic_fixture_as_raw_bytes(fixture_name: str) -> None:
    save_path = fixture_path(*FIXTURE_PARTS, fixture_name)

    assert load_save(save_path) == save_path.read_bytes()


@pytest.mark.fixture
def test_representative_fixture_has_the_observed_top_level_save_shape() -> None:
    fixture = json.loads(fixture_path(*FIXTURE_PARTS, "representative_campaign.json").read_text())

    assert set(fixture) == {"currentID", "gamestates"}
    assert fixture["currentID"]["value"] == 9001
    assert {
        "PavonisInteractive.TerraInvicta.TIMetadataState",
        "PavonisInteractive.TerraInvicta.TITimeState",
        "PavonisInteractive.TerraInvicta.TIFactionState",
        "PavonisInteractive.TerraInvicta.TINationState",
        "PavonisInteractive.TerraInvicta.TIHabState",
        "PavonisInteractive.TerraInvicta.TISpaceShipState",
    } <= set(fixture["gamestates"])


@pytest.mark.fixture
def test_unknown_state_fixture_remains_a_valid_uninterpreted_save_shape() -> None:
    fixture = json.loads(fixture_path(*FIXTURE_PARTS, "unknown_state_type.json").read_text())

    assert "Example.ModOrFutureState" in fixture["gamestates"]


@pytest.mark.fixture
def test_malformed_fixture_remains_malformed_json() -> None:
    raw = fixture_path(*FIXTURE_PARTS, "malformed_truncated.json").read_text()

    with pytest.raises(json.JSONDecodeError):
        json.loads(raw)
