"""Per-capita GDP trends: the trailing window, the first crossing, broken windows, quarter dates and the backstory."""

from dataclasses import replace
from datetime import datetime

import pytest

from tests.analyzers.support import AFTER, BEFORE, analyze, region_ref, snapshot, state
from tinarrative.analyzers.politics import NationEconomyAnalyzer
from tinarrative.analyzers.politics.nation_economy import (
    SERIES,
    TREND_QUARTERS,
    campaign_start,
    new_trend,
    quarter_date,
    trend,
)
from tinarrative.kinds import describe_event
from tinarrative.kinds.nations import PCGDP_TREND
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import DateBasis, SourceRole
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.model.values import freeze

ANALYZER = NationEconomyAnalyzer()
BACKSTORY = NationEconomyAnalyzer(before_sequence=True)
NATION = EntityDomain.NATION
REGIONS = (region_ref("40"),)
START_DAYS_BEFORE, START_DAYS_AFTER = 1854, 1946
"""Campaign days of the fixture dates 2031-03-01 and 2031-06-01 for a campaign starting 2026-02-01."""
LAST = 21
"""The quarter of 2031-06-01: the 21st calendar quarter after 2026's first."""


def flat(last: int, value: float = 100.0) -> dict[int, float]:
    return dict.fromkeys(range(last + 1), value)


def series_pair(
    before: dict[int, float], after: dict[int, float], *, regions: tuple[object, ...] = REGIONS
) -> tuple[SaveSnapshot, SaveSnapshot]:
    def nation(save: str, series: dict[int, float]) -> SaveSnapshot:
        tracker = freeze({str(key): value for key, value in series.items()})
        return snapshot(save, state(NATION, "20", save, regions=regions, **{SERIES: tracker}))  # type: ignore[arg-type]

    return (
        replace(nation(BEFORE, before), campaign_day=START_DAYS_BEFORE),
        replace(nation(AFTER, after), campaign_day=START_DAYS_AFTER),
    )


def test_a_boom_is_reported_at_the_quarter_its_trend_first_exceeds_the_threshold() -> None:
    series = flat(LAST) | {20: 140.0, LAST: 160.0}
    before, after = series_pair({key: series[key] for key in range(LAST)}, series)
    (event,) = analyze(ANALYZER, before, after)
    assert event.event_type == PCGDP_TREND.event_type and event.id == f"{PCGDP_TREND.event_type}/nation:20/{LAST}"
    assert (event.date, event.date_basis) == ("2031-04-01T00:00:00", DateBasis.RECORD)
    assert dict(event.attributes) == {
        "direction": "boom",
        "quarter": LAST,
        "window_quarters": TREND_QUARTERS,
        "window_start": "2026-04-01T00:00:00",
        "before": 100.0,
        "after": 160.0,
        "change": pytest.approx(0.6),
        "before_sequence": False,
    }
    assert [source.role for source in event.sources] == [SourceRole.PRIMARY]
    assert (
        describe_event(event) == f"Fixture nation 20 (nation:20) per-capita GDP boom at quarter {LAST}: 100.0 -> 160.0"
    )


def test_a_trend_that_already_held_a_quarter_earlier_is_not_reported_again() -> None:
    series = flat(LAST) | {20: 155.0, LAST: 160.0}
    before, after = series_pair({key: series[key] for key in range(LAST)}, series)
    assert analyze(ANALYZER, before, after) == []
    assert new_trend(series, 20) == "boom" and new_trend(series, LAST) is None


def test_a_slump_and_a_dip_back_inside_the_band() -> None:
    series = flat(LAST) | {LAST: 70.0}
    before, after = series_pair({key: series[key] for key in range(LAST)}, series)
    (event,) = analyze(ANALYZER, before, after)
    assert event.attribute("direction") == "slump"
    assert new_trend(flat(LAST) | {LAST: 80.0}, LAST) is None


def test_a_zero_or_a_missing_key_ends_the_window() -> None:
    series = flat(LAST) | {LAST: 160.0}
    assert trend(series, LAST) is not None
    assert trend(series | {5: 0.0}, LAST) is None
    assert trend({key: value for key, value in series.items() if key != 5}, LAST) is None
    assert trend(series, TREND_QUARTERS - 1) is None
    before, after = series_pair({key: series[key] for key in range(LAST)} | {5: 0.0}, series | {5: 0.0})
    assert analyze(ANALYZER, before, after) == []


def test_quarters_follow_the_calendar_from_the_campaign_start() -> None:
    start = datetime(2026, 2, 1, 8, 30)
    assert quarter_date(start, 0) == "2026-02-01T00:00:00"
    assert quarter_date(start, 1) == "2026-04-01T00:00:00"
    assert quarter_date(start, 4) == "2027-01-01T00:00:00"
    assert quarter_date(start, 83) == "2046-10-01T00:00:00"
    assert quarter_date(None, 1) is None
    _, after = series_pair({}, {})
    assert campaign_start(after) == datetime(2026, 2, 1)
    assert campaign_start(replace(after, campaign_day=None)) is None


def test_the_backstory_instance_judges_only_the_quarters_before_the_earlier_save() -> None:
    series = flat(LAST) | {20: 160.0, LAST: 161.0}
    before, after = series_pair({key: series[key] for key in range(LAST)}, series)
    assert analyze(ANALYZER, before, after) == []
    (event,) = analyze(BACKSTORY, before, after)
    assert event.attribute("quarter") == 20 and event.attribute("before_sequence") is True
    assert event.date == "2031-01-01T00:00:00"


def test_placeholders_are_skipped() -> None:
    series = flat(LAST) | {LAST: 160.0}
    before, after = series_pair({key: series[key] for key in range(LAST)}, series, regions=())
    assert analyze(ANALYZER, before, after) == []
