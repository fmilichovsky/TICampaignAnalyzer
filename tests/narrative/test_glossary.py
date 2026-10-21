"""The narrator glossary: one entry per referenced ID, named by the latest save or interval."""

from __future__ import annotations

from typing import Any

from tinarrative.narrative.glossary import build_glossary


def _entry(document: dict[str, Any], ref: str) -> dict[str, Any]:
    return next(entry for entry in build_glossary(document, []) if entry["ref"] == ref)


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
    entry = _entry(_document("Fixture Nation (Executive)", "Fixture Nation (Executive)"), "control_point:7")

    assert entry["name"] == "Fixture Nation (Executive)"
    assert "former_names" not in entry


def test_a_reference_without_a_name_neither_sets_nor_clears_one() -> None:
    entry = _entry(_document(None, "Fixture Nation (Executive)", None), "control_point:7")

    assert entry["name"] == "Fixture Nation (Executive)"
    assert "former_names" not in entry


def test_narrative_names_never_override_the_chronological_members() -> None:
    narrative = [{"entities": [{"ref": "control_point:7", "name": "Fixture Nation (Executive)"}]}]
    entry = _entry(_document("Fixture Nation (Unions)", narrative=narrative), "control_point:7")

    assert entry["name"] == "Fixture Nation (Unions)"
    assert entry["former_names"] == ["Fixture Nation (Executive)"]
