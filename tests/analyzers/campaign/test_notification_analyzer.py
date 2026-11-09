"""The notification analyzer on synthetic snapshots: edge cases the fixture pair does not cover."""

from tests.analyzers.support import AFTER, BEFORE, analyze, only, record_set, snapshot, state
from tinarrative.analyzers.campaign import NotificationAnalyzer
from tinarrative.kinds import describe_event
from tinarrative.kinds.campaign import entry_kind
from tinarrative.model.entities import EntityDomain, EntityRef
from tinarrative.model.events import DateBasis, Event
from tinarrative.model.records import NotificationEntry, RecordKind, RecordSet
from tinarrative.model.snapshot import EntityState
from tinarrative.model.values import Observed, Unknown, UnknownReason

KEY = "80"
LOG = "notificationSummaryQueue"
AFTER_DATE = snapshot(AFTER).date


def queue(save: str, **fields: Observed) -> EntityState:
    return state(EntityDomain.NOTIFICATION_QUEUE, KEY, save, **fields)


def owner(save: str) -> EntityRef:
    return queue(save).ref


def log(save: str, *entries: NotificationEntry) -> RecordSet:
    return record_set(save, owner(save), LOG, RecordKind.NOTIFICATION_LOG, entries)


def notice(index: int, template: Observed, date: Observed = "2031-05-01T00:00:00") -> NotificationEntry:
    return NotificationEntry(index, template, date, "Fixture summary.", "None", None, False, (), ())


def run(before: tuple[NotificationEntry, ...], after: tuple[NotificationEntry, ...]) -> list[Event]:
    return analyze(
        NotificationAnalyzer(),
        snapshot(BEFORE, queue(BEFORE), records=(log(BEFORE, *before),)),
        snapshot(AFTER, queue(AFTER), records=(log(AFTER, *after),)),
    )


def test_a_template_that_is_not_an_identifier_gets_the_unknown_template_type() -> None:
    assert entry_kind("LogFleetDetected").event_type == "notification.LogFleetDetected"
    assert entry_kind(Unknown(UnknownReason.UNPARSEABLE)).event_type == "notification.unknown_template"
    assert entry_kind("Log Fleet").event_type == "notification.unknown_template"
    assert entry_kind("entry_removed").event_type == "notification.unknown_template"  # never collides with a fixed type
    (event,) = run((), (notice(0, None),))
    assert event.event_type == "notification.unknown_template"


def test_an_entry_with_an_unparseable_date_falls_back_to_the_interval_date() -> None:
    (event,) = run((), (notice(0, "LogFleetDetected", Unknown(UnknownReason.UNPARSEABLE)),))
    assert (event.date, event.date_basis) == (AFTER_DATE, DateBasis.INTERVAL)


def test_a_queue_that_appears_is_one_presence_event_not_one_per_entry() -> None:
    events = analyze(
        NotificationAnalyzer(),
        snapshot(BEFORE),
        snapshot(AFTER, queue(AFTER), records=(log(AFTER, notice(0, "LogFleetDetected")),)),
    )
    event = only(events, "notification.queue_appeared")
    assert len(events) == 1 and event.attribute("side") == "after"
    assert (
        describe_event(event)
        == f"Fixture notification queue {KEY} (notification queue:{KEY}) is present only in the after snapshot"
    )


def test_an_unchanged_log_yields_nothing_and_a_singleton_field_change_is_literal() -> None:
    entry = notice(0, "LogFleetDetected")
    assert run((entry,), (notice(5, "LogFleetDetected"),)) == []
    events = analyze(
        NotificationAnalyzer(),
        snapshot(BEFORE, queue(BEFORE, displayName="A")),
        snapshot(AFTER, queue(AFTER, displayName="B")),
    )
    event = only(events, "notification.queue_value_changed")
    assert event.attribute("field") == "displayName"
