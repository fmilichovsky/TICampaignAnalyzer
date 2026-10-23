"""The narrator glossary: names for IDs referenced without one, and the former names of renamed entities."""

from __future__ import annotations

from typing import Any

from tinarrative.narrative.glossary import build_glossary


def _entry(document: dict[str, Any], ref: str) -> dict[str, Any]:
    return next(entry for entry in build_glossary(document) if entry["ref"] == ref)


def _listed(document: dict[str, Any]) -> list[str]:
    return [entry["ref"] for entry in build_glossary(document)]


def _document(*names: str | None, narrative: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    intervals = [
        {"events": [{"entities": [{"ref": "control_point:7", **({"name": name} if name else {})}]}]} for name in names
    ]
    return {"narrative": narrative or [], "intervals": intervals}


def test_a_renamed_entity_keeps_its_latest_name_and_lists_the_earlier_ones() -> None:
    entry = _entry(
        _document("Fixture Nation (Executive)", "Fixture Nation (Unions)", "Fixture Nation (Police)"), "control_point:7"
    )

    assert entry["name"] == "Fixture Nation (Police)"
    assert entry["former_names"] == ["Fixture Nation (Executive)", "Fixture Nation (Unions)"]


def test_a_name_that_never_changes_has_no_former_names() -> None:
    entry = _entry(_document("Fixture Nation (Executive)", None, "Fixture Nation (Executive)"), "control_point:7")

    assert entry == {"ref": "control_point:7", "domain": "control_point", "name": "Fixture Nation (Executive)"}


def test_an_entity_every_reference_names_has_no_entry() -> None:
    assert _listed(_document("Fixture Nation (Executive)", "Fixture Nation (Executive)")) == []


def test_an_entity_no_reference_names_has_no_entry() -> None:
    assert _listed(_document(None, None)) == []


def test_a_reference_without_a_name_neither_sets_nor_clears_one() -> None:
    entry = _entry(_document(None, "Fixture Nation (Executive)", None), "control_point:7")

    assert entry["name"] == "Fixture Nation (Executive)"
    assert "former_names" not in entry


def test_narrative_names_never_override_the_chronological_members() -> None:
    narrative = [{"entities": [{"ref": "control_point:7", "name": "Fixture Nation (Executive)"}]}]
    entry = _entry(_document("Fixture Nation (Unions)", narrative=narrative), "control_point:7")

    assert entry["name"] == "Fixture Nation (Unions)"
    assert entry["former_names"] == ["Fixture Nation (Executive)"]


def test_ally_refs_are_glossary_entries() -> None:
    document = {
        "narrative": [],
        "saves": [{"situation": {"nations": [{"nation": {"ref": "nation:1"}, "allies": ["nation:9"]}]}}],
        "intervals": [{"events": [{"entities": [{"ref": "nation:9", "name": "Fixture Ally"}]}]}],
    }

    assert _listed(document) == ["nation:9"]
    assert _entry(document, "nation:9")["name"] == "Fixture Ally"


def test_share_holders_are_glossary_entries() -> None:
    document = {
        "narrative": [],
        "saves": [{"situation": {"control_points": [{"shares": {"faction:15": 1}}]}}],
        "intervals": [{"events": [{"entities": [{"ref": "faction:15", "name": "Fixture Resistance"}]}]}],
    }

    assert _listed(document) == ["faction:15"]


def test_an_entry_carries_no_state_type() -> None:
    document = {
        "narrative": [],
        "intervals": [
            {"events": [{"entities": [{"ref": "nation:9", "name": "Fixture Ally", "state_type": "TINationState"}]}]},
            {"events": [{"entities": [{"ref": "nation:9", "state_type": "TINationState"}]}]},
        ],
    }

    assert _entry(document, "nation:9") == {"ref": "nation:9", "domain": "nation", "name": "Fixture Ally"}
