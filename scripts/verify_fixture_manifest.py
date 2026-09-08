"""Verify hashes and declared properties for a versioned fixture set."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path


REQUIRED_FIXTURE_FIELDS = {
    "path",
    "kind",
    "json_valid",
    "expected_loader_outcome",
    "format_assumption",
    "format_documentation",
    "version_assumption",
    "sha256",
    "purpose",
}
REQUIRED_MANIFEST_FIELDS = {
    "fixture_set_version",
    "source_save_capture_date",
    "game_version",
    "game_version_note",
    "provenance",
    "privacy_note",
    "licensing_note",
    "max_fixture_bytes",
    "fixtures",
}
EXPECTED_LOADER_OUTCOME = "returns_exact_raw_bytes"
SUPPORTED_FORMAT_ASSUMPTIONS = {"terra_invicta_json_v1"}
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def verify_manifest(manifest_path: Path) -> list[str]:
    """Return human-readable validation errors for ``manifest_path``."""
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"Cannot read manifest {manifest_path}: {error}"]

    missing_manifest_fields = REQUIRED_MANIFEST_FIELDS - manifest.keys()
    if missing_manifest_fields:
        errors.append(
            f"Manifest is missing fields: {', '.join(sorted(missing_manifest_fields))}"
        )
    if manifest.get("fixture_set_version") != 1:
        errors.append("fixture_set_version must be 1")
    try:
        date.fromisoformat(manifest["source_save_capture_date"])
    except (KeyError, TypeError, ValueError):
        errors.append("source_save_capture_date must be an ISO-8601 date")
    if not isinstance(manifest.get("fixtures"), list) or not manifest["fixtures"]:
        return [*errors, "fixtures must be a non-empty list"]

    max_fixture_bytes = manifest.get("max_fixture_bytes")
    if not isinstance(max_fixture_bytes, int) or max_fixture_bytes <= 0:
        return [*errors, "max_fixture_bytes must be a positive integer"]

    declared_paths: set[str] = set()
    for entry in manifest["fixtures"]:
        if not isinstance(entry, dict):
            errors.append("Each fixture entry must be an object")
            continue
        missing = REQUIRED_FIXTURE_FIELDS - entry.keys()
        if missing:
            errors.append(f"Fixture entry is missing fields: {', '.join(sorted(missing))}")
            continue
        if entry["path"] in declared_paths:
            errors.append(f"Fixture is declared more than once: {entry['path']}")
            continue
        declared_paths.add(entry["path"])

        fixture_path = manifest_path.parent / entry["path"]
        if not fixture_path.is_file():
            errors.append(f"Fixture does not exist: {entry['path']}")
            continue

        raw = fixture_path.read_bytes()
        if len(raw) > max_fixture_bytes:
            errors.append(
                f"Fixture exceeds {max_fixture_bytes} bytes: {entry['path']} ({len(raw)} bytes)"
            )
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != entry["sha256"]:
            errors.append(f"Fixture hash does not match manifest: {entry['path']}")
        if entry["expected_loader_outcome"] != EXPECTED_LOADER_OUTCOME:
            errors.append(f"Unexpected loader outcome declaration: {entry['path']}")
        if entry["format_assumption"] not in SUPPORTED_FORMAT_ASSUMPTIONS:
            errors.append(
                f"Unsupported format assumption for {entry['path']}: "
                f"{entry['format_assumption']!r}"
            )
        documentation_path = REPOSITORY_ROOT / entry["format_documentation"]
        if not documentation_path.is_file():
            errors.append(
                f"Fixture format documentation does not exist for {entry['path']}: "
                f"{entry['format_documentation']}"
            )
        elif entry["format_assumption"] not in documentation_path.read_text(encoding="utf-8"):
            errors.append(
                f"Fixture format documentation does not name {entry['format_assumption']!r}: "
                f"{entry['path']}"
            )
        if not isinstance(entry["version_assumption"], str) or not entry["version_assumption"]:
            errors.append(f"Fixture version assumption must be a non-empty string: {entry['path']}")

        try:
            json.loads(raw)
            is_valid_json = True
        except json.JSONDecodeError:
            is_valid_json = False
        if is_valid_json is not entry["json_valid"]:
            errors.append(f"Fixture JSON validity does not match manifest: {entry['path']}")

    actual_paths = {
        path.name for path in manifest_path.parent.iterdir() if path.is_file() and path != manifest_path
    }
    if declared_paths != actual_paths:
        errors.append("Manifest fixture paths do not match the files beside the manifest")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Path to fixture_manifest.json")
    args = parser.parse_args(argv)
    errors = verify_manifest(args.manifest)
    if errors:
        print("Fixture manifest validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Fixture manifest is valid: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
