"""Nation statistic shifts: thresholds scaled to the interval, cause attribution and the placeholder skip."""

import pytest

from tests.analyzers.support import AFTER, BEFORE, analyze, only, pair, region_ref, snapshot, state
from tinarrative.analyzers.politics import NationMetricAnalyzer
from tinarrative.analyzers.politics.nation_metrics import (
    COHESION,
    DISCRETE,
    GDP,
    STATISTIC_SHIFTED,
    StatisticThreshold,
    interval_days,
    is_shift,
)
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import SourceRole
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.model.values import FrozenMap, Observed, Unknown, freeze

ANALYZER = NationMetricAnalyzer()
NATION = EntityDomain.NATION
REGIONS = (region_ref("40"),)
TRACKER = "tracker_GDPChangeReason_AllTime"
QUARTER = 92.0
"""Days between the default synthetic dates (2031-03-01 to 2031-06-01)."""


def nation_pair(
    before_fields: dict[str, Observed], after_fields: dict[str, Observed], **dates: str
) -> tuple[SaveSnapshot, SaveSnapshot]:
    """Nation 20 on both sides; ``before``/``after`` override the default dates (92 days apart)."""
    before = snapshot(BEFORE, state(NATION, "20", BEFORE, **before_fields), date=dates.get("before"))
    after = snapshot(AFTER, state(NATION, "20", AFTER, **after_fields), date=dates.get("after"))
    return before, after


def test_a_gdp_shift_carries_the_per_cause_deltas_and_cites_the_tracker() -> None:
    before, after = nation_pair(
        {
            "regions": REGIONS,
            "GDP": 1.0e9,
            TRACKER: freeze({"GDPReason_EconomyPriority": 5.0e8, "GDPReason_ClimateChange": -1.0e7}),
        },
        {
            "regions": REGIONS + (region_ref("41"),),
            "GDP": 3.0e9,
            TRACKER: freeze(
                {
                    "GDPReason_EconomyPriority": 5.0e8,
                    "GDPReason_ClimateChange": -2.0e7,
                    "GDPReason_TerritoryChange": 2.01e9,
                }
            ),
        },
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == STATISTIC_SHIFTED and event.id == "nation.statistic_shifted/nation:20/GDP"
    assert [str(ref.entity_id) for ref in event.entities] == ["nation:20"]
    assert dict(event.attributes) == {
        "statistic": "GDP",
        "before": 1.0e9,
        "after": 3.0e9,
        "relative_change": 2.0,
        "interval_days": QUARTER,
        "causes": FrozenMap((("GDPReason_ClimateChange", -1.0e7), ("GDPReason_TerritoryChange", 2.01e9))),
    }
    assert [(s.role, s.change.field) for s in event.sources] == [
        (SourceRole.PRIMARY, "GDP"),
        (SourceRole.CORROBORATING, TRACKER),
    ]


def test_a_shift_below_the_threshold_emits_nothing() -> None:
    before, after = nation_pair({"regions": REGIONS, "GDP": 1.0e9}, {"regions": REGIONS, "GDP": 1.1e9})
    assert analyze(ANALYZER, before, after) == []


def test_a_tracker_change_without_a_statistic_change_stays_in_the_diff() -> None:
    before, after = nation_pair(
        {"regions": REGIONS, "GDP": 1.0e9, TRACKER: freeze({"GDPReason_EventEffect": 0.0})},
        {"regions": REGIONS, "GDP": 1.0e9, TRACKER: freeze({"GDPReason_EventEffect": 5.0e8})},
    )
    _, _, diff = pair(before, after)
    assert [change.field for change in diff.changes if change.domain == NATION.value] == [TRACKER]
    assert ANALYZER.analyze(before, after, diff) == []


def test_a_statistic_change_with_an_unchanged_tracker_has_no_causes_and_cites_only_the_statistic() -> None:
    tracker = freeze({"GDPReason_EventEffect": 1.0})
    before, after = nation_pair(
        {"regions": REGIONS, "GDP": 1.0e9, TRACKER: tracker}, {"regions": REGIONS, "GDP": 2.0e9, TRACKER: tracker}
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.attribute("causes") == FrozenMap()
    assert [s.change.field for s in event.sources] == ["GDP"]


def test_an_unreadable_tracker_makes_the_causes_unknown() -> None:
    before, after = nation_pair(
        {"regions": REGIONS, "GDP": 1.0e9, TRACKER: freeze({"GDPReason_EventEffect": "x"})},
        {"regions": REGIONS, "GDP": 2.0e9, TRACKER: freeze({"GDPReason_EventEffect": 1.0})},
    )
    (event,) = analyze(ANALYZER, before, after)
    assert isinstance(event.attribute("causes"), Unknown)


def test_placeholder_nations_are_skipped_but_a_nation_losing_its_regions_is_not() -> None:
    before, after = nation_pair({"regions": (), "GDP": 1.0e9}, {"regions": (), "GDP": 5.0e9})
    assert analyze(ANALYZER, before, after) == []
    before, after = nation_pair({"regions": REGIONS, "GDP": 1.0e9}, {"regions": (), "GDP": 1.0e2})
    assert only(analyze(ANALYZER, before, after), STATISTIC_SHIFTED).attribute("after") == 1.0e2


def test_a_statistic_without_a_tracker_has_no_causes_attribute() -> None:
    before, after = nation_pair(
        {"regions": REGIONS, "numNuclearWeapons": 1}, {"regions": REGIONS, "numNuclearWeapons": 4}
    )
    (event,) = analyze(ANALYZER, before, after)
    assert dict(event.attributes) == {
        "statistic": "numNuclearWeapons",
        "before": 1,
        "after": 4,
        "relative_change": 3.0,
        "interval_days": QUARTER,
    }


def test_a_control_point_count_change_is_not_a_tracked_statistic() -> None:
    before, after = nation_pair(
        {"regions": REGIONS, "numControlPoints": 1}, {"regions": REGIONS, "numControlPoints": 4}
    )
    assert analyze(ANALYZER, before, after) == []


def test_a_change_from_zero_has_no_ratio_and_always_reaches_a_relative_threshold() -> None:
    before, after = nation_pair(
        {"regions": REGIONS, "spaceFunding_year": 0.0}, {"regions": REGIONS, "spaceFunding_year": 10.0}
    )
    (event,) = analyze(ANALYZER, before, after)
    assert event.attribute("relative_change") is None


def test_public_opinion_shifts_are_reported_per_key() -> None:
    before, after = nation_pair(
        {"regions": REGIONS, "publicOpinion": freeze({"Resist": 0.5, "Submit": 0.3, "Undecided": 0.2})},
        {"regions": REGIONS, "publicOpinion": freeze({"Resist": 0.2, "Submit": 0.6, "Undecided": 0.2})},
        before="2031-03-01T00:00:00",
        after="2031-03-08T00:00:00",
    )
    events = analyze(ANALYZER, before, after)
    assert sorted(event.id for event in events) == [
        "nation.statistic_shifted/nation:20/publicOpinion/Resist",
        "nation.statistic_shifted/nation:20/publicOpinion/Submit",
    ]
    resist = next(event for event in events if event.attribute("key") == "Resist")
    assert resist.attribute("before") == 0.5 and resist.attribute("after") == 0.2
    assert [(s.role, s.change.field, s.member) for s in resist.sources] == [
        (SourceRole.PRIMARY, "publicOpinion", "Resist")
    ]


def test_unknown_and_flag_values_are_skipped() -> None:
    before, after = nation_pair({"regions": REGIONS, "GDP": Unknown()}, {"regions": REGIONS, "GDP": 5.0e9})
    assert analyze(ANALYZER, before, after) == []
    before, after = nation_pair(
        {"regions": REGIONS, "numNuclearWeapons": False}, {"regions": REGIONS, "numNuclearWeapons": 3}
    )
    assert analyze(ANALYZER, before, after) == []


def test_the_threshold_scales_with_the_interval() -> None:
    week = {"before": "2031-03-01T00:00:00", "after": "2031-03-08T00:00:00"}
    four_months = {"before": "2031-03-01T00:00:00", "after": "2031-06-29T00:00:00"}
    for dates, expected in ((week, 1), (four_months, 0)):
        before, after = nation_pair(
            {"regions": REGIONS, "cohesion": 2.0}, {"regions": REGIONS, "cohesion": 4.5}, **dates
        )
        assert len(analyze(ANALYZER, before, after)) == expected, dates
    # Discrete statistics count every change whatever the interval.
    before, after = nation_pair(
        {"regions": REGIONS, "numNuclearWeapons": 0}, {"regions": REGIONS, "numNuclearWeapons": 1}, **four_months
    )
    assert only(analyze(ANALYZER, before, after), STATISTIC_SHIFTED).attribute("interval_days") == 120.0


def test_interval_days_reads_the_dates_and_declines_unknown_or_reversed_intervals() -> None:
    assert interval_days(snapshot(BEFORE), snapshot(AFTER)) == QUARTER
    assert interval_days(snapshot(BEFORE, date=Unknown()), snapshot(AFTER)) is None
    assert interval_days(snapshot(BEFORE, date="not a date"), snapshot(AFTER)) is None
    assert interval_days(snapshot(AFTER), snapshot(BEFORE)) is None


@pytest.mark.parametrize(
    ("before", "after", "threshold", "days", "expected"),
    [
        (100.0, 104.0, GDP, None, False),  # floor 5%
        (100.0, 105.0, GDP, None, True),
        (100.0, 110.0, GDP, 7.0, True),  # the floor governs a short interval
        (100.0, 110.0, GDP, QUARTER, False),  # 4%/month over three months: 12.1%
        (0.0, 1.0, GDP, QUARTER, True),  # from zero: an infinite relative change
        (5.0, 6.9, COHESION, None, False),
        (5.0, 7.0, COHESION, None, True),
        (5.0, 7.0, COHESION, QUARTER, False),
        (3.0, 4.0, DISCRETE, 365.0, True),
    ],
)
def test_is_shift_applies_the_larger_of_the_floor_and_the_scaled_rate(
    before: float, after: float, threshold: StatisticThreshold, days: float | None, expected: bool
) -> None:
    assert is_shift(before, after, threshold, days) is expected
