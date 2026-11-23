"""The measure registry."""

from __future__ import annotations

from tinarrative.model.kinds import Measure
from tinarrative.narrative.measures import MEASURES


def test_every_measure_has_exactly_one_registry_entry() -> None:
    assert list(MEASURES) == list(Measure)


def test_every_entry_has_a_label_and_a_description() -> None:
    for spec in MEASURES.values():
        assert spec.label and spec.description
