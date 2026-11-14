"""The stake measure registry."""

from __future__ import annotations

from tinarrative.model.kinds import StakeMeasure
from tinarrative.narrative.measures import MEASURES


def test_every_stake_measure_has_exactly_one_registry_entry() -> None:
    assert list(MEASURES) == list(StakeMeasure)


def test_every_entry_has_a_positive_reference_a_label_and_a_description() -> None:
    for spec in MEASURES.values():
        assert spec.reference > 0 and spec.label and spec.description
