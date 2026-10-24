"""The game's value bands: labels at the boundaries, crossings and their margin."""

import pytest

from tinarrative.analyzers.politics.bands import (
    BANDS,
    MARGINS,
    Crossing,
    band,
    crossed,
    margin_crossing,
    rest_value_delta,
)
from tinarrative.model.values import FrozenMap


@pytest.mark.parametrize(
    ("statistic", "value", "label"),
    [
        ("unrest", 0.0, "Peaceful"),
        ("unrest", 1.49, "Peaceful"),
        ("unrest", 1.5, "Subversion"),
        ("unrest", 9.0, "Civil War"),
        ("unrest", 12.0, "Civil War"),
        ("democracy", 1.9, "Totalitarian"),
        ("democracy", 8.0, "Full Democracy"),
        ("education", 12.6, "Advanced"),
        ("cohesion", 0.5, "Fragmented"),
        ("cohesion", 10.0, "Monolithic"),
        ("inequality", 6.5, "Extreme"),
        ("militaryTechLevel", 3.9, "Atomic"),
        ("militaryTechLevel", -1.0, "Industrial"),
    ],
)
def test_a_value_takes_the_label_of_the_band_it_begins(statistic: str, value: float, label: str) -> None:
    assert band(statistic, value) == label


def test_every_band_table_ascends_from_an_unbounded_first_band() -> None:
    for statistic, bands in BANDS.items():
        bounds = [bound for bound, _ in bands]
        assert bounds[0] == float("-inf") and bounds == sorted(bounds), statistic
        assert statistic in MARGINS


def test_a_crossing_names_both_bands_and_measures_its_margin_from_the_last_boundary() -> None:
    assert crossed("unrest", 2.0, 2.5) is None
    assert crossed("unrest", 2.5, 4.75) == Crossing("Subversion", "Insurgency", 2, 4.5, 0.25)
    assert crossed("unrest", 4.75, 1.0) == Crossing("Insurgency", "Peaceful", 3, 1.5, 0.5)


def test_a_crossing_counts_only_beyond_the_statistics_margin() -> None:
    assert margin_crossing("democracy", 3.9, 4.01) is None
    assert margin_crossing("democracy", 3.5, 4.25) is not None
    assert margin_crossing("militaryTechLevel", 4.0, 3.9) == Crossing(
        "Information", "Atomic", 1, 4.0, pytest.approx(0.1)
    )
    assert margin_crossing("militaryTechLevel", 5.0, 4.9) is not None
    assert margin_crossing("militaryTechLevel", 3.95, 4.05) is None


def test_the_rest_value_delta_is_read_from_its_reason_only() -> None:
    causes = FrozenMap((("UnrestReason_MovementToRestValue", -0.75), ("UnrestReason_EventEffect", 2.0)))
    assert rest_value_delta(causes) == -0.75
    assert rest_value_delta(FrozenMap((("UnrestReason_EventEffect", 2.0),))) == 0.0
