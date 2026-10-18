"""Interval qualification of event IDs and the chronological stream of a save sequence."""

from __future__ import annotations

import pytest

from tinarrative.model.events import Confidence, DateBasis, Event, EventStatus
from tinarrative.narrative.chronology import chronological, qualified_id, qualify
from tinarrative.reconstruction import ID_ATTRIBUTES

KEY = "2032-04-01T00:00:00"


def event(event_id: str, date: str = KEY, **overrides: object) -> Event:
    fields: dict[str, object] = {
        "id": event_id,
        "event_type": event_id.split("/")[0],
        "status": EventStatus.OBJECTIVE,
        "confidence": Confidence.HIGH,
        "date": date,
        "date_basis": DateBasis.INTERVAL,
        "not_before": "2032-01-01T00:00:00",
        "sources": (),
        "entities": (),
    }
    fields.update(overrides)
    return Event(**fields)  # type: ignore[arg-type]


def test_qualify_rewrites_the_id_the_constituents_and_the_id_attributes_alike() -> None:
    inferred = event(
        "nation.unification/nation:20",
        status=EventStatus.INFERRED,
        constituents=("region.nation_changed/region:42", "nation.disappeared/nation:21"),
        attributes=(("alternatives", ("nation.annexation/nation:20/nation:21",)), ("region_count", 2)),
    )

    qualified = qualify(inferred, KEY)

    assert "alternatives" in ID_ATTRIBUTES
    assert qualified.id == f"nation.unification/nation:20@{KEY}"
    assert qualified.constituents == (
        f"nation.disappeared/nation:21@{KEY}",
        f"region.nation_changed/region:42@{KEY}",
    )
    assert qualified.attribute("alternatives") == (f"nation.annexation/nation:20/nation:21@{KEY}",)
    assert qualified.attribute("region_count") == 2
    assert (qualified.date, qualified.event_type, qualified.sources) == (inferred.date, inferred.event_type, ())


def test_the_same_raw_id_in_two_intervals_stays_distinct_in_the_stream() -> None:
    later = "2032-07-01T00:00:00"
    first = qualify(event("region.nation_changed/region:42"), KEY)
    second = qualify(event("region.nation_changed/region:42", date=later), later)

    assert [item.id for item in chronological([second, first])] == [
        qualified_id("region.nation_changed/region:42", KEY),
        qualified_id("region.nation_changed/region:42", later),
    ]


def test_a_duplicate_id_in_the_stream_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="duplicate event IDs"):
        chronological([event("region.nation_changed/region:42"), event("region.nation_changed/region:42")])
