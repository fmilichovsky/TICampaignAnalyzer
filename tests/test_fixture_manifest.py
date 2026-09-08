"""Regression coverage for versioned fixture-set metadata."""

from tests.fixtures import fixture_path
from scripts.verify_fixture_manifest import verify_manifest


def test_terra_invicta_fixture_manifest_is_complete_and_consistent() -> None:
    manifest_path = fixture_path("io", "terra_invicta_json_v1", "fixture_manifest.json")

    assert verify_manifest(manifest_path) == []
