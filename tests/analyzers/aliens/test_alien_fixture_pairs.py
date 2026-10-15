"""Acceptance for the region alien analyzer and the megafauna marker over the aliens fixture pair."""

import pytest

from tests.analyzers.support import fixture_pair
from tinarrative.analyzers import ALIEN_ANALYZERS, ALL_ANALYZERS, run_analyzers
from tinarrative.analyzers.render import describe_event
from tinarrative.model.events import DateBasis, Event, EventStatus

PAIR = ("aliens_before.json", "aliens_after.json")
FORBIDDEN = ("detect", "clear", "crashed", "repel", "destroy", "spawn", "invad")


def run_all() -> tuple[Event, ...]:
    return run_analyzers(ALL_ANALYZERS, *fixture_pair(*PAIR))


@pytest.mark.fixture
def test_aliens_pair_yields_one_event_per_headline_field() -> None:
    events = run_analyzers(ALIEN_ANALYZERS, *fixture_pair(*PAIR))
    assert [event.id for event in events] == [
        "region.crashdown_changed/region alien state:100",
        "region.alien_facility_changed/region alien state:112",
        "region.landing_changed/region alien state:121",
        "region.xenoforming_changed/region alien state:103",
        "region.xenoforming_changed/region alien state:113",
    ]
    assert all(event.status is EventStatus.OBJECTIVE for event in events)
    assert all(event.entities[0].entity_id.domain.value == "region" for event in events)


@pytest.mark.fixture
def test_crashdown_appears_with_its_date_xenoforming_rises_and_drops_to_zero() -> None:
    by_id = {event.id: event for event in run_all()}
    crashdown = by_id["region.crashdown_changed/region alien state:100"]
    assert (crashdown.date, crashdown.date_basis) == ("2032-02-14T00:00:00", DateBasis.RECORD)
    assert [str(ref.entity_id) for ref in crashdown.entities] == ["region:40", "region alien state:100"]
    rising = by_id["region.xenoforming_changed/region alien state:103"]
    dropping = by_id["region.xenoforming_changed/region alien state:113"]
    assert (rising.attribute("before"), rising.attribute("after")) == (0.0, 2.5)
    assert (dropping.attribute("before"), dropping.attribute("after")) == (3.0, 0.0)


@pytest.mark.fixture
def test_megafauna_army_appears_marked_and_lines_avoid_inferred_wording() -> None:
    events = run_all()
    army = next(event for event in events if event.id == "army.appeared/army:51")
    assert army.attribute("megafauna") is True
    lines = {describe_event(event) for event in events if event.event_type.startswith("region.")}
    assert lines >= {
        "region:40 crashdown present: false -> true; crashdown time 2032-02-14T00:00:00",
        "region:40 xenoforming level: 0.0 -> 2.5",
        "region:41 xenoforming level: 3.0 -> 0.0",
        "region:41 alien facility built: false -> true",
        "region:42 landing present: false -> true",
    }
    assert describe_event(army).endswith("(megafauna)")
    for line in lines:
        assert not any(word in line.lower() for word in FORBIDDEN), line
