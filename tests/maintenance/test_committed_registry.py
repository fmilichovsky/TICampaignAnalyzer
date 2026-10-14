"""The committed unknowns registry stays valid, canonical and free of entries the schema already knows."""

import json
from pathlib import Path

from tinarrative.maintenance.registry import SAFE_STRING, dump, load_registry, prune_known, validate_document

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "docs" / "game-data-notes" / "unknowns" / "registry.json"


def test_committed_registry_is_valid_canonical_and_fully_unknown() -> None:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    assert validate_document(json.loads(text)) == []
    registry = load_registry(REGISTRY_PATH)
    assert dump(registry) == text, "regenerate the registry with 'tinarrative unknowns' instead of editing it"
    _pruned, dropped = prune_known(registry)
    assert dropped == (), f"re-run the unknowns scan: the schema now covers {[str(key) for key in dropped]}"
    for entry in registry.entries:
        for value in (entry.key.state_type, entry.key.field, entry.key.detail, *entry.game_versions):
            assert value is None or value == "" or SAFE_STRING.match(value), value
