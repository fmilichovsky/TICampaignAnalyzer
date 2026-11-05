"""The indexed event stream: every lookup equals the matching filter over the stream, in stream order."""

from __future__ import annotations

from tests.narrative.support import atomic, faction, nation
from tinarrative.model.events import Event
from tinarrative.narrative.chronology import interval_of
from tinarrative.narrative.stream import EventStream

K1 = "2032-04-01T00:00:00"
K2 = "2032-07-01T00:00:00"
GERMANY, FRANCE, ITALY = nation("1"), nation("2"), nation("3")
ACADEMY = faction("10")

EVENTS = (
    atomic("nation.changed/1", K1, entities=(GERMANY,)),
    atomic("point.changed/7", K1, entities=(nation("70"), FRANCE, ACADEMY)),
    atomic("nation.changed/2", K1, entities=(FRANCE, GERMANY)),
    atomic("campaign.changed/x", K1),
    atomic("nation.shifted/1", K2, entities=(GERMANY, GERMANY)),
    atomic("nation.changed/1", K2, entities=(GERMANY,)),
    atomic("point.changed/8", K2, entities=(nation("80"), GERMANY)),
    atomic("nation.changed/3", K2, entities=(ITALY, FRANCE)),
)
STREAM = EventStream(EVENTS)


def ids(events: list[Event]) -> list[str]:
    return [event.id for event in events]


def test_it_is_the_wrapped_sequence() -> None:
    assert list(STREAM) == list(EVENTS)
    assert len(STREAM) == len(EVENTS)
    assert STREAM[1] is EVENTS[1]
    assert list(STREAM[2:4]) == list(EVENTS[2:4])
    assert EventStream.of(STREAM) is STREAM
    assert list(EventStream.of(list(EVENTS))) == list(EVENTS)


def test_of_type_equals_the_type_filter_in_stream_order() -> None:
    types = ("point.changed", "nation.changed")
    assert ids(STREAM.of_type(*types)) == ids([event for event in EVENTS if event.event_type in types])
    assert STREAM.of_type("war.changed") == []
    assert STREAM.of_type() == []


def test_of_subject_matches_the_first_entity_only() -> None:
    subjects = {GERMANY.entity_id, FRANCE.entity_id}
    expected = [
        event
        for event in EVENTS
        if event.event_type in ("nation.changed", "nation.shifted")
        and event.entities
        and event.entities[0].entity_id in subjects
    ]
    assert ids(STREAM.of_subject(subjects, "nation.changed", "nation.shifted")) == ids(expected)
    assert ids(STREAM.of_subject(ITALY.entity_id, "nation.changed")) == [EVENTS[7].id]
    assert STREAM.of_subject(ACADEMY.entity_id, "point.changed") == []


def test_mentioning_matches_any_entity_once() -> None:
    expected = [
        event
        for event in EVENTS
        if event.event_type in ("nation.shifted", "point.changed")
        and any(ref.entity_id == GERMANY.entity_id for ref in event.entities)
    ]
    assert ids(STREAM.mentioning(GERMANY.entity_id, "nation.shifted", "point.changed")) == ids(expected)
    assert ids(STREAM.mentioning(ACADEMY.entity_id, "point.changed")) == [EVENTS[1].id]


def test_in_intervals_matches_the_qualifying_interval() -> None:
    assert ids(STREAM.in_intervals(K2, "nation.changed")) == ids(
        [event for event in EVENTS if event.event_type == "nation.changed" and interval_of(event.id) == K2]
    )
    both = ids(STREAM.in_intervals({K1, K2}, "point.changed", "campaign.changed"))
    assert both == ids([event for event in EVENTS if event.event_type in ("point.changed", "campaign.changed")])
    assert STREAM.in_intervals("2040-01-01T00:00:00", "nation.changed") == []


def test_get_and_union() -> None:
    assert STREAM.get(EVENTS[3].id) is EVENTS[3]
    assert STREAM.get("missing") is None
    union = STREAM.union([EVENTS[5], EVENTS[0]], [EVENTS[0], EVENTS[2]], ())
    assert ids(union) == ids([EVENTS[0], EVENTS[2], EVENTS[5]])
